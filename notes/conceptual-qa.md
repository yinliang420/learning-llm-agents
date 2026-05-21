# Agent 工程 — 概念问答记录

> 学习过程中的真实提问 + 解答。按"从底层到上层"顺序整理，建议按顺序阅读。

---

## 一、LLM 调用基础

### Q: Client 怎么初始化？messages 是什么结构？

```python
from openai import OpenAI
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 改 base_url 就能换后端，协议完全相同
)
# Client 建立后可复用，不需要每次新建
```

**messages 是一个列表，每条是一个字典，role 只有四种：**

| role | 谁写的 | 何时出现 |
|---|---|---|
| `system` | 你 | 对话开始，设定规则和角色 |
| `user` | 用户 | 每次用户提问 |
| `assistant` | 模型 | 模型的每次回复（含工具调用请求）|
| `tool` | 你的代码 | 工具执行结果 |

```python
messages = [
    {"role": "system",    "content": "你是材料科学助手..."},
    {"role": "user",      "content": "钢的密度是多少？"},
    # 后面动态追加 assistant 和 tool 消息
]
```

---

### Q: API 调用返回什么？finish_reason 是什么？

```python
response = client.chat.completions.create(
    model="qwen-plus", messages=messages, tools=tools, max_tokens=512
)

# 核心字段
response.choices[0].finish_reason        # 模型为什么停止
response.choices[0].message.content     # 文字回答（finish=stop 时）
response.choices[0].message.tool_calls  # 工具调用列表（finish=tool_calls 时）
```

**finish_reason 的三种值：**

| 值 | 含义 | 应对 |
|---|---|---|
| `"stop"` | 模型认为完成了，有文字回答 | 取 `message.content` 返回 |
| `"tool_calls"` | 模型需要调工具才能继续 | 执行工具，追加结果，再次调用 |
| `"length"` | 被 `max_tokens` 截断，不完整 | 增大 `max_tokens` 或分段 |

**关键**：`"stop"` 是模型的**主观判断**，不保证任务真的完成了。

---

## 二、Tool Use 底层机制

### Q: LLM 使用工具的完整 8 步流程

**① 初始化 Client**（见上）

**② 准备 messages**（系统规则 + 用户问题）

**③ 准备 tools schema（模型唯一能看到的东西）**
```python
tools = [{
    "type": "function",
    "function": {
        "name": "lookup",
        "description": "Use when user asks for a specific value. Never guess.",
        "parameters": {
            "type": "object",
            "properties": {
                "material": {"type": "string"},
                "property": {"type": "string", "enum": ["density", "hardness"]}
            },
            "required": ["material", "property"]
        }
    }
}]
```

**④ 发第一次请求**
```python
r1 = client.chat.completions.create(model=..., messages=messages, tools=tools)
```

**⑤ 解析响应**
```python
r1.choices[0].finish_reason           # "tool_calls" 说明需要调工具
r1.choices[0].message.tool_calls      # 工具调用列表
# tool_calls[i].id                    → 唯一 ID，如 "call_abc123"
# tool_calls[i].function.name         → 函数名
# tool_calls[i].function.arguments    → JSON 字符串（不是 dict！）
```

**⑥ 执行工具（本地 Python 运行，LLM 看不见）**
```python
for tc in r1.choices[0].message.tool_calls:
    args = json.loads(tc.function.arguments)  # 字符串 → dict
    result = lookup(**args)                    # 调你的 Python 函数
```

**⑦ 追加两条消息（顺序不能错）**
```python
# 第 1 条：模型的 tool_call 请求原样保存（API 用 id 做匹配）
messages.append({
    "role": "assistant", "content": None,
    "tool_calls": [tc.model_dump() for tc in r1.choices[0].message.tool_calls]
})
# 第 2 条：工具结果
messages.append({
    "role": "tool",
    "tool_call_id": tc.id,        # 必须和上面的 id 对应
    "content": json.dumps(result)  # 结构化 JSON，不是自然语言
})
```

**⑧ 发第二次请求**
```python
r2 = client.chat.completions.create(model=..., messages=messages)
print(r2.choices[0].message.content)  # 最终回答
```

