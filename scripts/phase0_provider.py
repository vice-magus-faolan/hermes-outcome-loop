# SPDX-License-Identifier: GPL-3.0-or-later
"""Loopback scripted model transport; NEVER a fake plugin/native dispatch adapter.

Drives one real worker tool call through Hermes's actual client and agent loop.
All board verdicts come from native tools, not model text. No outbound provider.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ScriptedProvider:
    """Serve deterministic OpenAI-compatible responses for one disposable worker."""

    def __init__(self, arguments):
        self.arguments = arguments
        self.requests = []
        self.results = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                self.send({"data": [{"id": "phase0-model", "object": "model"}]})

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(request)
                for message in request.get("messages", []):
                    if message.get("role") == "tool" and message.get("name") == "phase0_worker_check":
                        owner.results.append(json.loads(message["content"]))
                main = any(tool.get("function", {}).get("name") == "phase0_worker_check"
                           for tool in request.get("tools", []))
                seen_result = any(message.get("role") == "tool" for message in request.get("messages", []))
                message = {"role": "assistant", "content": "Disposable transport complete"}
                finish = "stop"
                if main and not seen_result:
                    message = {"role": "assistant", "content": None, "tool_calls": [{
                        "id": "call_phase0", "type": "function", "function": {
                            "name": "phase0_worker_check", "arguments": json.dumps(owner.arguments)}}]}
                    finish = "tool_calls"
                if request.get("stream"):
                    self.stream(message, finish)
                else:
                    self.send({"id": "probe-response", "object": "chat.completion", "created": 1,
                               "model": "phase0-model", "choices": [{"index": 0, "message": message,
                                                                      "finish_reason": finish}],
                               "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})

            def send(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def stream(self, message, finish):
                delta = dict(message)
                if "tool_calls" in delta:
                    delta["tool_calls"][0]["index"] = 0
                chunks = [{"id": "probe-response", "object": "chat.completion.chunk", "created": 1,
                           "model": "phase0-model", "choices": [{"index": 0, "delta": delta,
                                                                  "finish_reason": None}]},
                          {"id": "probe-response", "object": "chat.completion.chunk", "created": 1,
                           "model": "phase0-model", "choices": [{"index": 0, "delta": {},
                                                                  "finish_reason": finish}]}]
                body = "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body.encode())))
                self.end_headers()
                self.wfile.write(body.encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.server_port}/v1"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
