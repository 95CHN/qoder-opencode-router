---
name: qoder-opencode-router
version: 1.1.0
description: Routes implementation work from Qoder to the opencode CLI's free models to save tokens. Qoder acts as the decision maker that writes plan.md with numbered subgoals, absolute deliverable paths and testable acceptance criteria; opencode executes and returns report.md; Qoder reads only report.md to accept or send a same-session revision. Enforces a context budget against the free tier's 200K window, classifies interruptions (daily quota, rate limit, geo restriction, context overflow, model unavailable) and decides between Qoder takeover, stop-and-report, or switching to another free model. Use when the user wants to outsource coding/scripting/file-generation tasks to opencode, run tasks on free models such as deepseek flash, handle opencode quota/rate-limit/outage failures, or mentions 外包/派单/省钱跑任务/plan.md/report.md/opencode 协作/限额/中断.
description_zh: 把实现类任务外包给 opencode CLI 的免费模型以节省词元。Qoder 只做决策与验收：写 plan.md（编号子目标、绝对交付路径、可判定验收标准），opencode 执行后交 report.md，Qoder 只读 report.md 验收或同会话返工。按免费层 200K 上下文做预算闸门，对中断（每日额度、限流、地域限制、爆上下文、模型不可用）分类并在「Qoder 接管 / 停止上报 / 换免费模型」之间决策。当用户要把写代码/脚本/生成文件类任务交给 opencode、用 deepseek flash 等免费模型干活、处理 opencode 限额或中断报错，或提到外包/派单/省钱跑任务/plan.md/report.md/限额/中断时使用。
user-invocable: true
argument-hint: 描述要外包的任务，可附带模型偏好（如"用 deepseek flash low"）与交付路径
---

# Qoder → OpenCode 外包路由器

Qoder 是决策模型（贵），opencode 免费模型是执行工（便宜）。本技能把实现类工作外包出去，Qoder 只付出「写契约 + 读交工摘要」的词元。

## 铁律

1. **只用两份 markdown 连接**：`plan.md`（Qoder 写）→ `report.md`（opencode 写）。
2. **不监工**：禁止读取 opencode 的会话库（`opencode.db`）、会话缓存、`run-*.jsonl` 全文。执行细节由脚本压缩成 ≤10 行摘要。
3. **Qoder 不亲自实现**：一旦判定任务可外包，就不要自己写实现代码；只写 plan、验收、返工指令。
4. **任务隔离**：一个任务一个目录，`TASK_ID` 双向回写校验，防止串到别的任务。

## 词元纪律（本技能的核心收益）

- 每任务 Qoder 侧只允许：写 1 份 plan.md + 读 1 份 report.md + 脚本 terse 输出。
- 失败排查只允许 `tail` 日志末 20 行（`run-dispatch.err`），不要整份读入。
- 台账 `INDEX.md` 是给人看的，**Qoder 默认不读**；只有用户问历史时才读。
- 返工用 `revise`（同会话续跑，复用缓存前缀），不要重发全量背景、不要新开任务重做。

## 脚本

`ROUTER` = 本 SKILL.md 同目录下的 `scripts/router.py`（Windows 典型路径 `C:\Users\<用户>\.qoder-cn\skills\qoder-opencode-router\scripts\router.py`）。用绝对路径调用，`--root` 指定任务工作区（默认当前工作目录下 `opencode-tasks/`）。全局参数必须放在子命令之前。

```bash
python "<ROUTER>" doctor --smoke                      # 环境自检（首次或报错时）
python "<ROUTER>" models --filter deepseek            # 查可用模型
python "<ROUTER>" limits [--model X]                  # 查上下文/输出上限（本地快照）
python "<ROUTER>" new --title "标题" --deliver-dir "C:\Users\xhh\Desktop"
python "<ROUTER>" budget --task T... [--files a.csv]  # 上下文占用估算与分配建议
python "<ROUTER>" dispatch --task T... [--model "deepseek flash low"] [--files a.csv] [--force]
python "<ROUTER>" verify --task T... [--run-checks]
python "<ROUTER>" revise --task T... --note revision-01.md
python "<ROUTER>" fallback --task T... [--try]        # 列降级候选 / 自动依次试跑
python "<ROUTER>" takeover --task T... --note "原因"  # 标记 Qoder 接管
python "<ROUTER>" index                               # 重建用户台账
```

## 模型能力与上下文预算（派单前必须心里有数）

免费层不是"无限能力的便宜模型"，它有硬上限。快照详见 [opencode-policy-snapshot.md](references/opencode-policy-snapshot.md)（带创建时间戳，**不保证更新**，运行时以 `models`/`limits`/实际报错为准）。

