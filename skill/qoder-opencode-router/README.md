# qoder-opencode-router

把实现类任务外包给 opencode CLI 的免费模型，Qoder 只当决策者与验收者，从而省下贵模型的词元。

连接件只有两份 markdown：Qoder 写 `plan.md` 下达契约，opencode 写 `report.md` 交工，Qoder 只读 `report.md` 验收。不读对方会话缓存、不实时监工。

## 怎么用

在对话里直接说需求即可，例如：

- 「用 opencode 外包：写个批量重命名脚本，交付到桌面」
- 「派单给 opencode，用 deepseek flash low，把这份 csv 清洗成 xlsx」
- 「验收上一个外包任务」/「让 opencode 返工，输出少了一列」

也可以 `/qoder-opencode-router` 显式调用。

## 它替你做了什么

| 环节 | 谁做 | 产物 |
|---|---|---|
| 环境自检 | 脚本 `doctor` | CLI 路径/版本/可用模型/默认模型上限/连通性 |
| 查上限 | 脚本 `limits` | 各免费模型上下文与输出上限（本地快照） |
| 开任务 | 脚本 `new` | 任务目录 + `TASK_ID` + plan 骨架 |
| 上下文预算 | 脚本 `budget` | 占用估算 + GREEN/YELLOW/RED 与分配建议 |
| 写契约 | Qoder | `plan.md`（子目标 G、步骤 S、验收 A、绝对交付路径） |
| 干活 | opencode 免费模型 | 交付物 + `report.md` |
| 结构校验 | 脚本 `verify` | TASK_ID 对齐、交付物存在、可选 CHECK 命令 |
| 语义验收 | Qoder | 逐条对 A 编号判 PASS/FAIL |
| 返工 | 脚本 `revise` | 同会话续跑，只发增量问题清单 |
| 中断降级 | 脚本 `fallback` | 免费候选清单 / 自动依次试跑（跳过已知不可用） |
| Qoder 接管 | 脚本 `takeover` + Qoder | 标记执行者，Qoder 补完并写 report |
| 溯源台账 | 脚本 `index` | `INDEX.md`（给人看的一页汇总） |

## 免费服务不可信，中断有预案

免费层没有 SLA：每日额度耗尽、限流、地域封锁、模型下线都可能发生。脚本会把失败分类（`quota-daily / rate-limit / geo-restricted / context-overflow / model-not-found / auth / network / timeout / stale-report …`）并给出建议动作，Qoder 据此三选一：

1. **我来干完**（剩余量小、无需你拍板）→ 走接管协议，报告里标明哪部分是 Qoder 补的
2. **停止并上报**（额度耗尽且剩余量大、需要你处理凭据或批准危险操作）
3. **换免费模型**（地域/模型/限流类失败）→ 自动跳过已知不可用的，最多试 3 个

重试有硬上限，不会无限刷请求。政策与模型上限快照见 `references/opencode-policy-snapshot.md`（带创建时间戳，不保证更新）。

## 模型

默认 `opencode/deepseek-v4.1-flash-free#high`（推理高档，保交付质量）。想换就直接说：

- 「用 low 档」→ `--model "deepseek flash low"`
- 「用 <某个模型>」→ 脚本模糊匹配真实 ID；匹配不到会列候选让你选，不静默替换
- 变体可选：`none / minimal / low / medium / high / xhigh / max`

## 任务工作区

默认在当前工作目录下 `opencode-tasks/`，一个任务一个目录：

```
opencode-tasks/
├── INDEX.md                  ← 你只看这一页就能溯源
└── T20261119-151658-greet-cli-e2e/
    ├── plan.md               ← Qoder 下达的契约
    ├── report.md             ← opencode 的交工报告
    ├── revision-01.md        ← 返工单（如有）
    ├── meta.json             ← 编号/时间/模型/轮次/token
    └── run-*.jsonl           ← 原始执行日志（不进 Qoder 上下文）
```

交付物放在你指定的目录（如桌面），不混在任务目录里。

## 前置条件

需要本机可用的 opencode CLI。只装了 OpenCode 桌面版也行——脚本会自动找到它自带的 `resources/opencode-cli.exe`。缺失时 `doctor` 会给出安装指引，安装前会先征求你同意。

## 安全

- 涉及删除、覆盖既有文件、联网下载、安装依赖、推送远端，先问你再写进契约。
- 脚本会检测 opencode 是否写到了任务范围之外，越界即判失败，不会拿错产物来验收。
