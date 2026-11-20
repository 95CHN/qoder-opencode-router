# qoder-opencode-router 赛博外包

把实现类任务从 Qoder 外包给 opencode CLI 的免费模型，省下贵模型的词元。

**Qoder 当决策者与验收者，opencode 免费模型当执行工，两边只靠两份 markdown 连接**：Qoder 写 `plan.md` 下达契约，opencode 写 `report.md` 交工，Qoder 只读 `report.md` 验收。不读对方会话缓存、不实时监工。

形态是 **Qoder Skill**（不是 Plugin）：单一能力闭环，外部依赖是本地 CLI 而非 MCP 服务。

---

## 核心设计

| 设计 | 做法 | 为什么 |
|---|---|---|
| **分体 md + 单页台账** | 一个任务一个目录，`INDEX.md` 由脚本维护给人看 | 合体 md 会让每轮重读全量历史（累计 O(n²) 输入）并污染上下文引发串任务；分体让每任务输入恒定、前缀缓存稳定，可读性由台账补偿 |
| **四重进度对齐** | 目录名 = `TASK_ID` = plan 头部 = report 头部；时间戳带时区；G/S/A 编号互相对账；ROUND 递增 | 防止执行串到别的任务、防止旧报告冒充新交付 |
| **上下文预算闸门** | 按免费层 200K 窗口的 60% 安全水位估算，RED 直接阻止派单 | 免费版本上下文 200K / 输出 32K（付费版 1M / 384K），爆上下文会降质 |
| **不可信原则** | 13 类失败分类 + 三选一决策 + 重试硬上限 | 免费服务无 SLA：每日额度、限流、地域封锁、模型下线随时发生 |
| **同会话返工** | `revise` 用 `--session` 续跑，只发增量问题清单 | 复用缓存前缀，输入 token 降一个量级 |
| **越界写入检测** | 比对事件流写入路径与「任务目录 + 交付目录」 | 实测抓到过 opencode 读错 plan.md 跑去改别的文件 |

### 中断时的三选一

| 失败类别 | 决策 |
|---|---|
| `quota-daily`（账号级每日额度耗尽）、`auth` | 剩余量小且无需用户拍板 → **Qoder 接管**；否则 → **停止上报**。换免费模型通常无效 |
| `geo-restricted`、`model-not-found`、`rate-limit`、`server-error`、`network` | **换免费模型**：`fallback --try` 跳过健康档案里已知不可用的，最多试 3 个 |
| `context-overflow`、`timeout`、`out-of-scope`、`stale-report` | 换模型无用：拆任务 / 精简契约 / 修路径后重派 |

硬上限：同模型退避重试 ≤1 次、换模型 ≤3 个、返工 ≤2 轮。超限即停，转接管或上报。

接管时走**接管协议**：`takeover` 标记执行者 → Qoder 补完 → 由 Qoder 写 report.md（标 `EXECUTOR: qoder-takeover`、保留 TASK_ID、追加接管记录）→ verify → 汇报时分清外包完成与接管完成。

---

## 目录结构

```
qoder-opencode-router/
├── README.md                       ← 本文件（仓库说明）
├── .gitignore
├── skill/
│   └── qoder-opencode-router/      ← 技能本体，可直接打包安装
│       ├── SKILL.md                ← 主指令（163 行）
│       ├── README.md               ← 技能使用说明
│       ├── scripts/router.py       ← 确定性工作全交脚本（778 行）
│       └── references/
│           ├── protocol.md                 ← 方案论证：分体 vs 合体、缓存与词元账
│           ├── opencode-policy-snapshot.md ← 带时间戳的政策与模型上限快照（不保证更新）
│           ├── failure-playbook.md         ← 13 类分类表 + 决策树 + 接管协议
│           ├── troubleshooting.md          ← CLI 缺失/代理/地域/串任务/超时
│           ├── plan-template.md            ← 契约骨架
│           └── report-template.md          ← 交工报告骨架
├── docs/
│   ├── 交付报告-v1.0.md            ← 选型论证、协议设计、首轮端到端实测
│   └── 增补报告-v1.1.md            ← 模型认知/预算闸门/中断处置的设计与实测
└── examples/                       ← 真实运行留证（含原始事件流日志）
    ├── INDEX.md                    ← 台账样例
    ├── model-health.json           ← 模型健康档案样例
    ├── T20261119-151658-greet-cli-e2e/    ← 正常交付 + 同会话返工（high→low）
    ├── T20261119-154212-fail-probe/       ← 真实报错 → 地域限制 → 自动降级成功
    └── T20261119-155134-takeover-probe/   ← 真实失败 → Qoder 接管完成
```

---

## 安装

### 前置条件

- **opencode CLI 可用**。只装了 OpenCode 桌面版也行——脚本会自动找到它自带的 `resources/opencode-cli.exe`。
- **Python 3**（脚本只用标准库，无第三方依赖）。
- Qoder Desktop（技能安装到 user scope）。

### 方式一：打包 ZIP 导入（推荐）

```bash
cd skill
# Windows PowerShell
Compress-Archive -Path qoder-opencode-router -DestinationPath ..\qoder-opencode-router.zip
# 或 macOS / Linux
zip -r ../qoder-opencode-router.zip qoder-opencode-router
```

