"""把任何 Pattern 02 风格的 agent 包装成可被 run_eval 调用的 instrumented agent。

目的：消除 3 处 run_eval.py 里重复的 instrumented_agent 代码。每个 run_eval.py
现在只需要描述自己的工具配置，loop 逻辑/metric 捕获/exception 处理都在这里。

设计原则：
  - 用 dataclass 把"agent 长什么样"参数化（system、tools、dispatch、limits）
  - 返回一个 callable，签名 (question: str) → AgentResponse
  - 支持 Pattern 01 行为（drop_tools_in_final_round=True）和 Pattern 02 行为

用法：
    from shared.eval import build_instrumented_agent, AgentConfig

    config = AgentConfig(
        system=SYSTEM_PROMPT,
        tools=TOOL_SCHEMAS,
        dispatch={"foo": foo_fn, "bar": bar_fn},
        max_turns=10,
    )
    instrumented = build_instrumented_agent(config)
    response = instrumented("用户问题")
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable

from shared.llm import call

from .types import AgentResponse


@dataclass
class AgentConfig:
    """描述一个被 instrument 的 agent 的所有配置。"""
    system: str
    tools: list[dict]
    dispatch: dict[str, Callable]
    max_turns: int = 10
    max_tokens: int = 1024
    model: str | None = None         # None = 用 shared/llm.py 的默认
    drop_tools_in_final_round: bool = False   # Pattern 01：最后一轮不带 tools，强制收尾


def build_instrumented_agent(config: AgentConfig) -> Callable[[str], AgentResponse]:
    """根据 config 返回一个 (question) → AgentResponse 函数。"""

    def instrumented(question: str) -> AgentResponse:
        messages: list[dict] = [{"role": "user", "content": question}]
        start = time.time()
        tool_calls_made: list[dict] = []
        total_cost = 0.0
        turns = 0
        final_finish = ""
        final_text = ""

        while turns < config.max_turns:
            turns += 1

            # 最后一轮（且 Pattern 01 行为开关打开）→ 不带 tools，强制收尾
            is_final_round = (turns == config.max_turns)
            use_tools = not (config.drop_tools_in_final_round and is_final_round)

            kwargs: dict = {
                "system": config.system,
                "max_tokens": config.max_tokens,
            }
            if use_tools:
                kwargs["tools"] = config.tools
            if config.model:
                kwargs["model"] = config.model

            r = call(messages, **kwargs)
            total_cost += r.cost_usd
            final_finish = r.finish_reason

            # 模型给出最终答案
            if r.finish_reason == "stop":
                final_text = r.text
                break

            # 工具调用
            if r.finish_reason == "tool_calls":
                for tu in r.tool_uses:
                    tool_calls_made.append({"name": tu["name"], "args": tu["input"]})

                # 把 assistant tool_calls 消息加进 messages
                raw = r.raw.choices[0].message
                messages.append({
                    "role": "assistant",
                    "content": raw.content,
                    "tool_calls": [tc.model_dump() for tc in (raw.tool_calls or [])],
                })

                # 执行每个工具并 append 结果
                for tu in r.tool_uses:
                    name = tu["name"]
                    if name not in config.dispatch:
                        result = {"error": f"Unknown tool: {name}"}
                    else:
                        try:
                            result = config.dispatch[name](**tu["input"])
                        except Exception as e:
                            result = {"error": f"{type(e).__name__}: {e}"}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tu["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                continue

            # 非预期的 finish_reason（length / content_filter / 其他）
            final_text = f"[unexpected finish_reason: {r.finish_reason}] {r.text}"
            break
        else:
            # while 走完没 break = MAX_TURNS 到了
            final_text = "[MAX_TURNS reached]"

        return AgentResponse(
            text=final_text,
            tool_calls=tool_calls_made,
            cost_usd=total_cost,
            duration_ms=int((time.time() - start) * 1000),
            turns=turns,
            finish_reason=final_finish,
        )

    return instrumented