---

### Q: 为什么 parameters 永远是 `"type": "object"`？

因为参数必须是**具名参数**，不能是位置参数：

```python
lookup("steel", "density")              # ❌ 谁是谁？模型不知道
lookup(material="steel", property="density")  # ✅ 清晰
```

`object` 对应 key-value 结构，即使只有一个参数也必须包一层：
```python
# ❌ 不合法
"parameters": {"type": "string"}

# ✅ 正确
"parameters": {"type": "object", "properties": {"expr": {"type": "string"}}, "required": ["expr"]}
```

---

### Q: 为什么工具结果不能塞进 assistant 消息，非要单独一条 tool 消息？

**① 时序上做不到**：assistant 消息是模型输出的，只有"我想调什么"。结果在你执行工具之后才存在，物理上无法提前放进去。

**② API 协议角色分离**：
- `assistant` = 模型说的（云端 LLM）
- `tool` = 你的代码返回的（本地 Python）

API 会校验这个结构，合并会报格式错误。

---

### Q: 并行调用多个工具时，messages 结构是怎样的？

N 个并行工具调用 → **1 条 assistant**（tool_calls 列表有 N 项）+ **N 条 tool**：

```python
# 1 条 assistant
{"role": "assistant", "content": None, "tool_calls": [
    {"id": "call_001", "function": {"name": "lookup", "arguments": '{"material":"SiC","property":"density"}'}},
    {"id": "call_002", "function": {"name": "lookup", "arguments": '{"material":"steel","property":"density"}'}},
]},

# N 条 tool（每条对应一个 id）
{"role": "tool", "tool_call_id": "call_001", "content": '{"value":3210}'},
{"role": "tool", "tool_call_id": "call_002", "content": '{"value":7850}'},
```

**注意**：N 条 tool 结果必须全部追加完，才能发下一次请求。

---

### Q: 模型会自动并行调用多个工具吗？

**会**——只要问题需要多个数据点，模型会在一轮里同时发出多个 tool_call，不需要代码指示：

```
Q: SiC 和铝，谁更硬？
→ lookup(SiC, hardness)        ← 同时发出，无需指示
→ lookup(aluminium, hardness)  ← 同时发出
```

你的代码需要正确处理 `tool_uses` 列表里的多个元素。

---

## 三、多轮对话与 Context 管理

### Q: 多轮对话中 messages 会一直增长吗？怎么控制？

**是**。每次 API 调用都发完整的 messages 历史，用户每追问一次就追加若干条：

```
第 1 轮：5 条   ~300 tokens
第 5 轮：25 条  ~1500 tokens
第 20 轮        → 轻松超过 context 限制
```

**生产环境的三层防御体系**：

```
Layer 3 [外层]：MAX_TURNS / 成本 / 时间上限 — 防止 loop 无限跑
Layer 2 [中层]：滑动窗口 / 摘要         — 控制 messages 总长度
Layer 1 [内层]：工具结果压缩 / State 外置 — 控制单条消息大小
```

三层缺一不可，详细方法见后续问题。

---

### Q: Layer 1 — 工具结果压缩有哪些具体技术？

**四种技术，可叠加使用：**

**技术 ① 字段过滤**：工具函数返回时只保留必需字段
```python
# ❌ 把数据库行原样返回（30+ 字段，~2KB tokens）
return db.query("SELECT * FROM materials WHERE name=?", name)

# ✅ 只返回 agent 需要的字段（~30 tokens）
return {"material": row["name"], "value": row[property], "unit": UNIT_MAP[property]}
```

**技术 ② 长文本截断 + 元信息**：长文本必须截断，告诉模型还有多少没看到
```python
def smart_truncate(text: str, max_chars: int = 2000) -> dict:
    if len(text) <= max_chars:
        return {"content": text, "truncated": False}
    return {
        "content": text[:max_chars],
        "truncated": True,
        "total_chars": len(text),
        "hint": "Call again with offset=2000 if more context needed"
    }
```

