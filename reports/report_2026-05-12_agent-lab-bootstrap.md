# Report: agent-lab bootstrap + DashScope/Qwen 切换

**日期**: 2026-05-12
**作者**: Claude (代理 Yan)
**会话目的**: 启动 Phase 0 — 前置准备:把 Agent 学习的工程底座搭起来。

---

## 1. 动机

用户进入 Agent 工程系统化自学,需要一个**长期使用的本地工作区**:每天写小代码、跑 eval、记 journal。这不是一次性 hack,是 4-8 周(以及之后 Phase 2/3)持续迭代的容器。所以一开始就要把这几件事定下来:

- 统一的 LLM 客户端封装(后面所有 agent 代码都过它,traces / cost / retry 一处管)
- 项目结构(phase1 / phase2 / shared / notes / data 分清楚)
- API 通道验证(smoke test)
- Observability 接入位 (Langfuse,本期未实际接,占位先放着)
- 工作流纪律(journal、reports、code review)

中途用户从 Anthropic 切到 DashScope (Qwen):申请 Anthropic API key 阻塞了进度,且 Qwen 在中文生态、成本、迭代速度上对学习场景更优。

---

## 2. 改了什么文件,为什么

### 新建项目骨架
- `agent-lab/{phase1_patterns/{01..05_*},phase2_project,shared/{tools,eval},smoke_test,notes,data,reports}/`
- 目录命名按学习阶段切分,而不是按技术模块。学到哪一阶段就在对应目录里写,不会跨阶段污染。

### `shared/llm.py` (核心)
统一 LLM 客户端封装,任何后续 agent 代码必须经它:
- 输入:`messages`, 可选 `system / tools / model / max_tokens`
- 输出:`CallResult` dataclass — `text / tool_uses / token usage / cost / finish_reason / raw`
- **第一版用 Anthropic SDK(失败,API key 没 set),重写为 OpenAI SDK 走 DashScope OpenAI-compatible endpoint。**
- API key 环境变量优先级:`DASHSCOPE_API_KEY` → `OPENAI_API_KEY`
- base_url 默认走 `dashscope.aliyuncs.com/compatible-mode/v1`,可由 `OPENAI_BASE_URL` override
- 价格表 `PRICING` 含 qwen-max / plus / turbo / qwen3-* / qwen3-coder-plus,但**所有数字都是粗略 CNY→USD 换算,标 UNVERIFIED**

### `shared/__init__.py` 空文件占位

### `smoke_test/01_hello.py` `02_tool_use.py` `03_caching.py`
- 01:验证基础 chat completion 通路
- 02:验证 tool_use(OpenAI 函数调用格式)
- 03:验证 DashScope 自动 prefix caching(无需 cache_control 显式标记)
- 三个 test 都用 `sys.path` hack 引入 `shared.llm`,因为是脚本不是 package

### `.env.example`
- DashScope key + base_url + LLM_MODEL 默认 `qwen-plus` + Langfuse 占位

### `.gitignore`
- 标准 Python + `.env` + `.venv/`(`reports/` 最初按 workflow 规则 gitignore,2026-05-13 改为公开,作为本仓库的学习日志)

### `README.md`
- 描述项目结构和 setup 三步走 + 项目约定(每次过 `shared.llm.call()`、journal、eval-first)

### `notes/journal.md`
- Day 1 的模板,三段式(试了什么 / 失败 / 下次)

### `pyproject.toml`
- `uv init --bare` 生成,然后 `uv remove anthropic && uv add openai langfuse python-dotenv`
- 当前 deps: openai 2.36.0, langfuse 4.6.1, python-dotenv 1.2.2, requires-python>=3.13

---

## 3. 风险点

### 🔴 阻塞类
- **smoke test 还没真跑过** — 用户的 DASHSCOPE_API_KEY 还没填到 .env,所以 hello/tool_use/caching 三个测试都没验证。理论上代码对,但实际上可能踩 OpenAI SDK 2.x 的 `max_tokens` 已 deprecate 问题(reviewer 旗标)、DashScope compatible-mode 的某些行为不一致等。**用户填 key 后必须立刻跑一遍 smoke test 闭环**。

### 🟡 已知技术债
- **`max_tokens` 在 OpenAI SDK 2.x 中是 deprecated**,推荐 `max_completion_tokens`。DashScope 仍接受 `max_tokens`,但若某天 SDK 真删掉这个字段,我们会断。**短期不动,等真断了再切。**
- **`PRICING` 全部 UNVERIFIED**。学习阶段成本数字仅作参考,绝对不能用来做 budget 决策。Phase 2 开始前必须用真实账单校准。
- **`_client` module-global,base_url 第一次调用后锁定**。学习场景没问题,如果某天要在同一进程内切多个 endpoint 测试,要重构。
- **caching smoke test 可能 false negative**。DashScope auto-cache 的触发条件(prefix 长度、TTL、模型支持)不完全透明,3000 token prefix 可能不够。test 已设计成失败时 print [INFO] 而非 [FAIL],不阻塞进度。

### 🟢 设计选择(非问题,但记一下)
- **没有 retry/backoff**。学习阶段每次 API 失败手工看就好,等踩到第一次 429 再加 tenacity。
- **Langfuse 装了没用**。下一步(Step 5)接入,这一轮只是把 deps 占位拿到。
- **smoke test 用 sys.path hack 不是 proper package import**。学习项目可接受,Phase 2 项目化时再改成 `uv pip install -e .`。
- **python>=3.13** — 跟用户本机一致(3.13.12),不刻意降低门槛。

### ⚠️ Workflow / 流程
- **本项目尚未 git init,也没问 GitHub 上传**。按 feedback memory 的规则,新项目第一次接触时应该问。**待办:下一轮代码改动前问用户**。
- 因此 PR 流程也没启动。如果用户决定走 GitHub,后续每轮改动应在 feature 分支 → PR → 合并。

---

## 4. 未来 TODO (按时间顺序)

1. **下一轮立即做**:用户填 DASHSCOPE_API_KEY → 跑 3 个 smoke test → 根据结果决定是否要修 `max_tokens` 等问题
2. **本周内**:Langfuse Cloud 注册 + 在 `shared/llm.py` 接入 trace(用 langfuse.openai 装饰器或 OTel)
3. **Phase 1 开工前**:问用户 git init / GitHub 上传选择;若 yes,补 git 初始化 + 第一个 PR
4. **Phase 2 进入前**:
   - 用真实 DashScope 账单校准 PRICING
   - 给 `shared/llm.py` 加 retry (tenacity 或手写指数退避)
   - 把 smoke_test 改成 pytest,加进 CI 检查
5. **Multi-endpoint 支持**(如果以后要在同一进程对比 Qwen vs Claude):重构 `client()` 让它接受 model/endpoint 参数

---

## 5. Code Review 总结(本轮 reviewer 反馈摘要)

- 🔴 `max_tokens` 可能 deprecated → 已记录,等实测
- 🔴 caching test 可能 false negative → 已知,test 输出已设计为友好
- 🟡 PRICING 是猜的 → 已加 UNVERIFIED 注释
- 🟡 未知模型静默 0 成本 → 已加 stderr 警告
- 🟡 _client 全局不响应后续参数变化 → 文档化,不改
- 🟡 01_hello.py docstring 残留 "Claude" → 已改 "LLM"
- 🟢 langfuse 装了没用、retry 缺失、type hints 略松 → 全部进上述 TODO
- **Verdict**: ship after key 拿到 + 跑通 smoke test
