local DataStorage = require("datastorage")
local LuaSettings = require("luasettings")
local NetworkMgr = require("ui/network/manager")
local UIManager = require("ui/uimanager")
local WidgetContainer = require("ui/widget/container/widgetcontainer")
local lfs = require("libs/libkoreader-lfs")
local ltn12 = require("ltn12")
local http = require("socket.http")
local json = require("rapidjson")
local socketutil = require("socketutil")
local util = require("util")
local _ = require("gettext")

local HighlightArt = WidgetContainer:extend{
    name = "highlightart",
    is_doc_only = false,
}

local function fileSignature(path)
    local attrs = lfs.attributes(path)
    if not attrs then return nil end
    return tostring(attrs.size or 0) .. ":" .. tostring(attrs.modification or 0)
end

local function readFile(path)
    local file = io.open(path, "rb")
    if not file then return nil end
    local body = file:read("*all")
    file:close()
    return body
end

local function copyFile(source, target)
    local input = io.open(source, "rb")
    if not input then return false end
    local temporary = target .. ".part"
    local output = io.open(temporary, "wb")
    if not output then input:close() return false end
    while true do
        local chunk = input:read(32768)
        if not chunk then break end
        output:write(chunk)
    end
    input:close()
    output:close()
    os.rename(temporary, target)
    return true
end

function HighlightArt:init()
    self.settings = LuaSettings:open(DataStorage:getSettingsDir() .. "/highlightart.lua")
    self.outbox = self.settings:readSetting("outbox", {})
    self.downloads = self.settings:readSetting("downloads", {})
    self.stock_downloads = self.settings:readSetting("stock_downloads", {})
    self:configureScreensaver()
    self.periodic_sync_task = function()
        self:sync()
        UIManager:scheduleIn(tonumber(self:config().poll_seconds) or 300, self.periodic_sync_task)
    end
    UIManager:scheduleIn(5, self.periodic_sync_task)
end

function HighlightArt:config()
    return self.settings:readSetting("relay", {})
end

function HighlightArt:configureScreensaver()
    if not self:config().manage_screensaver or not G_reader_settings then return end
    if not self.settings:has("previous_screensaver") then
        self.settings:saveSetting("previous_screensaver", {
            screensaver_type = G_reader_settings:readSetting("screensaver_type"),
            screensaver_dir = G_reader_settings:readSetting("screensaver_dir"),
            screensaver_show_message = G_reader_settings:readSetting("screensaver_show_message"),
            screensaver_stretch_images = G_reader_settings:readSetting("screensaver_stretch_images"),
        })
    end
    G_reader_settings:saveSetting("screensaver_type", "random_image")
    G_reader_settings:saveSetting("screensaver_dir", "/mnt/us/highlight-art/screensavers")
    G_reader_settings:makeFalse("screensaver_show_message")
    G_reader_settings:makeFalse("screensaver_stretch_images")
    G_reader_settings:flush()
    self.settings:flush()
end

function HighlightArt:restoreScreensaver()
    local previous = self.settings:readSetting("previous_screensaver")
    if not previous or not G_reader_settings then return end
    for key, value in pairs(previous) do
        if value == nil then
            G_reader_settings:delSetting(key)
        else
            G_reader_settings:saveSetting(key, value)
        end
    end
    G_reader_settings:flush()
    self.settings:delSetting("previous_screensaver")
    self.settings:flush()
end

function HighlightArt:request(method, path, body, content_type, sink)
    local config = self:config()
    if not config.url or not config.token then return nil end
    local headers = { Authorization = "Bearer " .. config.token }
    if body then
        headers["Content-Type"] = content_type or "application/json"
        headers["Content-Length"] = #body
    end
    local chunks = {}
    socketutil:set_timeout(socketutil.FILE_BLOCK_TIMEOUT, socketutil.FILE_TOTAL_TIMEOUT)
    local requested, ok, code = pcall(http.request, {
        method = method,
        url = config.url .. path,
        headers = headers,
        source = body and ltn12.source.string(body) or nil,
        sink = sink or ltn12.sink.table(chunks),
    })
    socketutil:reset_timeout()
    if requested and ok and tonumber(code) and tonumber(code) >= 200 and tonumber(code) < 300 then
        return sink and true or table.concat(chunks)
    end
    return nil
end

function HighlightArt:queue(batch)
    table.insert(self.outbox, batch)
    self.settings:saveSetting("outbox", self.outbox)
    self.settings:flush()
end

function HighlightArt:flushOutbox()
    local remaining = {}
    for _, batch in ipairs(self.outbox) do
        if not self:request("POST", "/v1/highlights", json.encode(batch), "application/json") then
            table.insert(remaining, batch)
        end
    end
    self.outbox = remaining
    self.settings:saveSetting("outbox", remaining)
    self.settings:flush()