**技术 ③ State 外置**（最重要）：完整结果存 Python dict，messages 里只放引用
```python
class AgentState:
    def __init__(self):
        self.store, self.counter = {}, 0
    def save(self, result):
        self.counter += 1
        ref = f"result_{self.counter:03d}"
        self.store[ref] = result
        return ref

state = AgentState()
for tu in r.tool_uses:
    full = execute_tool(tu)
    ref = state.save(full)              # 完整数据存 state
    compact = {"_ref": ref, "summary": full.get("title", "")[:80]}
    messages.append({"role": "tool", "tool_call_id": tu["id"],
                     "content": json.dumps(compact)})  # messages 里只放精简版
```

**技术 ④ 批量工具**：让一个工具一次处理多个输入，减少 tool_call 数量
```python
# 与其让模型并行调 5 次 lookup，不如设计一个 batch 工具
{
    "name": "lookup_batch",
    "parameters": {"materials": {"type": "array"}, "property": {"type": "string"}}
}
# 模型一次调用 → 一个结果 → 1 对 messages，而非 5+1=6 条
```

---

### Q: 技术 ② 截断和技术 ③ State 外置都是让模型自己判断要不要更多信息吗？

**两者本质不同。**

| | 技术 ② 截断 | 技术 ③ State 外置 |
|---|---|---|
| 信息够不够谁判断 | **模型**（看 hint 自主决定）| **你的代码**（确定性逻辑）|
| 完整数据何时进 messages | 模型再次调工具时 | 你代码主动注入时（通常最后一步）|
| 适合场景 | 探索性任务（模型自主决定深度）| 结构化任务（你知道何时需要数据）|
| 模型 context 节省 | 中等 | 极高 |

**截断（技术 ②）**：模型看到 `truncated: True` 和 hint，可能再次调工具拿后续。判断权在模型。

**State 外置（技术 ③）**：模型只看到 `_ref` 标识符，不会因此再调工具——它根本不知道有"取详情"这件事。判断权在你的代码，通常在 synthesizer 阶段主动从 state 取数据注入。

---

### Q: State 外置的真正优势是什么？数据搬到 Synthesizer 不也是 messages 变长了？

**核心洞察**：loop 里的消息是被**重复发送**的，不是只发一次。每次 API 调用都把完整 messages 历史发给模型。

具体例子：loop 跑 10 轮，每轮调一个工具，每个结果 500 tokens。

**不用 State 外置**（结果留在 messages 里）：

| Turn | 这次调用发送的 tokens |
|---|---|
| 1 | 500 (result_1) |
| 2 | 1000 (result_1 + result_2) |
| 3 | 1500 |
| ... | ... |
| 10 | 5000 |

**全程发送总量** = 500 + 1000 + ... + 5000 = **27,500 tokens**  
（result_1 被发送了 10 次，result_2 发送 9 次……）

**用 State 外置**（messages 只放引用 ~20 tokens）：

| Turn | 这次调用发送的 tokens |
|---|---|
| 1-10 | 线性增长（每次只多 ~20 tokens 引用）|
| Synthesizer | 5500（一次性塞所有数据）|

**全程发送总量** ≈ **9,000 tokens**，省了约 70%。

关键不在"数据搬家"，而在"避免数据在 loop 里反复发送"。

**额外好处**：
- 模型 loop 阶段决策更清晰（不被旧数据干扰）
- 可以为 loop 和 synthesizer 选不同模型（loop 用便宜的，synthesizer 用强的）
- Prompt caching 命中率更高（messages 前缀稳定）

---

### Q: State 里到底存什么？是用户问题和答案的配对吗？

**不是。State 存的是工具执行的原始结果**，不是 Q&A 配对。

```python
state.store = {
    "result_001": {                        # ← 工具的完整原始结果
        "found": True,
        "material": "SiC", "property": "density",
        "value": 3210, "unit": "kg/m³",
        "source_db": "materials_v2",        # 元数据
        "last_updated": "2026-01-15",
        "confidence": 0.98
    },
    "result_002": {...},
    ...
}
# 用户的原始问题不在 state 里，它在 messages 里
# 模型说过的话也不在 state 里
```

