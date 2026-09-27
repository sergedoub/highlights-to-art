import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from highlight_art.relay import RelayHTTPServer, make_handler
from highlight_art.store import Store


TOKEN = "t" * 32


def request(base, path, *, token=TOKEN, data=None, content_type="application/json"):
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = content_type
    return urlopen(Request(base + path, data=data, headers=headers), timeout=3)


def test_relay_auth_ingest_and_receipts(tmp_path):
    store = Store(tmp_path)
    server = RelayHTTPServer(("127.0.0.1", 0), make_handler(store, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        try:
            request(base, "/v1/health", token="wrong")
            raise AssertionError("expected unauthorized request")
        except HTTPError as exc:
            assert exc.code == 401

        clipping = b"Work (Author)\n- Your Highlight on Location 1 | Added on today\n\nExact text.\n==========\n"
        with request(base, "/v1/clippings", data=clipping, content_type="text/plain") as response:
            assert json.load(response)["added"] == 1

        receipt = json.dumps({"receipt_id": "device-sync-123", "active": 1}).encode()
        with request(base, "/v1/backgrounds/receipts", data=receipt) as response:
            assert json.load(response)["receipt_id"] == "device-sync-123"
        assert (store.receipts / "device-sync-123.json").exists()

        unsafe = json.dumps({"receipt_id": "../../escape", "active": 1}).encode()
        try:
            request(base, "/v1/backgrounds/receipts", data=unsafe)
            raise AssertionError("expected unsafe receipt id to fail")
        except HTTPError as exc:
            assert exc.code == 400
    finally:
        server.shutdown()
        server.server_close()
