# 故障排查

## CLI 找不到

`doctor` 的探测顺序：`OPENCODE_CLI` 环境变量 → PATH 上的 `opencode`/`opencode-cli` → Windows 桌面版自带 `resources/opencode-cli.exe`（含 `ai.opencode.desktop.update-*` 目录）→ `~/.opencode/bin` → `~/.bun/bin` → npm 全局 → `/usr/local/bin`、`/opt/homebrew/bin`。

常见情况：用户只装了 OpenCode 桌面版，CLI 不在 PATH。这不算故障，`doctor` 会直接找到桌面版自带的可执行文件。

需要安装时（**先征得用户同意再执行**）：

- Windows：安装 OpenCode 桌面版（自带 CLI），或 `npm i -g opencode-ai`
- macOS / Linux：`curl -fsSL https://opencode.ai/install | bash`
- 已有可执行文件但探测不到：设 `OPENCODE_CLI=<绝对路径>`

## 下载/联网失败

opencode CLI 不读系统代理。若用户本机有 Clash 等代理（常见端口 7897），给脚本加 `--proxy http://127.0.0.1:7897`，它会注入子进程的 `HTTP_PROXY`/`HTTPS_PROXY`。

**实测注意**：把 `--proxy` 指向一个死端口（127.0.0.1:9）后，opencode 的模型调用**仍然成功**——说明其模型流量未必走 `HTTP_PROXY`。所以 `--proxy` 不能当作可靠的断网/换网开关；网络类失败要结合 `ERROR_EVENT` 与日志判断。

先分清两类原因：没读到代理（加 `--proxy` 即好）vs 节点本身传不动（换节点/换网络，重试无用）。

## 模型地域不可用

症状：`ERROR_EVENT: provider.auth: This model is not available in your country`，`FAILURE_CLASS: geo-restricted`。

这不是凭据问题，是该免费模型在当前地区不开放。对策：`fallback --try`，脚本会把它记进 `model-health.json` 并自动跳过，依次试其他候选。本机实测 `beam-free` 属此类，`hy4-flash-free` 可用。

## 权限询问导致挂起

派单固定带 `--auto`。若仍卡住，检查 plan 是否要求了任务目录之外的敏感操作；把范围写清或先问用户。

## 模型相关报错

- `模型不存在` / `无匹配模型`：跑 `models --filter <关键字>` 看真实 ID，再让用户选。
- `未知变体`：合法值为 `none/minimal/low/medium/high/xhigh/max`。
- 免费模型列表随版本变化：脚本默认 ID 失效时会自动模糊匹配 deepseek+flash；仍失败就显式 `--model`。

## REPORT: MISSING

opencode 跑完但没写 report.md。按顺序查：

1. `STDERR_TAIL` / `TOOL_ERRORS` 是否有报错
2. `tail -20 run-dispatch.err`
3. plan 的第 6 节是否明确了 report.md 路径与 TASK_ID 回写要求

确认后写 `revision-01.md` 只要求补报告，跑 `revise`。

## 串任务：opencode 执行了别的任务

症状：`REPORT: MISSING`、`OUT_OF_SCOPE`，或 LAST_TEXT 描述的根本不是本次契约。

**已证实的根因**：opencode 会采信环境变量 `PWD` 来决定工作目录。从 Git Bash 调用 Python 脚本时，子进程虽设了 `cwd=任务目录`，但继承的 `PWD` 仍指向 bash 所在目录（往往是项目根）。若项目根恰好有一份旧 `plan.md`，opencode 就会去执行那份旧契约。

脚本已双重防护：`env["PWD"] = 任务目录`，且派单提示词写 plan.md 的**绝对路径**。若仍复现：

1. 看事件流里第一条 `read` 的路径（`grep` 即可，不要整份读入），确认它读的是哪份 plan.md。
2. 检查项目根/父目录是否有同名 `plan.md` 干扰；有则改名或移走。
3. 重派该任务；若越界写入覆盖了用户既有文件，先告知用户并恢复原内容。

## TASK_ID 串号

`verify` 报 `TASK_ID 串号` 说明 report 里的 ID 与 plan 不符。处理：确认读的是本任务 plan.md，然后返工要求原样回写正确 ID。**不要手工改 report 的 ID 来「让它通过」**。

## 超时

默认 900 秒。长任务 `--timeout 1800`。超时会 kill 进程并保留日志；续跑用 `revise`（同会话），不要重新 `dispatch` 重做全部步骤。

## 中文乱码

脚本子进程统一 UTF-8。若交付文件乱码，在 plan 中明确要求 UTF-8 编码写入；Windows PowerShell 侧的 `Get-Content` 显示乱码不代表文件本身坏，用 Read 工具确认。

## 不要做的事

- 不要读 `opencode.db` / 会话缓存来「监工」——违背本协议，且词元代价高。
- 不要把 `run-*.jsonl` 整份读入上下文。
- 不要为了让 verify 通过而手改 report.md。