- 默认主力 `deepseek-v4.1-flash-free`：**上下文 200K、最大输出 32K**（付费版是 1M/384K，缩水的是窗口不是档位）。
- 200K 里系统前缀+工具定义实测占 5–6K，契约+模板约 1–2K；**真正吃上下文的是 opencode 自己读入的文件和工具输出**。
- 脚本按 **60% 安全水位**（200K→120K）做闸门：`dispatch` 前自动估算，RED 直接阻止派单并给拆分建议，`--force` 才越过。
- 分配任务的规则：
  - 单份契约控制在 ~2K tokens 内；背景只写影响决策的信息。
  - **大文件不要让它读进上下文**——改为让它写脚本处理文件、只回读摘要/统计。
  - 预计要读入文件时，用 `budget --files <路径>` 或 `dispatch --files <路径>` 把它们计入估算。
  - 输出上限 32K：交付物分文件、分步骤写，避免单次超长生成被截断。
  - 多阶段任务拆成多个 TASK_ID，下游 plan 只引用上游产物的**路径**，不复制内容。
  - 需要更大窗口时才考虑长上下文候选（如 `longcat-2.5-free` 1M），但先确认它在本机可调用。

## 工作流

### Step 0 · 环境自检（首次使用或任何 CLI 报错时）

跑 `doctor --smoke`。它探测 CLI（PATH → 桌面版自带 `resources/opencode-cli.exe` → 常见安装位置）、版本、可用模型数、默认模型解析、连通性。

- `CLI: NOT FOUND` → 按输出的 FIX 行引导用户安装，**不要擅自执行安装命令**；安装属用户确认事项。详见 [troubleshooting.md](references/troubleshooting.md)。
- `SMOKE: FAIL` → 先分清是网络/代理问题还是模型问题，再决定是否 `--proxy http://127.0.0.1:7897` 重试。
- 已 PASS 过且本次无异常 → 跳过 Step 0，省词元。

### Step 1 · 开任务

`new --title "<简短标题>" --deliver-dir "<用户要求的交付目录>"`。用户没指定交付目录时，用任务目录下 `out/`，并在最终汇报里告知路径。

脚本产出 `TASK_ID`、任务目录、`plan.md` 骨架、随任务下发的 `report-template.md`。**记下 TASK_ID**。

### Step 2 · 写 plan.md（Qoder 的核心价值所在）

用 Write 覆盖骨架正文，**保留 `<!-- ROUTER:BEGIN -->` 头部**（若整份重写丢了头部，dispatch 前脚本会自动补盖并校正 TASK_ID）。质量要求：

- **背景可选**：只写影响执行决策的信息（既有文件位置、技术栈、命名规范、用户偏好）。没有就删掉整节。
- **子目标编号** G1/G2…，**步骤编号** S1/S2…，**验收标准编号** A1/A2…，三者可互相追溯。
- **交付物必须是绝对路径**，每行以 `- ` 开头（`verify` 靠这一节做存在性校验）。
- **验收标准必须可判定**：写"运行输出恰好为 X"，不写"质量良好"。
- **补上用户没想到的关键信息**：编码 UTF-8、依赖限制、失败时如实报告、禁止删除/联网、完成信号 `DELIVERED:`。
- 需要自动跑校验时，加 `CHECK: python "<绝对路径>"` 行（可执行文件+参数形式，不要 shell 管道）。
- 若用户要求报告也交付到某目录，把该路径追加进交付物清单，并要求 opencode 同时写任务目录的 `report.md` 与该副本。

骨架见 [plan-template.md](references/plan-template.md)。

### Step 3 · 派单

`dispatch --task <TASK_ID>`，默认模型 **deepseek flash high**。用户指定模型时按下方规则传 `--model`。

脚本以任务目录为 cwd、`--auto --archived --format json` 调用 opencode，落盘 `run-dispatch.jsonl`，只回显摘要（BUDGET/EXIT/TOOLS/TOKENS/REPORT/FAILURE_CLASS/LAST_TEXT）。

- 先过**预算闸门**：RED 会阻止派单（返回 3），按建议拆分或精简；YELLOW 会提示收紧读取范围。
- `REPORT: MISSING` / `STALE(上一轮遗留)` / `EXIT != 0` → 看 `FAILURE_CLASS` 与 `ACTION`，按 [failure-playbook.md](references/failure-playbook.md) 决策。**旧报告不算本次交工。**
- `OUT_OF_SCOPE` → opencode 写到了任务范围外（典型原因：读错了别处的 plan.md）。**不要验收**，按 [troubleshooting.md](references/troubleshooting.md) 的「串任务」排查后重派；若已覆盖用户既有文件，先告知并恢复。
- 超时默认 900 秒，长任务加 `--timeout 1800`。

### Step 4 · 验收（两段）

1. **结构校验**：`verify --task <TASK_ID>`（需要跑命令时加 `--run-checks`）。它校验 report 的 TASK_ID 是否与 plan 一致、交付物是否存在且非空。`RESULT: FAIL` 时按列出的原因返工。
2. **语义验收**：Qoder 亲自 `Read` 任务目录的 `report.md`，逐条对照 A1..An 判断证据是否成立。**只读 report.md，不读交付物全文**；只有当报告证据可疑时，才抽查具体交付物或实跑一次验证命令。

