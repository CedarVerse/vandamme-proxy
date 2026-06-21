#!/usr/bin/env python3
"""vandamme-proxy debug utility — REQUEST SNITCH.

A transparent logging reverse-proxy: forwards every request to an upstream
Anthropic-compatible endpoint and records the exact on-the-wire request (and, on
failure, the response) to a log file. Born from debugging Claude Code / OpenCode
against GLM/z.ai, where the client surfaced only an opaque generic error.

WHY this exists (the lesson that paid for it): tool-use clients (Claude Code,
OpenCode, any MCP host) send the ENTIRE tool list on EVERY request. So a single
malformed tool schema makes *every* call fail with a generic provider error that
names no tool — the failure looks total and unrelated to tools. The only reliable
way to find the culprit is to capture the exact request here, then replay it
against the upstream while bisecting the payload (drop all tools to confirm, then
bisect halves down to the one tool, then bisect that tool's schema fields).
Reasoning from the error string alone repeatedly sent us down wrong paths.
Full story: https://github.com/elifarley/hub/issues/134

Usage:
    VANDAMME_UPSTREAM=https://api.z.ai/api/anthropic \\
    VANDAMME_SNITCH_PORT=8788 python3 zai_snitch.py
Then point the client at http://127.0.0.1:$PORT (e.g. set ANTHROPIC_BASE_URL).
Inspect the capture:  grep -E '^(REQ|BODY|RESP|event: error)' "$VANDAMME_SNITCH_LOG"
"""

import contextlib
import http.server
import json
import os
import ssl
import urllib.error
import urllib.request

UPSTREAM = os.environ.get("VANDAMME_UPSTREAM", "https://api.z.ai/api/anthropic").rstrip("/")
HOST = os.environ.get("VANDAMME_HOST", "127.0.0.1")
PORT = int(os.environ.get("VANDAMME_SNITCH_PORT", "8788"))
LOG = os.environ.get("VANDAMME_SNITCH_LOG", "/tmp/zai_snitch.log")

# GOTCHA: hop-by-hop headers are per-connection (RFC 7230 §6.1) and must NOT be
# relayed to the upstream — forwarding Connection/TE/Transfer-Encoding/Expect/...
# can corrupt or stall the upstream request. `accept-encoding` is dropped too so
# the upstream replies uncompressed (simpler to capture and aggregate).
HOP = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "proxy-connection",
    "accept-encoding",
    "expect",
}


def log(line: str) -> None:
    with open(LOG, "a") as f:
        f.write(line + "\n")


def redact(headers) -> dict:
    # WHY redact: Authorization / x-api-key carry the provider key. A capture log
    # routinely gets pasted into bug reports — never let a credential ride along.
    return {
        k: ("<redacted>" if k.lower() in ("authorization", "x-api-key") else v)
        for k, v in headers.items()
    }


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _do(self) -> None:
        n = int(self.headers.get("content-length", "0") or 0)
        body = self.rfile.read(n) if n else b""
        try:
            j = json.loads(body)
            stream, model, mt = j.get("stream"), j.get("model"), j.get("max_tokens")
        except Exception:
            j, stream, model, mt = None, "?", "?", "?"
        log(
            f"\n===== REQ {self.command} {self.path}  stream={stream} model={model} max_tokens={mt}"
        )
        log("HEADERS " + json.dumps(redact(self.headers)))  # captures anthropic-beta etc.
        if j is not None:
            log("BODY " + json.dumps(j))

        req = urllib.request.Request(UPSTREAM + self.path, data=body or None, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in HOP:
                req.add_header(k, v)

        try:
            r = urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context())
        except urllib.error.HTTPError as e:  # upstream returned non-2xx synchronously
            data = e.read()
            log(f"RESP {e.code} {data.decode('utf-8', 'replace')[:800]}")
            self._send_bytes(e.code, data, e.headers.get("content-type", "application/json"))
            return
        except Exception as e:
            log(f"PROXY-ERR {e!r}")
            self._send_bytes(
                502, json.dumps({"type": "error", "error": {"message": repr(e)}}).encode()
            )
            return

        # GOTCHA: stream the response through CHUNK-BY-CHUNK; do NOT read it whole
        # then forward. A buffering proxy withholds the first byte until the upstream
        # finishes, which makes streaming clients time out or silently retry as a
        # second (non-streamed) request — a false signal that cost a wrong diagnosis.
        # GOTCHA: a streamed HTTP 200 is NOT proof of success — Anthropic-compatible
        # gateways (z.ai/GLM) answer 200 and then deliver the failure as an in-stream
        # SSE `event: error`. Always grep the captured log for `event: error`; never
        # trust the status line alone.
        self.send_response(r.status)
        for hk, hv in r.headers.items():
            if hk.lower() not in HOP and hk.lower() != "content-encoding":
                self.send_header(hk, hv)
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        while True:
            chunk = r.read(2048)
            if not chunk:
                break
            self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")

    def _send_bytes(self, code: int, data: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        with contextlib.suppress(Exception):
            self.wfile.write(data)

    # http.server dispatches each request to a method named exactly do_<HTTP-METHOD>
    # (do_GET / do_POST), so these framework-required names can't be snake_case (N815).
    do_POST = _do  # noqa: N815
    do_GET = _do  # noqa: N815

    def log_message(self, *args) -> None:  # silence the default stderr access log
        pass


if __name__ == "__main__":
    print(f"snitch: http://{HOST}:{PORT}  ->  {UPSTREAM}   (log: {LOG})")
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
