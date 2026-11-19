# 交工报告：失败路径探针

TASK_ID: T20261119-154212-fail-probe
REPORTED_AT: 2026-11-19 15:47:18 +08:00
ROUND: 1

## 1. 做了什么

- S1：在交付目录 `C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out2` 创建 `poi.txt`，写入内容 `ROUTER-OK`（首次用 Set-Content -Encoding UTF8 写入带有 BOM，已用无 BOM 的 UTF8 重新写入以符合 A1）。
- S2：实际读取该文件确认内容，捕获真实输出（`Get-Content` 输出 `ROUTER-OK`；字节为 `82 79 85 84 69 82 45 79 75 13 10`，即 `ROUTER-OK` + CRLF，无 BOM）。
- S3：按第 6 节撰写本报告到本任务目录。

## 2. 交付物清单

| 路径 | 状态 | 说明 |
|---|---|---|
| C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out2\poi.txt | 已创建 | 标记文件，内容恰好为一行 `ROUTER-OK`（无 BOM） |
| C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\tasks\T20261119-154212-fail-probe\report.md | 已创建 | 本报告（UTF-8） |

## 3. 执行命令与真实输出

```text
# S1 创建（首次，带 BOM）
$dir = 'C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out2'; if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }; Set-Content -Path (Join-Path $dir 'poi.txt') -Value 'ROUTER-OK' -Encoding UTF8; Write-Output 'CREATE_DONE'
CREATE_DONE

# S1 重写为无 BOM
$f = 'C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out2\poi.txt'; [System.IO.File]::WriteAllText($f, "ROUTER-OK`r`n", (New-Object System.Text.UTF8Encoding($false))); Write-Output 'REWRITTEN_NO_BOM'
REWRITTEN_NO_BOM

# S2 读取确认
$f = 'C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out2\poi.txt'; Write-Output '--- Get-Content ---'; Get-Content -Path $f; Write-Output '--- bytes ---'; $b = [System.IO.File]::ReadAllBytes($f); Write-Output ("Bytes: " + ($b -join ' ')); Write-Output ("Exists: " + (Test-Path $f))
--- Get-Content ---
ROUTER-OK
--- bytes ---
Bytes: 82 79 85 84 69 82 45 79 75 13 10
Exists: True

# 运行环境查询
Write-Output '--- Local time with timezone ---'; Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'; Write-Output '--- Time zone ---'; (Get-TimeZone).Id; Write-Output '--- PowerShell version ---'; $PSVersionTable.PSVersion.ToString()
--- Local time with timezone ---
2026-11-19 15:47:03 +08:00
--- Time zone ---
China Standard Time
--- PowerShell version ---
5.1.19041.6456
```

## 4. 逐条自检（对应 plan.md 的 A1..An）

- A1：PASS — 第 3 节真实输出显示 `Get-Content` 返回 `ROUTER-OK`，字节序列 `82 79 85 84 69 82 45 79 75 13 10` 即 `ROUTER-OK` 加结尾换行（CRLF），无 BOM、`Exists: True`，满足“存在且内容恰好为 `ROUTER-OK`（可含结尾换行）”。

## 5. 运行环境

Windows PowerShell 5.1.19041.6456；时区 China Standard Time（UTC+08:00）。查询命令与真实输出见第 3 节。

## 6. 遗留问题与风险

无。

## 7. 返工记录（ROUND ≥ 2 时追加，不覆盖上文）

不适用（ROUND: 1）。
