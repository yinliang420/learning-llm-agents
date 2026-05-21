# Architecture Decision Records

ADR 记录项目里的**重要决策**：为什么这么选、当时有哪些备选、否决备选的理由。

3 个月后你回来改代码，看 git log 只能看到"做了什么"，看 ADR 才能看到"为什么这么做"——避免重复犯同样的错。

## 什么决策值得写 ADR

✅ 写：
- 选了某个库 / 框架（reject 了其他备选）
- 选了某个架构 pattern（reject 了其他 pattern）
- 选了某个数据格式 / 算法（reject 了其他）
- 划了某个 scope 边界（明确不做什么）

❌ 不写：
- 修一个 bug
- 加一个 feature
- 重命名变量
- 普通 refactor

## 格式约定

文件名：`NNNN-short-decision-title.md`（4 位数字 + 短英文标题 + .md）

每份 ADR 包含 4 段：
1. **Status**：proposed / accepted / superseded by NNNN
2. **Context**：当时面临什么问题、有哪些约束
3. **Decision**：我们选了什么，明确具体
4. **Consequences**：选了之后的后果（好的 + 坏的 + 中性的）

## 当前 ADR 列表

| # | 标题 | 状态 |
|---|---|---|
| 0001 | Pattern 02 Tool-use Loop as baseline architecture | accepted |
| 0002 | chromadb as local vector DB | accepted |
| 0003 | sentence-transformers/all-MiniLM-L6-v2 as embedding model | accepted |
| 0004 | Sample 5 papers before scaling to full 1823 | accepted |
| 0005 | Chunk strategy: 800 chars + 200 overlap, page-aware | accepted |
