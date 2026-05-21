# ADR-0001: Pattern 02 Tool-use Loop as baseline architecture

**Status**: accepted (2026-05-18)

## Context

paper_qa 第一版要选一种 agent 模式。备选有 5 个 pattern：

1. **Pattern 01 Augmented LLM** — 单轮，模型回答 + 单次 tool call
2. **Pattern 02 Tool-use Loop** — 多轮，模型自决何时停
3. **Pattern 03 Routing** — 先分类再分发到专门 handler
4. **Pattern 04 Plan-then-Execute** — 先规划全部步骤再执行
5. **Pattern 05 Reflection** — 生成 → 评估 → 修改

我们的实际使用场景：
- 单 PDF 内问答（"这篇方法是什么"）
- 跨多篇查找（"哪几篇用了 NiFe"）
- 元数据查询（"有几篇"、"哪个最长"）
- 数据提取（"overpotential 多少 mV"）

约束：
- 5 篇起步，问题种类 < 10 个
- 必须支持<strong>条件分支</strong>（先 list 再决定 read 哪一篇）
- 学习项目，架构尽量简单可改

## Decision

选 **Pattern 02 Tool-use Loop**。

具体实现：
```python
while turn < MAX_TURNS:
    r = call(messages, tools=TOOLS)
    if r.finish_reason == "stop": return r.text
    execute_tools_and_append_to_messages(r.tool_uses, messages)
```

## Consequences

### 正面
- **代码简单**：50 行 agent loop 搞定，新人 10 分钟读完
- **灵活性强**：模型自己决定调几次工具、调哪个
- **支持条件分支**：tool A 返回结果后再决定要不要 tool B
- **架构可演进**：升级到 Pattern 03/04 时不用重写底层

### 负面
- **多轮成本高**：每轮都重新发送完整 messages（context 累积）
- **跨论文数字对比卡顿**：眼前的极限 case（`hard_oer_overpotential_compare` 9 个 tool call、122 秒）
- **不可预测的 tool 调用次数**：可能 2 次也可能 10 次，难做精确成本预算

### 中性
- 需要写 MAX_TURNS 安全阀（不写会死循环）
- 需要 instrumented_agent 包一层来捕获 cost/latency metrics

## 否决其他模式的理由

- **Pattern 01**：单 PDF QA 大多需要多轮（先看目录再读内容），单轮不够
- **Pattern 03**：5 篇起步问题种类少，Routing 的成本节省没体现，反而增加 router 错误率
- **Pattern 04**：杀鸡用牛刀，planner 错了反而比 Pattern 02 更难恢复
- **Pattern 05**：研究 QA 主要是事实查询，不是质量待优化的生成任务

## 未来升级路径

当遇到这些信号时升级：
- 跨 5+ 论文数字对比频繁 → 考虑 Pattern 04（让 planner 协调）
- 问题类型差异变大（如加入 "总结" 类） → 考虑 Pattern 03
- 答案质量在边界 case 不稳 → 加 Pattern 05 verify 一层

当前 Stage 2 的 hard_oer_overpotential_compare 已经在敲响这个警钟。
