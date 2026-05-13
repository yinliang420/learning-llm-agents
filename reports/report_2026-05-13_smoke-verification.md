# Report: smoke test 验证 + qwen3.6-plus 接通

**日期**: 2026-05-13
**作者**: Claude (代理 Yan)
**会话目的**: 用 DashScope `qwen3.6-plus` 把昨天搭好的 agent-lab 三条 smoke 测通,确认整条链路 ready for Phase 1。

---

## 1. 本轮改动

| 文件 | 改动 |
|---|---|
| `shared/llm.py` | PRICING dict 加 2 行:`qwen-3.6-plus`(用户拼写)+ `qwen3.6-plus`(canonical),都标 UNVERIFIED 沿用 plus tier 价格 |
| `.env` (新建) | 只放 `LLM_MODEL=qwen3.6-plus` + Langfuse 占位;**`DASHSCOPE_API_KEY` 留在 `~/.zshrc` 不进 .env**,靠 `load_dotenv(override=False)` 默认行为让 shell 环境胜出 |
| `.env` (改) | `qwen-3.6-plus` → `qwen3.6-plus`(模型实际名,无中间杠) |

零功能代码改动,纯配置 + 模型名修正。

---

## 2. 验证结果

| Test | 结果 | 关键数据 |
|---|---|---|
| `01_hello.py` | ✅ PASS | in=16, **out=169**, cost=$0.000051 |
| `02_tool_use.py` | ✅ PASS | 模型正确选 `get_weather({'city': 'Tokyo'})`,finish_reason=tool_calls |
| `03_caching.py` | ⚠️ INFO | call1 in=3768/cached=0,call2 in=3769/**cached=0** |

### 三个观察

**(a) `qwen3.6-plus` 是 reasoning model**:回 "hello world" 用了 169 output tokens,意味着思考链占了绝大部分。后果:延迟 + 成本会比想象中高 5-10x。
- 关闭办法:`call(..., extra_body={"enable_thinking": False})` —— `**kwargs` 已透传,无需改 `call()` 签名
- 学习阶段建议:**写小脚本快速迭代时关掉、做真正 reasoning 任务时开启**

**(b) 工具调用正常**:OpenAI tool 格式在 DashScope compatible mode 下 work。tool_calls 这条 finish_reason 也 wire 对了。

**(c) Auto cache 没触发**:3768 token 的 system prefix,两次调用间隔 1 秒,`cached=0`。可能原因(无定论):
- DashScope OpenAI-compatible mode 可能需要显式 enable(reviewer 说"undocumented for newer reasoning models")
- 也可能 reasoning model 走的是另一条 cache path
- **不阻塞**;Phase 2 用到长 prompt 时再 troubleshoot,届时也要去 DashScope 控制台看 cache-hit metrics

---

## 3. Reviewer 反馈摘要

> agent 走的 review:focused 200 字内(因为 delta 太小,不重做完整 review)

- ✅ `.env` 不放 secret 的设计 OK;`load_dotenv` 默认 override=False,shell 胜出
- ⚠️ **风险**:任何不继承 shell 的上下文(cron / IDE GUI / 某些 Jupyter kernel)会拿不到 key。错误信息够清晰,可调试
- ✅ PRICING 加项数学正确(实测 $0.000051 ≈ 169 × $0.29/M = $0.000049,匹配)
- 🔍 caching:需要查 DashScope 文档 / console 来确认 reasoning model 的 cache 行为
- 💡 **enable_thinking=False** 是 DashScope 文档化的开关,学习阶段值得用

---

## 4. 风险点(本轮新增)

### 🔴 无新阻塞

### 🟡 中期需关注
- **Reasoning 默认开启** → 学习阶段 token 成本被放大。大量小 case 跑 eval 时记得关。
- **Caching 实际不工作** → 今天没影响(prompt 短),Phase 2 长 prompt 场景会显著推高 cost。
- **`uv run` 起的 subshell 不会自动 source `.zshrc`**,所以每次跑都要 `source ~/.zshrc &&` 前缀。**长期解法**:
  - (a) 把 `DASHSCOPE_API_KEY` 写到 `~/.zprofile`(login shell 才会跑,会被所有子 shell 继承),或
  - (b) 直接放 `.env`(承认 secret 在 .env 里,反正已 gitignore)
  - 暂用 (a) 还是 (b) 待后续决定

### 🟢 已知小坑
- 跑命令时 zshrc 的 compdef 段会报 `_comps: assignment to invalid subscript range` —— zsh completion 系统在非交互 shell 下的常见噪音,无害
- PRICING 仍 UNVERIFIED;真实账单出来后校准

---

## 5. 更新后的 TODO

1. **下一步立即**:决定 git init / GitHub 上传(workflow 规则);决定后再启动 Langfuse 接入
2. **Langfuse 接入**(本周):
   - 用户去 https://cloud.langfuse.com 注册 + 拿 keys
   - `shared/llm.py` 用 `langfuse.openai` wrapper(或 OTel auto-instrument)替代 raw openai client
   - 重跑 smoke test,确认 trace 落到 Langfuse dashboard
   - 顺便在 trace 里看 prompt cache 究竟有没有命中
3. **Phase 1 之前还要做**:
   - 修一下 zshrc subshell 问题(zprofile 或 .env)
   - 决定 `enable_thinking` 的项目级 default(全 ON / 全 OFF / 看情况)
   - 跑一次真账单后校准 PRICING
4. **Phase 1 开工**:写 5 个 pattern 的 minimal agent

---

## 6. 这轮没有做但应该做的事

- **尚未问用户 git init / GitHub** —— workflow 规则第 1 条,从昨天起就欠;**下次 user 回话前一定要问**
- **Langfuse 还没接** —— 仍然只是 deps 占位,没有实际 trace
