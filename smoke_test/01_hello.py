"""Smoke test 1: basic LLM call.

Verifies API key, base URL, and SDK installation all work end-to-end.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.llm import call


def main() -> None:
    r = call([{"role": "user", "content": "Reply with exactly: hello world"}])
    print("--- response ---")
    print(r.text)
    print("--- usage ---")
    print(r.summary())

    assert "hello" in r.text.lower(), f"unexpected response: {r.text!r}"
    print("\n[PASS] basic call works")


if __name__ == "__main__":
    main()
