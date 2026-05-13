"""Smoke test 3: context caching.

DashScope/Qwen does context caching automatically when the prompt prefix
is identical and long enough (~256+ tokens). No explicit cache_control
markers needed (unlike Anthropic).

If cached_tokens stays 0, either:
  - the model doesn't support auto-caching (qwen-turbo and some smaller
    models may not),
  - or the prefix isn't long enough,
  - or the two calls were too far apart in time.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.llm import call

# Long, identical system prefix between calls — gives caching something to hit.
LONG_SYSTEM = (
    "You are a helpful, terse assistant. Always answer in one short sentence. "
) * 250  # ~3000 tokens


def main() -> None:
    print("=== call 1 (warm-up, populates cache) ===")
    r1 = call(
        [{"role": "user", "content": "Say hi."}],
        system=LONG_SYSTEM,
    )
    print(r1.summary())

    time.sleep(1)

    print("\n=== call 2 (expected: cached > 0) ===")
    r2 = call(
        [{"role": "user", "content": "Say hi again."}],
        system=LONG_SYSTEM,
    )
    print(r2.summary())

    if r2.cached_tokens > 0:
        ratio = r2.cached_tokens / r2.input_tokens
        print(f"\n[PASS] context caching works ({ratio:.1%} of input came from cache)")
    else:
        print("\n[INFO] cached_tokens=0 on call 2.")
        print("       Try qwen-plus or qwen-max if you used qwen-turbo.")
        print("       Caching matters less for learning — feel free to skip.")


if __name__ == "__main__":
    main()