**分工**：

| messages 里有 | state 里有 |
|---|---|
| system prompt | 工具结果的完整 raw data |
| user 原始问题 | （含元数据、source、confidence 等）|
| assistant 推理 | |
| 工具结果**精简版**（refs + summary）| |

State 的本质：把"占空间但 loop 阶段用不上"的大块数据抽出来，等真正需要时（synthesizer 阶段）再一次性注入。

---

### Q: 技术 ④ 批量合并真的省 token 吗？

**朴素的"合并 hack"省得有限**，因为 API 协议要求每个 tool_call_id 都必须有对应的 tool 消息：

```python
# 5 个并行工具调用 → 必须有 5 条 tool 消息（即使内容合并到一条）
{"role": "tool", "tool_call_id": "001", "content": json.dumps(combined)},
{"role": "tool", "tool_call_id": "002", "content": '{"see":"001"}'},  # 占位
{"role": "tool", "tool_call_id": "003", "content": '{"see":"001"}'},
{"role": "tool", "tool_call_id": "004", "content": '{"see":"001"}'},
{"role": "tool", "tool_call_id": "005", "content": '{"see":"001"}'},
```

只省了内容重复，没省结构开销（约 50%）。

**真正的解法是在 schema 层设计 batch 工具**：

```python
{
    "name": "lookup_batch",
    "description": "Look up the same property for multiple materials at once.",
    "parameters": {
        "type": "object",
        "properties": {
            "materials": {"type": "array", "items": {"type": "string"}},
            "property": {"type": "string", "enum": [...]}
        },
        "required": ["materials", "property"]
    }
}
# 模型一次调用 → 1 个 tool_call_id → 1 条 tool 消息
# messages 从 6 条减到 2 条，token 省 70%+
```

经验法则：如果一个工具被反复调用查不同 key 的同一种数据，做成 batch 版本比任何后处理 hack 都管用。

---

### Q: Layer 2 — 滑动窗口为什么必须按 tool-call 配对为单位？

API 协议硬约束：**每个 tool_call_id 必须有对应的 tool 消息**，不能只删一个：

```python
# ❌ 错误：粗暴按 token 删
def naive_truncate(messages, max_tokens):
    while count_tokens(messages) > max_tokens:
        messages.pop(0)  # 可能删 assistant 留下孤立的 tool
    return messages
# → 下次 API 调用：报错 "tool_call_id not found"
```

**正确做法**：识别 tool-call 对（assistant + 它的 N 条 tool 结果），整对删除：

```
索引  内容
─────────────────────────────────────────────
 0    system                              ← 永远保留
 1    user "钢的密度？"                     ← 永远保留（最初问题）
 2    assistant {tool_calls: [A]}         ┐
 3    tool A_result                       ┘ 配对单位 1
 4    assistant "钢密度 7850"
 5    user "再查铜"
 6    assistant {tool_calls: [B]}         ┐
 7    tool B_result                       ┘ 配对单位 2
 8    assistant "铜密度 8960"
 9    user "对比 SiC、铝、钛"
10    assistant {tool_calls: [C, D, E]}   ┐
11-13 tool C/D/E_result                   ┘ 配对单位 3
14    assistant "对比结果..."
```

滑动窗口触发后（保留最近 2 对配对单位）：
- 保留 0, 1（永远）
- 删除 2-5（配对单位 1 + 中间文本）
- 保留 6-14（配对单位 2、3 + 文本）

注意：**不是按 session 切，不是周期性摘要**，就是同 session 内按配对单位从前往后删。

---

### Q: Layer 3 — MAX_TURNS 为什么要组合多个上限？

单纯计数 turns 不够用，每种指标都有自己的盲区：

| 指标 | 能挡住什么 | 挡不住什么 |
|---|---|---|
| **turns**（轮数）| 模型死循环、反复重试 | 单轮里调 50 个工具的爆炸 |
| **cost**（累积美元）| 整体烧钱失控 | cost 低但卡住的死锁 |
| **time**（累积时间）| 外部工具慢、网络卡 | 快速但无意义的循环 |
| **tool_calls**（工具调用总数）| 工具调用爆炸 | 单纯模型推理但不调工具 |

