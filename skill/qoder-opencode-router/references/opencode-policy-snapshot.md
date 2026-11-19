# OpenCode 政策与模型能力快照（本地参考，不保证更新）

SNAPSHOT_AT: 2026-11-19 15:40 +08:00
SKILL_VERSION: 1.1.0
性质: **创建本技能时的一次性快照**。免费政策、模型清单、上限、地域可用性随时可能变化。运行时以 `router.py models` / `limits` / 实际报错为准，本文件只用于让 Qoder 决策模型建立合理预期。

---

## 1. 免费政策（快照时点）

- 2026-10-15，OpenCode 宣布 **DeepSeek V4.1 Flash 免费提供**，在 OpenCode 平台内调用不计入额度消耗。（来源：用户告知 + 公开报道；本技能未独立核实公告原文）
- **但"免费"不等于"无限量"**。社区实测存在两类限制：
  - **账号级每日免费消息数上限**，错误串如：`You've used today's free messages. They reset at 5:51 PM.`、`Free usage limit reached. Subscribe to OpenCode Go to keep going`
  - **每模型速率限制（RPM/TPM/并发）**，错误串如：`Rate limit exceeded`（429）
- 关键推论：**账号级每日额度耗尽时，换其他 `*-free` 模型通常同样失败**（社区 issue 中多人报告所有 opencode 免费模型返回同一限额错误）。此时"换模型"不是有效对策。
- 免费模型清单会随版本增减；付费版（OpenCode Zen / Go）与免费版是不同额度体系。

## 2. 上下文与输出上限（快照时点，来源 models.dev 目录）

opencode 运行时使用 models.dev 模型目录。下表为本机 `opencode models` 列出的 12 个可用模型在快照时点的上限：

| 模型（opencode/…） | 上下文 | 最大输出 | 备注 |
|---|---|---|---|
| deepseek-v4.1-flash-free | **200,000** | **32,000** | 默认主力；付费版 deepseek-v4.1-flash 为 1,000,000 / 384,000 |
| mimo-v2.6-flash-free | 200,000 | 32,000 | |
| big-pickle | 200,000 | 32,000 | 名称不带 -free 但在免费清单内 |
| flint-40b-free | 262,144 | 65,536 | |
| iceman-free | 262,144 | 131,072 | |
| nemotron-3.5-lightning-free | 262,144 | 262,144 | 输出上限最大之一 |
| longcat-2.5-free | 1,000,000 | 262,144 | 长上下文候选 |
| beam-free | 1,048,576 | 131,072 | **本机实测地域不可用**，见第 4 节 |
| hy4-flash-free | 1,048,576 | 65,536 | 本机实测可用（降级成功） |
| inkling-2-small-free | 1,048,576 | 131,072 | |
| nemotron-3.5-super-vl-free | 1,048,576 | 131,072 | 视觉模型 |
| tidepool-alpha-free | 1,048,576 | 131,072 | alpha，稳定性未知 |

**免费版相比付费版的主要缩水是上下文（200K vs 1M）与输出（32K vs 384K）**，不是推理档位。推理档位（none/low/medium/high/max）仍可用。

## 3. 对任务分配的直接含义

- 200K 上下文里，系统前缀 + 工具定义实测约占 5–6K；契约与模板约 1–2K。**真正吃掉上下文的是 opencode 自己读入的文件内容与工具输出**。
- 32K 输出上限意味着：一次性生成超长文件会被截断。交付物应分文件、分步骤写。
- 因此本技能设 **60% 安全水位**（200K → 120K 可用于契约+预期读取），其余留给执行过程中的工具输出与多轮累积。
- 大文件（日志、CSV、代码库）**不要让它读进上下文**，改为让它写脚本处理文件、只回读摘要。

## 4. 地域与可用性（本机实测）

- `opencode/beam-free` 实跑返回：`provider.auth: This model is not available in your country`。**免费模型存在地域限制**，清单里"可用"不代表"能调用"。
- `opencode/hy4-flash-free` 实跑成功，可作为降级候选。
- 技能用 `model-health.json` 记录每个模型最近一次结果，降级时自动跳过已知地域/鉴权不可用的模型。

## 5. 官方排错信息（快照时点）

- 日志目录：Windows `%USERPROFILE%\.local\share\opencode\log`；macOS/Linux `~/.local/share/opencode/log/`
- 详细日志：`--log-level DEBUG`；把服务日志打到 stderr：`--print-logs`（服务日志需 `--standalone`）
- 文档中出现的错误类型：`ProviderModelNotFoundError`、`ProviderInitError`
- 官方 troubleshooting 文档**未给出限额/配额的具体错误串**；限额与账单问题官方引导走账号支持渠道（社区 issue 中给出的联系邮箱为 help@anoma.ly），而非 GitHub issue
- 排错要记录四项：HTTP 状态码、供应商/网关 URL、错误响应体、是否有 `Retry-After`。**不要把 API Key、Authorization 头、auth.json 贴到公开场合**
- 注意：网关可能把 403、余额不足、上游超时统一改写成 `Rate limit exceeded`，所以"稍后重试"只适合短时速率限制；等待后仍 429 应查额度而非无脑重试

## 6. 不可信原则（长期有效，不随快照过期）

免费外部服务**没有 SLA**：可能限流、可能每日额度耗尽、可能地域封锁、可能下线模型、可能改政策。因此：

1. 任何外包任务都必须有**中断预案**（见 [failure-playbook.md](failure-playbook.md)）。
2. 不把关键路径唯一押在免费模型上；重要交付物 Qoder 必须亲自验收。
3. 不无限重试；重试与换模型都有次数上限。
4. 快照只用于建立预期，**不作为事实断言的依据**；涉及额度/价格的对外表述需重新核实。

## 7. 来源

- models.dev 模型目录（opencode 运行时所用），本机于 SNAPSHOT_AT 抓取
- OpenCode 官方文档：模型页、troubleshooting 页
- 社区 issue：免费层限额集中反馈帖、Zen 免费模型 `Rate limit exceeded` 帖
- 用户提供的 2026-10-15 免费公告信息与 200K 实测结论
