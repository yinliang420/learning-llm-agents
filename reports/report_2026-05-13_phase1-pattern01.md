# Report: Phase 1 Pattern 01 — Augmented LLM

**日期**: 2026-05-13
**作者**: Claude
**会话目的**: 实现并运行第一个 agent pattern:Augmented LLM。搞清楚 tool use 的完整消息流。

---

## 1. 实现的内容

### 文件
| 文件 | 内容 |
|---|---|
| `phase1_patterns/01_augmented_llm/tools.py` | Mock 材料属性数据库(5 种材料 × 4 个属性)+ 两个工具函数 |
| `phase1_patterns/01_augmented_llm/main.py` | 完整的 Augmented LLM agent:schema 定义、工具调度、两轮消息流 |

### 设计决策
- **两个工具**: `lookup_material_property`(有参)+ `list_materials`(无参)— 展示不同 schema 形态
- **property 字段用 enum 约束** — 阻止模型发明数据库里没有的属性名
- **工具结果返回 structured JSON** — 比自然语言字符串更稳定
- **verbose 模式** — 每步打印 finish_reason + token 用量,便于学习观察

---

## 2. 实际运行结果(4 个测试问题)

```
Q1: 钢的杨氏模量是多少？
  → lookup_material_property({material: "steel", property: "Young's modulus"})
  ← {found: true, value: 200, unit: "GPa"}
  A: 钢的杨氏模量约为 200 GPa。
  cost: $0.000140

Q2: SiC 和铝，谁的硬度更高？
  → [并行] lookup(SiC, hardness) + lookup(aluminium, hardness)
  ← SiC: 2500 HV, Al: 25 HB
  A: SiC 硬度更高(2500 HV vs 25 HB)
  cost: $0.000256

Q3: 你的数据库里有哪些材料可以查？
  → list_materials({})
  ← {materials: [steel, aluminium, SiC, copper, titanium], ...}
  A: 详细列出 5 种材料(中英文)
  cost: $0.000275

Q4: 帮我比较钛和铝的密度。
  → [并行] lookup(titanium, density) + lookup(aluminium, density)
  ← Ti: 4500 kg/m³, Al: 2700 kg/m³
  A: 钛比铝致密,约为铝的 1.67 倍
  cost: $0.000248
```

**所有 4 个问题全部 PASS**。

---

## 3. 这次运行学到的 3 件事

### ① 模型自动做并行工具调用

Q2 和 Q4 都需要查询两种材料。模型在 Round 1 **同时**发出两个 tool_call(不是先查 A 再查 B)。这是模型自主决定的,schema 里没有显式指示。

意义:设计好工具后,并行调用是免费得到的——只要问题需要两个数据点,模型会自己优化。Pattern 02(tool loop)里这更明显。

### ② Round 1 的 token 消耗远高于 Round 2

| 问题 | Round 1 out | Round 2 out |
|---|---|---|
| Q1(单工具) | 114 | 113 |
| Q2(双工具) | **429** | 168 |
| Q4(双工具) | **400** | 170 |

Round 1 消耗多是因为 qwen3.6-plus 是 reasoning model,在思考链里推断"要调哪几个工具"。这笔推理开销在 tool selection 阶段集中爆发。

实际意义:如果用工具很多(10+ 个),Round 1 的 token 成本会更高——这是 Pattern 03(Routing)存在的原因之一,先分类再派发可以减少无关工具噪音。

### ③ 模型自动中英文翻译

用户用中文问"钢"、"铝"、"钛",工具参数是英文 key("steel", "aluminium", "titanium")。模型**自动完成了翻译**,完全没有在 schema 里说明这件事。

这在 Qwen 这种多语言模型上 work,但不是每个模型都能做到。如果换一个英文单语模型,这里可能会出故障。

---

## 4. Code Review 结论(subagent 评审)

| 级别 | 问题 |
|---|---|
| 🟡 | `shared/llm.py` 的 `tool_uses` 是否暴露了全部并行 tool calls — 已由实际运行验证:Q2/Q4 均正确拿到 2 个 |
| 🟡 | 工具出错时(`found: False`),`run_agent` 返回 `r2.text` 但调用方看不到任何 error signal |
| 🟡 | schema + system prompt 没有说明"中文→英文参数转换"这个假设;依赖模型隐式能力 |
| 🟡 | 代码注释没有写"这是单轮,多步请用 Pattern 02" — 增加跳转提示避免学习者困惑 |
| 🟢 | schema description 质量高,`enum` 约束 property 字段是正确做法 |

**Verdict**: 实现正确,可以直接在此基础上扩展。错误处理和注释可以后续补。

---

## 5. 下一步

1. **运行 20+ 个真实案例** — 覆盖各种失败场景:
   - 问数据库没有的材料("tungsten")
   - 问数据库没有的属性("tensile strength")
   - 模棱两可的问题("which material is best for aerospace?")
   - 需要计算的问题("SiC 和 steel 哪个的 Young's modulus 高多少?")
2. **写 failure_analysis.md** — 记录每种失败模式
3. **对比 schema 写法** — 把 description 改短 1/3,看 tool 选择准确率会怎么变
4. 完成后 **feature branch → PR** 提交本阶段

注: reports/ 当前为公开目录(2026-05-13 决策),不加 gitignore。