**真实失败案例对应**：

```
案例 A：模型 turn 3 进入死循环，反复调同一个工具 → max_turns 兜住
案例 B：模型 turn 1 同时调了 80 个并行工具       → max_tool_calls 兜住
案例 C：模型连续输出超长答案，cost 累计 $0.30    → max_cost 兜住
案例 D：工具调了挂掉的外部 API，超时 30 秒/次    → max_duration 兜住
```

**生产配置示例（按任务类型分级）**：

```python
@dataclass
class LoopLimits:
    max_turns: int = 15
    max_cost_usd: float = 0.10
    max_duration_sec: int = 60
    max_tool_calls: int = 30

LIMITS_SIMPLE   = LoopLimits(max_turns=3,  max_cost_usd=0.01, max_duration_sec=10,  max_tool_calls=5)
LIMITS_DEFAULT  = LoopLimits(max_turns=15, max_cost_usd=0.10, max_duration_sec=60,  max_tool_calls=30)
LIMITS_RESEARCH = LoopLimits(max_turns=50, max_cost_usd=2.00, max_duration_sec=600, max_tool_calls=200)
```

**任何上限被触发都必须告警**，不能静默 return——说明出了非预期情况。

---

### Q: 对话历史也能像 tool 结果一样外置吗？

**完全可以**。这是 State 外置思路的自然延伸，也是 **Agent Memory 系统的核心**。

把"State 外置"从 tool 结果扩展到整个对话历史：

```python
# 历史全部存到 Python state / DB
conversation_state = {
    "turn_1": {"user": "钢的密度？", "asst": "7850", "tools_used": [...]},
    "turn_2": {"user": "对比 SiC", "asst": "...", "tools_used": [...]},
    ...
}

# 当前 API 调用只塞最相关的部分
messages = [
    system,
    {"role": "system", "content": injected_relevant_history},  # 按需注入
    user_N
]
```

**生产里三种实现**：

**① 滑动窗口 + 摘要**（最常用）：最近 N 轮完整保留，更早的折叠成摘要塞进 system 消息

**② 语义检索（RAG-like）**：历史全部存向量库，根据当前问题检索最相关的几条注入。适合长 session（几百轮以上）

**③ 分层记忆**（ChatGPT / Claude 这种长期助手用的）：
```
第 1 层 短期：最近 5 轮完整保留
第 2 层 中期：5-50 轮的摘要
第 3 层 长期：超过 50 轮归档到向量库，按需检索
```

**信息丢失的代价**——这是不能无脑外置的根本原因：

```
Turn 1: 用户："我做的是航空结构件"      ← 重要的隐含上下文！
Turn 2: 用户："推荐一种轻量材料"
...
Turn 15: 用户："那个钛的比强度怎么样？"

激进滑动窗口删掉了 Turn 1 → 模型不知道航空场景 → 推荐错误材料
```

**取舍建议**：

| 场景 | 推荐方案 |
|---|---|
| 短任务（<10 轮）| 全保留 |
| 中等会话（10-50 轮）| 滑动窗口 + 摘要 |
| 长期助手（持续几天/月）| 分层记忆 + 语义检索 |
| 多用户跨 session | 必须外置到 DB，按 user_id 索引 |

**关键决策点**：外置之后，难点变成"**如何决定哪些历史值得 inject 回来**"。这是 Agent Memory 工程的核心，也是 Phase 3 要深入的内容。

---

## 四、Tool 设计原则

### Q: LLM 在训练时学习了一些工具吗？推理时能用吗？

**训练教的是"如何用工具"，不是"有哪些具体工具"。**

| 训练教会的 | 训练没教的 |
|---|---|
| 工具调用的格式（如何输出合法 JSON）| 你的 `lookup` 函数存不存在 |
| 工具调用的时机（什么时候该调）| 你的工具有什么参数 |
| 工具结果的理解（拿到结果后怎么推理）| 什么时候该用你这个具体工具 |

