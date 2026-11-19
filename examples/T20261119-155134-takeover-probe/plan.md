# 任务：接管路径探针

> 只读本文件与同目录 report-template.md。ROUTER 头部禁止修改。

## 2. 目标与子目标

- G1：在交付目录创建标记文件，用于验证外包中断后由 Qoder 接管的链路

## 3. 执行步骤

1. S1：在交付目录创建 `poi2.txt`，内容恰好为一行 `TAKEOVER-OK`
2. S2：实际读取确认内容
3. S3：按第 6 节撰写 report.md 到本任务目录

## 4. 交付物

- C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out3\poi2.txt — 标记文件

## 5. 验收标准

- A1：`poi2.txt` 存在，内容恰好为 `TAKEOVER-OK`（可含结尾换行）

## 6. report.md 要求

- 路径：本任务目录下 `report.md`，UTF-8
- 头部原样回写 `TASK_ID: T20261119-155134-takeover-probe`，写 `REPORTED_AT`、`ROUND`、`EXECUTOR`
- 章节遵循同目录 report-template.md，输出必须真实

## 7. 约束与禁止事项

- 只创建第 4 节交付物与本任务目录 report.md；不安装依赖、不联网、不删除文件、不修改 plan.md

## 8. 完成信号

完成后回复 `DELIVERED: poi2.txt`；被阻塞则回复 `BLOCKED: <原因>`。