end

function HighlightArt:uploadClippings()
    local path = "/mnt/us/documents/My Clippings.txt"
    local signature = fileSignature(path)
    if not signature or signature == self.settings:readSetting("clippings_signature") then return end
    local body = readFile(path)
    if body and #body <= 5000000 and self:request("POST", "/v1/clippings", body, "text/plain; charset=utf-8") then
        self.settings:saveSetting("clippings_signature", signature)
        self.settings:flush()
    end
end

function HighlightArt:cleanup(directory, desired)
    if lfs.attributes(directory, "mode") ~= "directory" then return 0 end
    local removed = 0
    for filename in lfs.dir(directory) do
        if filename:match("^highlight%-art%-.+%.png$") and not desired[filename] then
            if os.remove(directory .. "/" .. filename) then removed = removed + 1 end
        end
    end
    return removed
end

function HighlightArt:syncBackgrounds()
    local payload = self:request("GET", "/v1/backgrounds/manifest")
    if not payload then return end
    local manifest = json.decode(payload)
    local directory = "/mnt/us/highlight-art/screensavers"
    util.makePath(directory)
    local stock = self:config().linkss_enabled and "/mnt/us/linkss/screensavers" or nil
    if stock and lfs.attributes(stock, "mode") ~= "directory" then stock = nil end
    local desired = {}
    local downloaded = 0
    for _, background in ipairs(manifest.backgrounds or {}) do
        local filename = "highlight-art-" .. background.id .. ".png"
        desired[filename] = true
        local path = directory .. "/" .. filename
        local revision = background.sha256 or ""
        local changed = false
        if lfs.attributes(path, "mode") ~= "file" or self.downloads[background.id] ~= revision then
            local temporary = path .. ".part"
            local file = io.open(temporary, "wb")
            if file and self:request("GET", background.download_path, nil, nil, ltn12.sink.file(file)) then
                os.rename(temporary, path)
                self.downloads[background.id] = revision
                downloaded = downloaded + 1
                changed = true
            else
                if file then file:close() end
                os.remove(temporary)
            end
        end
        if stock and lfs.attributes(path, "mode") == "file"
            and (changed or lfs.attributes(stock .. "/" .. filename, "mode") ~= "file"
                or self.stock_downloads[background.id] ~= revision) then
            if copyFile(path, stock .. "/" .. filename) then
                self.stock_downloads[background.id] = revision
            end
        end
    end
    local removed = self:cleanup(directory, desired)
    local stock_removed = stock and self:cleanup(stock, desired) or 0
    self.settings:saveSetting("downloads", self.downloads)
    self.settings:saveSetting("stock_downloads", self.stock_downloads)
    self.settings:flush()
    self:request("POST", "/v1/backgrounds/receipts", json.encode({
        receipt_id = "sync-" .. tostring(os.time()),
        kind = "background_sync",
        downloaded = downloaded,
        removed = removed,
        stock_removed = stock_removed,
        active = #(manifest.backgrounds or {}),
    }), "application/json")
end

function HighlightArt:sync()
    if not NetworkMgr:isOnline() then return end
    self:uploadClippings()
    self:flushOutbox()
    self:syncBackgrounds()
end

function HighlightArt:onResume() self:sync() end
function HighlightArt:onNetworkConnected() self:sync() end

function HighlightArt:onCloseDocument()
    if not self.ui or not self.ui.document then return end
    local props = {}
    pcall(function() props = self.ui.document:getProps() or {} end)
    local rows = {}
    if self.ui.annotation then
        for _, item in ipairs(self.ui.annotation.annotations or {}) do
            local text = item.text or ""
            if text ~= "" then
                table.insert(rows, {
                    source_id = self.ui.document.file or "",
                    work_title = props.title or self.ui.document.file or "Unknown work",
                    author = props.authors or "",
                    location = tostring(item.pageno or item.page or item.pageref or ""),
                    highlighted_at = item.datetime or "",
                    text = text,
                    note = item.note or "",
                })
            end
        end
    end
    if #rows > 0 then
        self:queue({ highlights = rows })
        self:sync()
    end
end

function HighlightArt:addToMainMenu(menu_items)
    menu_items.highlight_art = {
        text = _([[Highlight Art]]),
        sorting_hint = "tools",
        sub_item_table = {
            { text = _([[Sync now]]), callback = function() self:sync() end },
            { text = _([[Restore previous sleep-screen settings]]), callback = function() self:restoreScreensaver() end },
        },
    }
end

function HighlightArt:onCloseWidget()
    UIManager:unschedule(self.periodic_sync_task)
end

return HighlightArt