**模型在推理时是第一次看到你定义的任何工具**，完全靠你写的 `description` 理解用途。

---

### Q: 什么时候应该把一个函数设计成工具？

三个问题依次判断：

1. **模型自己能可靠回答吗？** 能（公开知识、稳定常识）→ 不需要工具
2. **执行有副作用吗？**（写文件、改数据库）→ 必须做成工具
3. **信息量少且静态，放 system prompt 够吗？** 够 → 放 system prompt；数据量大或动态 → 做成工具

**常见错误**：
- 太细：`get_density(material)` + `get_hardness(material)` 分两个工具 → 合并成 `lookup(material, property)`
- 太粗：`get_all_info(material)` 返回所有属性 → 大量无关 token
- 把模型已知的通用知识做成工具 → 浪费

---

### Q: 如何提升工具调用准确率？

**6 条规则：**

**① description 写 WHEN，不写 HOW**
```python
# ❌ 只写了 HOW
"description": "Gets material data by name and property"

# ✅ 写了 WHEN（模型知道何时用、何时不用）
"description": "Use ONLY when user asks for a specific numeric value. NOT for general concepts."
```

**② 有限枚举值必须用 enum**
```python
# ❌ 模型会发明 "tensile strength"
"property": {"type": "string"}

# ✅ 只能选合法值
"property": {"type": "string", "enum": ["Young's modulus", "density", "melting point", "hardness"]}
```

**③ 工具返回结构化 JSON，不返回自然语言**
```python
# ❌ 模型提取不稳定
return f"The density of {material} is {value} kg/m³"

# ✅ 可靠提取
return {"found": True, "value": 7850, "unit": "kg/m³"}
```

**④ 错误信息要可操作**
```python
# ❌ 模型不知道怎么处理
return {"error": "not found"}

# ✅ 告诉模型下一步能做什么
return {"found": False, "error": "'钨' not in DB", "available": list(DB)}
```

**⑤ System prompt 强制约束**
```python
SYSTEM = "Always use lookup tool for property values — never recall from memory."
```

**⑥ 工具粒度适中**：一次调用满足一个信息需求，不太细也不太粗。

---

## 五、Agent 设计模式

### Q: Tool use 本质上就是 Augmented LLM 吗？

**不是，两者是不同层次。**

- **Tool use**：API 机制，模型能输出结构化函数调用 JSON
- **Augmented LLM**：设计模式，用 tool use 增强单次调用能力

Tool use 是所有 agent 模式的底层原语；Augmented LLM 只是其中最简单的应用。

---

### Q: Function Calling 和 Tool Use 有什么区别？

**不是同义词，Function Calling ⊂ Tool Use。**

| | Function Calling | Tool Use |
|---|---|---|
| 粒度 | 原子，单步 | 任意复杂的黑盒 |
| 背后是什么 | 一个具体 Python 函数 | 函数 / subagent / workflow / 人 |
| 执行时间 | 毫秒级 | 秒到小时 |
| 确定性 | 期望确定性 | 可以非确定性 |

从接口层看两者一模一样（JSON in，result out），区别在于语义契约——背后的东西有多重。

---

### Q: Tool Use vs Skills vs MCP 的区别？

```
MCP（协议层）
└── 标准化工具如何暴露和被发现（跨应用复用）
    额外还有 Resources（可读数据）和 Prompts（提示词模板）

Tool Use / Function Calling（机制层）
└── LLM 推理时如何发起一次工具调用

Skills（概念层）
├── Claude Code 里：Markdown 指令文件，影响模型行为，不产生 API 调用
└── Agent 工程通用：Tool + 多步骤 + 记忆 = 复合能力（Tool 是锤子，Skill 是装家具全流程）
```

---

### Q: ReAct（Tool-use Loop）和 Plan-Execute 的区别？

**大方向：决策时机不同。**

