# 交工报告：greet CLI 脚本

TASK_ID: T20261119-151658-greet-cli-e2e
REPORTED_AT: 2026-11-19 15:24:02 +08:00
ROUND: 2

## 1. 做了什么

- S1：在交付目录创建 `greet.py`，用标准库 `argparse` 实现 `--name`（默认 `World`）与 `--upper` 两个开关，输出格式为 `Hello, <name>!`，`--upper` 时整行转大写；仅 `import argparse`。
- S2：实际运行三次并捕获真实输出：默认无参、`--name Qoder`、`--name Qoder --upper`，同时记录退出码（均为 0），并用 `python -c` 以 `repr()` 校验输出仅为一行且以 `\n` 结尾。
- S3：在交付目录创建 `usage.md`，含用途、参数表、三条真实命令与真实输出，另附 `--help` 输出与绝对路径调用示例。
- S4：按 plan.md 第 6 节与本目录 `report-template.md` 的结构撰写本报告。
- 附加校验：`python -m py_compile greet.py` 语法检查通过；其产生的 `__pycache__` 缓存已清理，交付目录最终只保留两个交付物。

## 2. 交付物清单

| 路径 | 状态 | 说明 |
|---|---|---|
| C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out\greet.py | 已创建 | 问候 CLI 脚本，仅标准库 argparse，UTF-8 无 BOM |
| C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out\usage.md | 已创建 | 使用说明，含参数表与三条真实运行示例 |
| C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\tasks\T20261119-151658-greet-cli-e2e\report.md | 已创建 | 本交工报告 |

## 3. 执行命令与真实输出

```text
$ python --version
Python 3.15.2

$ python greet.py
Hello, World!

$ python greet.py --name Qoder
Hello, Qoder!

$ python greet.py --name Qoder --upper
HELLO, QODER!

# 退出码与原始字节校验（repr）
$ python -c "import subprocess,sys; [print(repr(subprocess.run([sys.executable,'greet.py',*a],capture_output=True,text=True).stdout)) for a in ([],['--name','Qoder'],['--name','Qoder','--upper'])]"
'Hello, World!\n'
'Hello, Qoder!\n'
'HELLO, QODER!\n'

# 上方三次运行的 $LASTEXITCODE 依次为
0
0
0

# plan.md 第 4 节 CHECK 命令
$ python "C:\Users\<user>\Documents\Qoder\2026-11-19\cea38378\_e2e\out\greet.py" --name Qoder
Hello, Qoder!

$ python greet.py --help
usage: greet.py [-h] [--name NAME] [--upper]

输出一句问候语：Hello, <name>!

options:
  -h, --help   show this help message and exit
  --name NAME  要问候的对象，默认 World
  --upper      将整行输出转为大写

# import 检查（源码中以 import/from 开头的行）
$ Select-String -Path greet.py -Pattern '^\s*(import|from)\s' | ForEach-Object { $_.Line.Trim() }
import argparse

# 语法检查
$ python -m py_compile greet.py
（无输出，退出码 0）

# 文件编码检查（greet.py 前 3 字节）
35,33,47      -> "#!/" ，无 UTF-8 BOM

# 交付目录最终内容
$ Get-ChildItem -Force | ForEach-Object { "$($_.Name)`t$($_.Length)" }
greet.py	1038
usage.md	1693
```

### 返工 R2 复验（`--repeat`）

```text
$ python greet.py --name Qoder --repeat 2
Hello, Qoder!
Hello, Qoder!
（退出码 0）

$ python -c "... '--name','Qoder','--repeat','2' ..."
rc 0
stdout 'Hello, Qoder!\nHello, Qoder!\n'

$ python greet.py --repeat 0
usage: greet.py [-h] [--name NAME] [--upper] [--repeat N]
greet.py: error: argument --repeat: 需要正整数（>= 1），收到 0
（退出码 2）

$ python -c "... '--repeat','0' ..."
rc 2
stdout ''
stderr 'usage: greet.py [-h] [--name NAME] [--upper] [--repeat N]\ngreet.py: error: argument --repeat: 需要正整数（>= 1），收到 0\n'