然后在 Qoder 的技能/扩展安装入口选择本地 ZIP 导入（`kind=skill`）。同名已存在时需确认替换。

### 方式二：直接复制

把 `skill/qoder-opencode-router/` 整个目录复制到用户技能目录：

- Windows：`%USERPROFILE%\.qoder-cn\skills\`
- macOS / Linux：`~/.qoder-cn/skills/`

安装后在对话里说「用 opencode 外包：…」即可触发，也可 `/qoder-opencode-router` 显式调用。

---

## 使用

对话里直接说需求：

- 「用 opencode 外包：写个批量重命名脚本，交付到桌面」
- 「派单给 opencode，用 deepseek flash low，把这份 csv 清洗成 xlsx」
- 「让 opencode 返工，输出少了一列」
- 「opencode 限额了，剩下的你来干完」

脚本命令（`ROUTER` = `skill/qoder-opencode-router/scripts/router.py`，全局参数放在子命令前）：

```bash
python "$ROUTER" doctor --smoke                      # 环境自检：CLI/版本/模型/上限/连通性
python "$ROUTER" models --filter deepseek            # 查可用模型
python "$ROUTER" limits [--model X]                  # 查上下文/输出上限（本地快照）
python "$ROUTER" new --title "标题" --deliver-dir "<交付目录>"
python "$ROUTER" budget --task T... [--files a.csv]  # 上下文占用估算与分配建议
python "$ROUTER" dispatch --task T... [--model "deepseek flash low"] [--files a.csv] [--force]
python "$ROUTER" verify --task T... [--run-checks]
python "$ROUTER" revise --task T... --note revision-01.md
python "$ROUTER" fallback --task T... [--try]        # 降级候选 / 自动依次试跑
python "$ROUTER" takeover --task T... --note "原因"  # 标记 Qoder 接管
python "$ROUTER" index                               # 重建用户台账
```

任务工作区默认在当前工作目录下 `opencode-tasks/`，可用 `--root` 指定。

### 模型

默认 `opencode/deepseek-v4.1-flash-free#high`（推理高档保质量）。`--model` 接受模糊词（`"deepseek flash low"`）、完整 ID、或只给变体（`"low"`）。变体：`none / minimal / low / medium / high / xhigh / max`。匹配不到会列候选让用户选，不静默替换。

---

## 实测结论（详见 docs/）

- 全链路跑通：自检 → 开任务 → 派单 → 结构校验 → 语义验收 → 同会话返工 → 台账重建。
- 默认 high 与用户自选 low 均实测生效；返工复用同一 session，缓存前缀命中（实测某步 `input=152, cache_read=6912`）。
- 预算闸门实测：把 6.7MB 文件计入读取量后估出 226 万 tokens，**BLOCKED 未调用模型**。
- 真实报错分类实测：`provider.no-route` → `model-not-found`；`provider.auth: This model is not available in your country` → `geo-restricted`。
- 降级实测：`fallback --try` 自动换到 `hy4-flash-free#high` 并成功交付。
- 接管实测：真实失败 → `takeover` → Qoder 写交付物与报告 → verify PASS。
- 首轮曾发生**串任务事故**（opencode 读了父目录旧 plan.md）：根因是它采信环境变量 `PWD`，只设子进程 `cwd` 不够。已三重修复（强制 PWD、提示词用绝对路径、越界写入检测），详见 v1.0 报告第 6 节。

---

## 已知限制

- **政策快照会过期**：`opencode-policy-snapshot.md` 带 `SNAPSHOT_AT`，只用于建立预期，不作为事实断言依据；运行时以 `models` / `limits` / 实际报错为准。
- **免费 ≠ 无限量**：存在账号级每日免费消息上限与每模型限流；额度耗尽时换免费模型通常同样失败。
- **地域限制**：部分免费模型在某些地区不可调用（本机实测 `beam-free` 属此类）。健康档案需积累后才精准。
- `quota-daily` 类别用社区真实错误串做合成样本验证，未做真实耗尽测试。
- 上下文估算是粗估（字符数/3），非精确 tokenizer；留了 40% 余量兜底。
- `CHECK:` 只支持「可执行文件 + 参数」形式，不支持 shell 管道与 PowerShell 专用语法。
- 单任务串行，未做多工并发派发。

---

## 安全与隐私提示

- 派单固定带 `--auto`（自动批准 opencode 权限请求），因此 **plan 必须写清允许改动的文件范围**。涉及删除、覆盖既有文件、联网下载、安装依赖、推送远端，先问用户再写进契约。
- 脚本不自动安装/升级 opencode CLI，不改动其全局配置。
- **`examples/` 含会话 ID 与原始事件流日志**；本机绝对路径中的用户名已脱敏为 `<user>`。若在你自己的环境复跑，日志会重新出现真实路径，提交前请自行检查。
- 不要把 API Key、Authorization 头、`auth.json` 内容写进报告或贴到公开场合。

---

## 版本

| 版本 | 内容 |
|---|---|
| 1.0.0 | 外包闭环：分体 md 协议、四重对齐、同会话返工、越界检测、台账 |
| 1.1.0 | 模型能力认知与政策快照、上下文预算闸门、13 类失败分类、三选一决策、模型健康档案与自动降级、接管协议 |

许可证：MIT（见 LICENSE）。