| 维度 | ReAct | Plan-Execute |
|---|---|---|
| 决策方式 | 每轮根据最新结果实时决定下一步 | 开始前一次性生成完整计划 |
| 自适应 | ✅ 步骤失败可调整 | ❌ 计划固定（需 Replanner）|
| 并行执行 | 轮内可以，轮间串行 | ✅ 独立步骤可全部并行 |
| Context 增长 | 随轮次线性增长 | 执行阶段不调 LLM，不增长 |
| 透明度 | 计划不可见，边跑边定 | 计划可视化，可人工审查 |
| 适合任务 | 探索性、步骤不确定 | 结构清晰、步骤可枚举 |

**小细节差异：**

- **LLM 调用次数**：ReAct N 次（N 轮）；Plan-Execute 2 次（Planner + Synthesizer），执行阶段零 LLM
- **错误处理**：ReAct 看到错误可立即调整；Plan-Execute 错误会级联（我们的"钢/钛"命名案例）
- **messages 结构**：ReAct 是一个持续增长的数组；Plan-Execute 是三个独立的短数组

---

### Q: Plan-Execute 的 messages 是同一个 session 还是独立的？

**三个独立的 LLM 调用，各有自己的 messages，互相不知道对方内容。**

```python
# Planner：只需要知道目标
messages_1 = [{"role": "system", "content": "你是规划器..."}, {"role": "user", "content": "目标..."}]
plan = call(messages_1)

# Executor：纯 Python，不调 LLM，results 存在 Python dict 里
results = {}
for step in plan:
    results[step["id"]] = lookup(step["material"], step["property"])

# Synthesizer：只需要知道目标 + 结果
messages_3 = [{"role": "system", "content": "只用提供的数据..."}, {"role": "user", "content": f"目标...\n数据：{results}"}]
answer = call(messages_3)
```

**状态靠 Python 变量传递，不靠 messages**：`plan`（Python list）和 `results`（Python dict）是三个调用之间的桥梁。

LLM 本身是无状态的，"上下文"永远是你的代码把信息注入 messages 带过去的。

---

### Q: 那 Plan-Execute 里可以给每次 LLM 调用用不同的 system prompt 吗？

**完全可以，这正是 Plan-Execute 的优势之一。**

```python
plan    = call(messages, system="你是规划器，只输出 JSON", model="qwen-turbo")   # 便宜模型
# Executor 不调 LLM
answer  = call(messages, system="你是材料分析师，深度推理", model="qwen-max")    # 强模型
# 如果有 Pattern 05 的 Evaluator：
score   = call(messages, system="你是严苛审稿人，主动找问题", model="qwen-plus") # 对立角色
```

每次调用都是独立的 messages，没有历史包袱，换角色零代价。这是 Pattern 05（Reflection）里 Evaluator 必须和 Generator 用不同 prompt 的深层原因。

---

### Q: 为什么 ReAct 里不能随意改 system prompt？

**技术上可以改，但会产生语义矛盾。**

ReAct 的 messages 里有模型自己说过的历史（assistant 消息）。换了 system prompt 就和这些历史产生身份矛盾：

```
Turn 1 时 system = "你是探索者" → 模型以探索者身份回答，进入 messages
Turn 2 时 system = "你是总结者" → 模型读到 Turn 1 的"探索者"回答
                                 → 困惑：我到底是谁？上一条是我说的吗？
```

Plan-Execute 没这个问题，因为每次都是全新干净的 messages，没有历史包袱。

---

### Q: Replanner 是怎么工作的？

**当步骤失败时，不是直接跳过，而是调 LLM 重新规划后续步骤：**

```python
def execute_with_replanning(goal, plan, max_replan=2):
    results = {}
    replan_count = 0
    i = 0

    while i < len(plan):
        result = lookup(plan[i]["material"], plan[i]["property"])

        if result.get("found"):           # 成功，继续下一步
            results[plan[i]["id"]] = result
            i += 1
        elif replan_count >= max_replan:  # 超限，跳过
            results[plan[i]["id"]] = {"skipped": True}
            i += 1
        else:                             # 失败，重新规划
            new_remaining = call([{"role": "user", "content": f"""
                Goal: {goal}
                Completed: {json.dumps(results)}
                Failed step: {json.dumps(plan[i])}
                Error: {result['error']}
                Generate revised remaining steps as JSON array.
            """}], system=PLANNER_SYSTEM)

            plan = plan[:i] + json.loads(new_remaining.text)
            replan_count += 1
            # 不递增 i，从 Replanner 生成的第一步继续

    return results
```

