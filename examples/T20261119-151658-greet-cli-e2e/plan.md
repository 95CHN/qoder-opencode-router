<!-- ROUTER:BEGIN -->
TASK_ID: T20261119-151658-greet-cli-e2e
CREATED_AT: 2026-11-19 15:16:58 +0800
DELIVER_DIR: C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out
<!-- ROUTER:END -->

# 任务：greet CLI 脚本

> 本文件是 Qoder 下达给 opencode 的唯一任务契约。只读本文件与同目录 report-template.md，不读其他任务目录、不读台账、不读历史会话。ROUTER 头部禁止修改。

## 1. 背景

交付目录已存在且为空。运行环境为 Windows + Python 3.15，命令行通过 Git Bash 或 PowerShell 均可。文件一律 UTF-8 编码。

## 2. 目标与子目标

- G1：交付一个可复用的问候 CLI 脚本 `greet.py`
- G2：脚本支持 `--name`（默认 `World`）与 `--upper`（输出转大写）两个开关
- G3：交付一份使用说明 `usage.md`，含真实运行示例

## 3. 执行步骤

1. S1：在交付目录创建 `greet.py`，用标准库 `argparse` 实现 G2，输出格式为 `Hello, <name>!`，`--upper` 时整行转大写。只用标准库。
2. S2：实际运行三次并捕获真实输出：默认无参、`--name Qoder`、`--name Qoder --upper`。
3. S3：在交付目录创建 `usage.md`，包含用途、参数表、S2 的三条真实命令与真实输出。
4. S4：按第 6 节撰写 report.md 到本任务目录。

## 4. 交付物

- C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out\greet.py — 问候 CLI 脚本
- C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out\usage.md — 使用说明与真实示例

CHECK: python "C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out\greet.py" --name Qoder

## 5. 验收标准

- A1：无参运行输出恰好为 `Hello, World!`
- A2：`--name Qoder` 输出恰好为 `Hello, Qoder!`
- A3：`--name Qoder --upper` 输出恰好为 `HELLO, QODER!`
- A4：`greet.py` 只 import 标准库，无第三方依赖
- A5：`usage.md` 含参数表与三条真实运行示例，输出与 S2 实测一致

## 6. report.md 要求

- 路径：本任务目录下 `report.md`，UTF-8。
- 头部原样回写 `TASK_ID: T20261119-151658-greet-cli-e2e`，并写 `REPORTED_AT`（当前本地时间含时区）、`ROUND: 1`。
- 章节遵循同目录 report-template.md：做了什么 / 交付物清单 / 执行命令与真实输出 / 逐条自检 A1..A5 / 运行环境 / 遗留问题。
- 所有输出必须真实执行取得，禁止编造；失败就如实写错误信息。

## 7. 约束与禁止事项

- 只创建第 4 节两个交付物与本任务目录的 report.md，不动其他文件。
- 不安装依赖、不联网、不执行删除类命令。
- 不修改 plan.md。
- 无法完成时停下，把阻塞原因写进 report.md 的「遗留问题」，不要自行改变目标。

## 8. 完成信号

完成后最终回复一行：`DELIVERED: greet.py, usage.md`；被阻塞则回复 `BLOCKED: <原因>`。