$ python greet.py --repeat -3
usage: greet.py [-h] [--name NAME] [--upper] [--repeat N]
greet.py: error: argument --repeat: 需要正整数（>= 1），收到 -3
（退出码 2）

$ python greet.py --repeat x
usage: greet.py [-h] [--name NAME] [--upper] [--repeat N]
greet.py: error: argument --repeat: 需要正整数，收到 'x'
（退出码 2）

# 回归：原有三种用法仍正常
$ python greet.py
Hello, World!
$ python greet.py --name Qoder
Hello, Qoder!
$ python greet.py --name Qoder --upper
HELLO, QODER!

# 交付目录最终内容
$ Get-ChildItem -Force | ForEach-Object { "$($_.Name)`t$($_.Length)" }
greet.py	1758
usage.md	2457

# import 检查（仍仅标准库）
$ Select-String -Path greet.py -Pattern '^\s*(import|from)\s' | ForEach-Object { $_.Line.Trim() }
import argparse
```

## 4. 逐条自检（对应 plan.md 的 A1..An）

- A1：PASS — 无参运行输出恰为 `Hello, World!`，`repr` 为 `'Hello, World!\n'`（第 3 节）。
- A2：PASS — `--name Qoder` 输出恰为 `Hello, Qoder!`，`repr` 为 `'Hello, Qoder!\n'`；plan.md 的 CHECK 命令同样输出 `Hello, Qoder!`。
- A3：PASS — `--name Qoder --upper` 输出恰为 `HELLO, QODER!`，`repr` 为 `'HELLO, QODER!\n'`。
- A4：PASS — 源码仅有一条导入语句 `import argparse`，属标准库；无第三方依赖。
- A5：PASS — `usage.md` 含参数表（`--name`、`--upper`、`-h/--help`）与三条真实运行示例，输出与 S2 实测结果逐字一致。
- A6：PASS（R2 补测）— `--name Qoder --repeat 2` 输出恰好两行 `Hello, Qoder!`，退出码 0，`repr` 为 `'Hello, Qoder!\nHello, Qoder!\n'`（第 3 节「返工 R2 复验」）。
- A7：PASS（R2 补测）— `--repeat 0` 退出码 2，`stdout` 为空字符串，错误信息写入 `stderr`，未产生任何问候输出。

## 5. 运行环境

- 操作系统：Windows（win32）
- Python：3.15.2（`python --version` 实测）
- Shell：PowerShell（命令均在该环境执行）
- 文件编码：UTF-8（无 BOM）
- 第三方依赖：无；仅标准库 `argparse`

## 6. 遗留问题与风险

无。三项验收输出与 `usage.md` 示例一致；未安装依赖、未联网、未修改 plan.md，交付目录仅含 `greet.py` 与 `usage.md` 两个文件。

## 7. 返工记录（ROUND ≥ 2 时追加，不覆盖上文）

- R2：按 `revision-01.md` 只处理 P1/P2，未重做 R1 已完成部分。
  - 改动 1（P1，`out\greet.py`）：新增 `--repeat N`（`type=positive_int`，`metavar="N"`，默认 1）；新增 `positive_int()` 校验，`int()` 失败或 `< 1` 时抛 `argparse.ArgumentTypeError`；`main()` 改为循环 `args.repeat` 次输出同一行。仍仅 `import argparse`，未引入第三方依赖。
  - 改动 2（P2，`out\usage.md`）：用途段补 `--repeat` 说明；参数表新增 `--repeat` 行并注明非法取值行为；新增示例 4（`--name Qoder --repeat 2`）与示例 5（`--repeat 0` 报错），均为实测输出；同步更新 `--help` 输出块。
  - 复验结果：A6 PASS（两行 `Hello, Qoder!`，退出码 0）；A7 PASS（退出码 2、stdout 为空、错误在 stderr）；`--repeat -3`、`--repeat x` 均以 2 退出；A1~A5 回归全部仍 PASS。真实输出见第 3 节「返工 R2 复验」。
