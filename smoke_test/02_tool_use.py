"""Smoke test 2: tool use.

Verifies the endpoint actually supports OpenAI-style tool calling.
Some smaller / older models may not — if this fails, switch to a stronger
model in .env (e.g. qwen-plus or qwen-max).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.llm import call

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a given city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name in English, e.g. 'Tokyo' or 'Beijing'.",
                },
            },
            "required": ["city"],
        },
    },
}


def main() -> None:
    r = call(
        [{"role": "user", "content": "What's the weather in Tokyo right now?"}],
        tools=[WEATHER_TOOL],
    )
    print("--- response text ---")
    print(r.text or "(none)")
    print("--- tool calls ---")
    for t in r.tool_uses:
        print(f"  {t['name']}({t['input']})")
    print("--- usage ---")
    print(r.summary())

    assert r.tool_uses, "model did not call any tool — try a stronger model (qwen-plus / qwen-max)"
    assert r.tool_uses[0]["name"] == "get_weather"
    assert "city" in r.tool_uses[0]["input"]
    print("\n[PASS] tool use works")


if __name__ == "__main__":
    main()