**Replanner 是一个独立的 LLM 调用**，messages 里包含：已完成的结果、失败的步骤、失败原因。它输出修正后的后续步骤列表，不改动已完成的步骤。

---

### Q: Routing 是不是必须提前把所有情况都列好？遇到没列到的情况怎么办？

**是，Routing 的本质是封闭世界假设**——你定义了哪些类别，它就只能选那些。没列到的情况会被误分类。

**三种应对方式：**

**① 兜底 handler 带全部工具**（推荐）
```python
HANDLERS = {
    "lookup":  handle_lookup,   # 只有 lookup 工具
    "compute": handle_compute,  # 只有 calculate 工具
    "general": handle_general,  # 无工具
    "default": handle_default,  # 所有工具都有 ← 兜底
}

def route(question):
    label = call_router(question)
    if label not in HANDLERS:
        return "default"        # 路由失败 → 兜底
    return label
```

**② handler 之间工具重叠**：lookup handler 也带 calculate，避免混合型问题失败。

**③ 直接不用 Routing**：如果混合型多、边界模糊，路由的代价（额外调用 + 误分类）超过收益，直接用 Pattern 02 给模型全部工具。

**判断要不要加 Routing**：
- 问题类型清晰、各类别工具差异大 → 加，成本降 40-60%
- 混合型多、类别边界模糊 → 别加

---

### Q: 早停（early stop）的生产解决方案是什么？

**三种方法，生产环境组合使用：**

**① System Prompt 约束**（概率性）
```python
SYSTEM = "Check ALL materials before concluding. Only stop after verifying every item."
```

**② 显式 done 工具**（中等可靠）
```python
# 模型必须主动调这个工具才能结束，不能靠 finish_reason="stop"
DONE_TOOL = {"type": "function", "function": {
    "name": "task_complete",
    "description": "Call ONLY when ALL items are verified.",
    "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}
}}
# loop 里检测
for tu in r.tool_uses:
    if tu["name"] == "task_complete":
        return tu["input"]["summary"]
```

**③ 代码层验证**（最可靠，生产首选）
```python
if r.finish_reason == "stop":
    ok, reason = validate(results, required_materials)  # 代码自己验证完整性
    if ok:
        return r.text
    else:
        messages.append({"role": "user", "content": reason})
        continue  # 顶回去继续
```

**生产标准组合**：
```
System Prompt（降低早停概率）
    + 代码层验证（兜底，完成条件可编程的任务）
    + MAX_TURNS（防死循环）
```

对于完成条件主观的任务（如"生成完整报告"），改用**显式 done 工具 + MAX_TURNS**。

---

## 六、工程建议

### Q: 先学框架（LangGraph）还是先写裸 SDK？

**强烈建议先写裸 SDK。**

框架是 2-3 天能学会的东西，但如果你不知道框架背后在发生什么，问题出现时会完全没有方向。

顺序：① 手动拼 messages，摸清 function calling 机制 → ② 跑 5 个不同模式的 agent（50-200 行）→ ③ 有"又写了一遍 boilerplate"的痛感后，再上框架。

---

### Q: Round 1 的 token 为什么比 Round 2 多？

**Round 1 包含模型推理"调哪些工具"的思考链。**

用 reasoning model（如 qwen3.6-plus）时，Round 1 要推断工具选择，output tokens 多；Round 2 已有数据，直接整合作答，output tokens 少。

工具列表越长，Round 1 的推理成本越高——这是 Routing 的价值之一：先分类减少无关工具噪音，降低 Round 1 成本。

---

### Q: Multi-Agent 应该什么时候学？

**单 Agent 的 memory 管理和错误处理完全搞清楚之后。**

单 Agent 没吃透就上 Multi-Agent，状态同步、消息传递格式、循环依赖、部分失败处理——每个都会成倍放大复杂度。

---

*持续更新 — 每次学习会话后补充新问题*
