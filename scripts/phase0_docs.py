#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit official-doc retrieval receipts, separate from offline verification.

Fetches only these fixed public documentation pages, never evidence pointers.
No downloaded files or page instructions are executed or persisted.
"""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import urllib.request

URLS = ["https://hermes-agent.nousresearch.com/docs/developer-guide/plugins",
        "https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban",
        "https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks"]


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignore += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignore -= 1

    def handle_data(self, data):
        if not self.ignore:
            self.parts.append(data)


def main():
    results = []
    for url in URLS:
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read()
        parser = Text()
        parser.feed(body.decode())
        text = " ".join(parser.parts)
        snippets = {}
        for token in ("dispatch_tool", "kanban_task_completed", "post-commit", "isolated", "board"):
            position = text.find(token)
            if position >= 0:
                snippets[token] = text[max(0, position - 100):position + 350]
        results.append({"url": url, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                        "interface_snippets": snippets})
    print(json.dumps({"retrieved_utc": datetime.now(timezone.utc).isoformat(), "pages": results}, indent=2))


if __name__ == "__main__":
    main()