### Step 5 · 判定与返工

- 通过 → 向用户汇报：任务编号、交付物绝对路径、验收结论、所用模型。不要复述报告全文。
- 不通过 → 在任务目录写 `revision-01.md`（只列问题清单 + 期望结果 + 对应 A 编号，不重抄背景），跑 `revise --task <ID> --note revision-01.md`。同会话续跑，命中缓存前缀。
- 最多返工 2 轮。仍失败 → 停止，向用户说明卡点与已完成部分，不要无限重试烧时间。

## 模型选择

- 默认：`opencode/deepseek-v4.1-flash-free#high`（脚本在该 ID 失效时自动模糊匹配 deepseek+flash）。
- 用户自选：`--model` 接受三种写法 —— 模糊词（`"deepseek flash low"`）、完整 ID（`opencode/xxx#high`）、只给变体（`"low"`）。
- 变体是推理档位：`none/minimal/low/medium/high/xhigh/max`。**默认 high 保交付质量**；只有用户明确要更快/更省时才降档。
- 用户说的模型名匹配不到时，跑 `models --filter <关键字>` 把候选给用户选，不要静默替换成别的模型。

## 不可信原则与中断决策

**免费服务没有 SLA，随时可能中断。** 派单前就要有预案，不要等报错才临时决定。完整分类表与决策树见 [failure-playbook.md](references/failure-playbook.md)。

脚本会输出 `FAILURE_CLASS / RETRYABLE / ACTION`，据此三选一：

| 情况 | 决策 |
|---|---|
| `quota-daily`（账号级每日额度耗尽）、`auth` | 剩余量小且无需用户拍板 → **我来干完**；否则 → **停止上报**（等重置/需用户处理）。**换免费模型通常无效，不要刷请求** |
| `geo-restricted`、`model-not-found`、`rate-limit`、`server-error`、`network` | **换免费模型**：`fallback --try` 自动跳过健康档案里已知不可用的模型，依次试最多 3 个（新会话） |
| `context-overflow`、`timeout`、`out-of-scope`、`stale-report` | 换模型解决不了：拆任务/精简契约/修路径后重派；拆不动或反复失败 → 接管或上报 |

硬上限：同模型退避重试 ≤1 次，换模型 ≤3 个，返工 ≤2 轮。超限即停，转接管或上报。

**接管协议**（选「我来干完」时必须走，保证台账不断链）：

1. `takeover --task <ID> --note "<原因>"` 标记执行者。
2. Qoder 亲自完成剩余步骤。
3. **由 Qoder 写/更新 report.md**：保留 TASK_ID、`ROUND` 递增、加 `EXECUTOR: qoder-takeover`、在返工记录里写明中断类别 + opencode 已完成部分 + 接管做了什么 + 复验证据；不删 opencode 已写的真实内容。
4. `verify` + 逐条语义验收。
5. 向用户汇报时**分清哪部分是外包完成、哪部分是 Qoder 接管**。

**上报模板**：错在哪（FAILURE_CLASS + 证据）／已试过什么／已完成到哪／剩余步骤／三个选项与你的建议。不要只说"失败了"。

## 串号防护

- 目录名即 `TASK_ID`（`T<日期>-<时分秒>-<slug>`），plan 头部与 report 头部必须一致，`verify` 会判 FAIL。
- 派单提示词用 **plan.md 的绝对路径**，不依赖「当前目录」这种相对表述；脚本同时把子进程 `PWD` 强制设为任务目录（opencode 会采信 `PWD`，只设 cwd 不够）。
- 脚本比对事件流里的写入路径与「任务目录 + 交付目录」，越界即报 `OUT_OF_SCOPE` 并判失败。
- plan 中明令禁止读取其他任务目录与台账；返工提示词固定强调「只处理 revision 列出的问题」。

## 安全边界

- `--auto` 会自动批准 opencode 的权限请求，因此 plan 必须写清允许改动的文件范围；涉及删除、覆盖既有文件、联网下载、安装依赖、推送到远端等动作，**先问用户**再写进 plan。
- 交付目录已有同名文件时，先告知用户并确认覆盖或改名，不要静默覆盖。
- 不自动安装/升级 opencode CLI，不改动 opencode 全局配置。

## 参考

- 方案论证与协议细节（分体 vs 合体、缓存与词元账）：[protocol.md](references/protocol.md)
- 政策与模型能力快照（带时间戳，不保证更新）：[opencode-policy-snapshot.md](references/opencode-policy-snapshot.md)
- 中断分类与三选一决策、接管协议：[failure-playbook.md](references/failure-playbook.md)
- 故障排查（CLI 缺失、代理、权限、超时、串号）：[troubleshooting.md](references/troubleshooting.md)
- 契约模板：[plan-template.md](references/plan-template.md) · [report-template.md](references/report-template.md)
