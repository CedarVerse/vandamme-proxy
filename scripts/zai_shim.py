#!/usr/bin/env python3
"""vandamme-proxy utility — NON-STREAMING <-> STREAMING BRIDGE (stream-shim).

For an upstream that only accepts streaming requests (or when you want to force
all upstream traffic to streaming and normalize it), this shim:
  - rewrites a non-streaming client request to `stream:true` before forwarding,
  - reads the SSE response and re-assembles it into the single Messages JSON the
    client expected (so a non-streaming caller never knows the upstream streamed).
Streaming client requests pass straight through, byte-for-byte.

HISTORY / honesty note (don't inherit the wrong belief): this was written while
chasing a GLM/z.ai outage where *every* request returned `1210 Invalid API
parameter`, on the hypothesis that **z.ai requires streaming**. That hypothesis
was WRONG. z.ai accepts non-streaming fine; the real cause was an MCP tool schema
it rejected (Zod `z.tuple` -> array-form JSON-Schema `items:[…]`). See
https://github.com/elifarley/hub/issues/134 . The shim is kept only because the
SSE->JSON bridge is independently useful — it is NOT required to talk to z.ai.

Usage:
    VANDAMME_UPSTREAM=https://api.z.ai/api/anthropic \\
    VANDAMME_SHIM_PORT=8789 python3 zai_shim.py
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
PORT = int(os.environ.get("VANDAMME_SHIM_PORT", "8789"))

# GOTCHA: hop-by-hop headers must not be relayed (RFC 7230 §6.1). `accept` is also
# stripped here because the shim sets its own `accept: text/event-stream` when it
# forces streaming; `accept-encoding` is dropped so the SSE arrives uncompressed.
HOP = {
    "host",
    "content-length",
    "accept-encoding",
    "accept",
    "expect",
    "connection",
    "keep-alive",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "proxy-connection",
}


def aggregate_sse(raw: bytes):
    """Collapse an Anthropic Messages SSE stream into one final Message dict.

    Returns (message, None) on success, or (None, error_event) if the stream
    carried a failure.
    """
    msg, blocks, partial = None, {}, {}
    stop_reason = stop_sequence = None
    usage = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            ev = json.loads(payload)
        except Exception:
            continue
        t = ev.get("type")
        if t == "message_start":
            msg = ev["message"]
            usage = dict(msg.get("usage") or {})
        elif t == "content_block_start":
            i = ev["index"]
            block = dict(ev["content_block"])
            blocks[i] = block
            # tool_use args arrive as streamed JSON fragments; buffer to re-parse at stop.
            if block.get("type") == "tool_use":
                partial[i] = ""
        elif t == "content_block_delta":
            i = ev["index"]
            d = ev.get("delta", {})
            dt = d.get("type")
            if dt == "text_delta":
                blocks[i]["text"] = blocks[i].get("text", "") + d.get("text", "")
            elif dt == "thinking_delta":
                blocks[i]["thinking"] = blocks[i].get("thinking", "") + d.get("thinking", "")
            elif dt == "signature_delta":
                blocks[i]["signature"] = blocks[i].get("signature", "") + d.get("signature", "")
            elif dt == "input_json_delta":
                partial[i] = partial.get(i, "") + d.get("partial_json", "")
        elif t == "content_block_stop":
            i = ev["index"]
            if i in partial:  # finalize a tool_use block's buffered JSON args
                try:
                    blocks[i]["input"] = json.loads(partial[i] or "{}")
                except Exception:
                    blocks[i]["input"] = {}
        elif t == "message_delta":
            d = ev.get("delta", {})
            stop_reason = d.get("stop_reason", stop_reason)
            stop_sequence = d.get("stop_sequence", stop_sequence)
            if ev.get("usage"):
                usage.update(ev["usage"])
        elif t == "error":
            # GOTCHA: the upstream can return HTTP 200 and THEN stream this error
            # event. Surface it as a real error instead of returning a bogus empty
            # 200 — otherwise the caller sees "success" with no content. This
            # in-stream-error trap is the #1 source of misdiagnosis with these
            # gateways: never equate "HTTP 200" with "the request succeeded".
            return None, ev
    if msg is None:
        return None, {
            "type": "error",
            "error": {"type": "api_error", "message": "empty upstream stream"},
        }
    msg["content"] = [blocks[i] for i in sorted(blocks)]
    msg["stop_reason"] = stop_reason
    msg["stop_sequence"] = stop_sequence
    if usage:
        msg["usage"] = usage
    return msg, None


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        with contextlib.suppress(Exception):
            self.wfile.write(body)

    def _do(self) -> None:
        n = int(self.headers.get("content-length", "0") or 0)
        body = self.rfile.read(n) if n else b""
        try:
            j = json.loads(body)
        except Exception:
            j = None
        # Only POSTs carrying a JSON body that isn't already streaming need bridging.
        force = j is not None and self.command == "POST" and j.get("stream") is not True
        if force:
            j["stream"] = True
            body = json.dumps(j).encode()

        req = urllib.request.Request(UPSTREAM + self.path, data=body or None, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in HOP:
                req.add_header(k, v)
        if force:
            req.add_header("accept", "text/event-stream")

        try:
            r = urllib.request.urlopen(req, timeout=180, context=ssl.create_default_context())
        except urllib.error.HTTPError as e:  # synchronous upstream error — relay verbatim
            self._send(e.code, e.read(), e.headers.get("content-type", "application/json"))
            return
        except Exception as e:
            self._send(
                502,
                json.dumps(
                    {"type": "error", "error": {"type": "api_error", "message": repr(e)}}
                ).encode(),
            )
            return

        if not force:
            # Client wanted streaming: pass the SSE through chunk-by-chunk.
            # GOTCHA: never buffer-then-forward a stream — it defeats streaming and
            # can make the client time out or fall back to a non-streamed retry.
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
            return

        # Client wanted non-streaming: aggregate the forced SSE back into one JSON.
        msg, err = aggregate_sse(r.read())
        if err is not None:
            self._send(400, json.dumps(err).encode())
            return
        self._send(200, json.dumps(msg).encode())

    # http.server dispatches each request to a method named exactly do_<HTTP-METHOD>,
    # so these framework-required names can't be snake_case (N815).
    do_POST = _do  # noqa: N815
    do_GET = _do  # noqa: N815

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    print(f"stream-shim: http://{HOST}:{PORT}  ->  {UPSTREAM}")
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
