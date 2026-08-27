#!/usr/bin/env python3
import json
import re
import sys
from urllib.parse import urlparse


UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,15}-[0-9]+\b", re.IGNORECASE)


def parse(text: str) -> dict:
    text = text.strip()
    result = {"issue_ref": "", "workspace_slug": "", "url": ""}

    for token in re.findall(r"https?://\S+", text):
        parsed = urlparse(token.rstrip(".,;，。；）)]"))
        parts = [p for p in parsed.path.split("/") if p]
        if "issues" in parts:
            idx = parts.index("issues")
            if idx + 1 < len(parts):
                result["issue_ref"] = parts[idx + 1]
                result["url"] = parsed.geturl()
                if idx > 0:
                    result["workspace_slug"] = parts[idx - 1]
                return result

    uuid_match = UUID_RE.search(text)
    if uuid_match:
        result["issue_ref"] = uuid_match.group(0)
        return result

    key_match = KEY_RE.search(text)
    if key_match:
        result["issue_ref"] = key_match.group(0).upper()
        return result

    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: parse_issue_input.py <issue-url-or-ref>", file=sys.stderr)
        return 2
    parsed = parse(" ".join(sys.argv[1:]))
    if not parsed["issue_ref"]:
        print(json.dumps(parsed, ensure_ascii=False))
        return 1
    print(json.dumps(parsed, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
