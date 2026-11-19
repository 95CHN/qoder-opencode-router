# 中断处置手册（免费服务不可信原则）

opencode 免费层没有 SLA：限流、每日额度耗尽、地域封锁、模型下线、临时故障都可能发生。**派单前就要想好中断了怎么办**，不要等报错才临时决定。

## 1. 错误分类与对策

脚本从事件流的 `error` 事件、stderr、工具错误里识别类别，输出 `FAILURE_CLASS / RETRYABLE / ACTION`。

| FAILURE_CLASS | 典型证据 | 重试有用? | 换免费模型有用? | 首选动作 |
|---|---|---|---|---|
| `quota-daily` | `You've used today's free messages…reset at…` / `Free usage limit reached` | 否（等重置） | **通常无效**（账号级） | 接管 或 上报等重置 |
| `rate-limit` | `Rate limit exceeded` / 429 | 是（短退避） | 可能有效（每模型限流） | 退避重试 1 次 → 换模型 → 接管 |
| `geo-restricted` | `provider.auth: This model is not available in your country` | 否 | **有效** | 换模型（脚本自动跳过该模型） |
| `model-not-found` | `provider.no-route` / `Model unavailable` / `ProviderModelNotFoundError` | 否 | 有效 | 重解析模型名 → 换模型 |
| `context-overflow` | `context_length_exceeded` / `maximum context length` | 否 | 仅当换更大窗口 | **拆任务/精简契约**，不是换模型 |
| `auth` | 401/403、invalid api key | 否 | 否 | 上报（需用户处理凭据） |
| `provider-init` | `ProviderInitError` | 否 | 可能 | 查配置/网络，必要时上报 |
| `network` | `fetch failed` / ECONNRESET / ENOTFOUND | 是 | 可能 | 重试；注意 opencode 模型流量未必走 `HTTP_PROXY` |
| `server-error` | 500/502/503/504、overloaded | 是 | 可能 | 退避重试 1 次 → 换模型 |
| `timeout` | 本地超时 kill | — | — | 拆小任务或加 `--timeout` |
| `out-of-scope` | 写到任务范围外 | — | — | 查 plan 路径后重派，不验收 |
| `stale-report` | report.md 是上一轮遗留 | — | — | 重派；**旧报告不算本次交工** |
| `no-report` | 跑完但没写报告 | 是 | — | `revise` 只要求补报告 |

## 2. 三选一决策树

```
中断发生
├─ quota-daily / auth
│   ├─ 剩余工作量小且无需用户决策 → 【1. 我来干完】（Qoder 接管）
│   └─ 剩余量大 / 涉及用户决策 / 需等额度重置 → 【2. 停止并上报】
├─ geo-restricted / model-not-found / server-error / rate-limit / network
│   ├─ 有未试过的免费候选 → 【3. 换模型】fallback --try（最多 3 个）
│   └─ 候选用尽或仍失败 → 回到【1】或【2】按剩余量判断
└─ context-overflow / timeout / out-of-scope / stale-report
    └─ 不是换模型能解决的：拆任务、精简契约、修路径后重派；
       拆不动或已反复失败 → 【1】接管 或 【2】上报
```

### 选 1「我来干完」的条件（同时满足）

- 剩余步骤明确、范围小（Qoder 自己做的词元成本低于继续折腾外包）
- 不涉及需要用户拍板的决策、不涉及危险操作（删除/覆盖/推送/付费）
- 已有产物可复用，不需要从零重做
- 接管后**必须走接管协议**（第 3 节），不能悄悄改完就算

### 选 2「停止并上报」的条件（任一满足）

- 账号级额度耗尽且剩余量大，等待重置更划算
- 需要用户提供凭据、选择付费方案、或批准危险操作
- 同一任务已失败 ≥ 3 次（含换模型），继续试只是烧时间
- 任务本身契约有歧义，需要用户澄清

上报必须给出：错在哪（FAILURE_CLASS + 证据）、已试过什么、已完成到哪一步、剩余步骤、**三个选项与你的建议**。不要只说"失败了"。

### 选 3「换模型」的条件

- 失败类别属于"换模型可能有效"那一列
- `fallback` 列出的候选里还有未试过、且健康档案未标记不可用的
- 任务上下文没被污染（换模型走**新会话**，不复用旧上下文）
- 最多试 3 个候选；`quota-daily` 与 `context-overflow` 直接跳过此路径

## 3. 接管协议（Qoder 自己干完时）

外包中断后由 Qoder 完成剩余工作，**连接件与台账不能断链**：

1. 跑 `router.py takeover --task <ID> --note "<一句话原因>"`，把执行者标记为 qoder 并记入台账。
2. Qoder 亲自完成剩余步骤，产出交付物。
3. **由 Qoder 撰写/更新任务目录的 `report.md`**，要求：
   - 保留原 `TASK_ID` 头部，`ROUND` 递增
   - 加 `EXECUTOR: qoder-takeover`
   - 在「返工记录」追加：中断类别、opencode 已完成部分、Qoder 接管做了什么、复验证据
   - 不删除 opencode 已写的真实内容（保留审计链）
4. 跑 `verify` 做结构校验，再逐条对 A 编号语义验收。
5. 向用户汇报时**明确说明哪部分是外包完成、哪部分是 Qoder 接管完成**，不要混为一谈。

## 4. 重试预算（硬上限）

- 同一模型退避重试：最多 1 次（仅 retryable 类别）
- 换模型：最多 3 个候选
- 返工：最多 2 轮
- 超过任一上限 → 停止，走接管或上报。**不要无限重试。**

## 5. 禁止事项

- 不要为了让 verify 通过而手改 report.md 的 TASK_ID 或伪造输出
- 不要把上一轮遗留的 report.md 当本次交工（脚本已判 `stale-report`）
- 不要在 `quota-daily` 时反复换免费模型刷请求
- 不要把 API Key、Authorization 头、auth.json 内容写进报告或贴到公开场合
- 不要读取 opencode 会话库来"监工"；排错只看脚本摘要与日志末尾
