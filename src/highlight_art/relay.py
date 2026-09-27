"""Authenticated LAN relay for highlight uploads and background downloads."""
from __future__ import annotations

import hmac
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer

from .ingest import ingest_clippings, ingest_koreader_batch
from .rotation import current_manifest
from .store import Store


class RelayHTTPServer(ThreadingHTTPServer):
    def server_bind(self) -> None:
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.socket.getsockname()[:2]


def make_handler(store: Store, token: str, *, max_body_bytes: int = 5_000_000):
    class Handler(BaseHTTPRequestHandler):
        server_version = "HighlightArtRelay/1"

        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            return hmac.compare_digest(supplied, f"Bearer {token}")

        def _json(self, status: HTTPStatus, payload: dict | list) -> None:
            body = json.dumps(payload, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _guard(self) -> bool:
            if not self._authorized():
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return False
            return True

        def _body(self) -> bytes:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("invalid Content-Length") from exc
            if length <= 0 or length > max_body_bytes:
                raise ValueError("invalid body length")
            return self.rfile.read(length)

        def do_GET(self) -> None:  # noqa: N802
            if not self._guard():
                return
            if self.path == "/v1/health":
                self._json(HTTPStatus.OK, {"ok": True, "manifest": len(current_manifest(store).get("backgrounds", []))})
                return
            if self.path == "/v1/backgrounds/manifest":
                self._json(HTTPStatus.OK, current_manifest(store))
                return
            match = re.fullmatch(r"/v1/backgrounds/([a-f0-9]{24}-[a-f0-9]{12})\.png", self.path)
            if not match:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            path = store.background_path(match.group(1))
            if not path.exists():
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", f'"{match.group(1).rsplit("-", 1)[-1]}"')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if not self._guard():
                return
            try:
                body = self._body()
                if self.path == "/v1/clippings":
                    result = ingest_clippings(store, body, source="kindle-clippings")
                elif self.path == "/v1/highlights":
                    result = ingest_koreader_batch(store, json.loads(body))
                elif self.path == "/v1/backgrounds/receipts":
                    receipt = json.loads(body)
                    if not isinstance(receipt, dict):
                        raise ValueError("receipt must be an object")
                    result = {"receipt_id": store.save_receipt(receipt)}
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json(HTTPStatus.OK, result)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def serve(store: Store, token: str, host: str, port: int, *, max_body_bytes: int = 5_000_000) -> None:
    if len(token) < 24:
        raise ValueError("HIGHLIGHT_ART_RELAY_TOKEN must contain at least 24 characters")
    server = RelayHTTPServer((host, port), make_handler(store, token, max_body_bytes=max_body_bytes))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
