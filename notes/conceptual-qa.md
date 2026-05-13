# Agent 工程 — 概念问答记录

> 学习过程中的真实提问 + 解答。这些问题往往是刚入门时最容易搞混的地方。

---

## Tool Use & Function Calling

### Q: Tool use 本质上就是 Augmented LLM 吗？它是增强模型回答能力的机制？

**不完全是。两者是不同层次的概念。**

- **Tool use** 是 API 层面的*机制*:模型能输出结构化的函数调用 JSON
- **Augmented LLM** 是一种*设计模式*:用 tool use(加上检索、缓存等)来增强**单次**调用的能力

后面的 tool-use loop、routing、plan-execute 也都用 tool use，所以 tool use 不等于 augmented LLM。Tool use 是所有 agent 模式的底层原语，augmented LLM 只是其中最简单的应用方式。

---

### Q: LLM 在 RL 训练过程中学习了一些"工具"，这些工具是模型训练时就固定的吗？

**训练教的是"如何用工具"，不是"有哪些具体工具"。**

| 训练(RL/RLHF)教会模型的 | 训练*没有*教的 |
|---|---|
| 工具调用的**格式** — 怎么输出合法的 function call JSON | 你的 `get_material_property` 工具存不存在 |
| 工具调用的**时机** — 什么时候该调工具 | 你的工具有什么参数 |
| 工具结果的**理解** — 拿到 result 后怎么推理 | 什么时候该用你这个具体工具 |

**模型在推理时是"第一次看到"你定义的任何工具**。它完全靠你写的 `description` 来理解这个工具的用途。

类比：RL 训练教会人类"如何看说明书"，你写的 schema 是你现场给他一本新工具的说明书。

这就是为什么 description 写得差，模型会传错参数——不是模型不聪明，是说明书写得不好。

---

### Q: Tool use 完整的消息交换流程是什么？Schema 怎么写？

**流程（4 步）：**

```
你                          模型
── messages + tools ──►
                      ◄── "call get_weather(Tokyo)"
── tool_result("22°C") ──►
                      ◄── "Tokyo 现在 22°C，晴天"
```

**Schema 解剖（OpenAI 格式，DashScope 兼容）：**

```python
{
    "type": "function",
    "function": {
        "name": "lookup_material_property",

        # 最重要的字段：告诉模型"什么时候用这个工具"
        # 不要写 HOW，要写 WHEN
        "description": "查询材料的物理/力学属性。当用户需要具体的材料参数时使用。",

        "parameters": {
            "type": "object",
            "properties": {
                "material": {
                    "type": "string",
                    "description": "材料名称，如 'steel', 'aluminium', 'SiC'",
                },
                "property": {
                    "type": "string",
                    "description": "属性名称",
                    "enum": ["Young's modulus", "density", "melting point", "hardness"]
                    # 有限枚举值必须列出来——不要让模型自由发挥
                },
            },
            "required": ["material", "property"]
        }
    }
}
```

**工程上的责任划分：**

| 问题 | 谁来定义 |
|---|---|
| 模型知不知道"工具调用"是什么 | 模型（训练决定） |
| 模型用不用这个工具 | 你写的 description |
| 模型传什么参数 | 你写的 parameters schema |
| 工具实际做什么 | 你写的 Python 函数 |

---

## 学习路径

### Q: 先学框架（LangGraph）还是先写裸 SDK？

**强烈建议先写裸 SDK。**

很多人急着上手框架，跳过底层机制，然后在各种莫名其妙的问题上卡死——因为他们不知道框架背后在发生什么。

建议的顺序：
1. **不用框架，直接调 SDK，手动拼 messages 数组** — 花一个下午，把 function calling 机制摸清楚
2. **跑 5 个不同模式的小 agent**（每个 50-200 行）— 建立"哪种问题用哪种结构"的肌肉记忆
3. **框架（LangGraph 等）是 2-3 天能学会的东西** — 等你有"又写了一遍这个 boilerplate"的痛感再上

---

### Q: Multi-Agent 应该什么时候学？

**单 Agent 做扎实之前，不要碰 Multi-Agent。**

如果你连单 Agent 的 memory 管理和错误处理都没搞清楚，上 Multi-Agent 只会让问题指数级复杂：两个 Agent 之间的状态同步、消息传递格式、循环依赖、部分失败的处理——这些在单 Agent 没吃透之前全是陷阱。

---

## 运行时观察

### Q: 为什么 Round 1 的 token 消耗远大于 Round 2？

**因为 Round 1 包含了"推理应该调哪些工具"的思考链。**

用 qwen3.6-plus（reasoning model）时：
- Round 1：模型在思考链里推断"需要哪几个工具、传什么参数" → 大量 output tokens
- Round 2：模型已经有了数据，直接整合成答案 → output tokens 少

实际数据（Pattern 01 运行）：

| 问题类型 | Round 1 out | Round 2 out |
|---|---|---|
| 单工具查询 | ~114 tokens | ~113 tokens |
| 双工具并行查询 | ~400-430 tokens | ~170 tokens |

**意义**：工具列表越长，Round 1 的推理成本越高。这是 Pattern 03（Routing）存在的原因之一——先分类再派发，减少无关工具的噪音。

---

### Q: 模型会自动并行调用多个工具吗？

**会——只要问题需要多个数据点，模型会在一次 Round 1 里同时发出多个 tool_call。**

实测（Pattern 01）：
```
Q: SiC 和铝，谁的硬度更高？
→ lookup_material_property({"material": "SiC",       "property": "hardness"})  ← 同时发出
→ lookup_material_property({"material": "aluminium", "property": "hardness"})  ← 同时发出
```

这不需要你显式指示，模型从 schema 推断出"两个数据点可以同时拿"。你的代码需要正确处理 `tool_uses` 列表里的多个元素。

---

*持续更新 — 每次学习会话后补充新问题*
