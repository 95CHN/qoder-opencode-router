#!/usr/bin/env python3
"""Deterministic bridge: Qoder decides, opencode CLI executes, markdown files connect."""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_MODEL = "opencode/deepseek-v4.1-flash-free#high"
VARIANTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
SNAPSHOT_AT = "2026-11-19 15:40 +08:00"
SYSTEM_PREFIX_EST = 6000
SAFE_WATERLINE = 0.6
MODEL_LIMITS = {
    "deepseek-v4.1-flash-free": (200000, 32000),
    "mimo-v2.6-flash-free": (200000, 32000),
    "big-pickle": (200000, 32000),
    "flint-40b-free": (262144, 65536),
    "iceman-free": (262144, 131072),
    "nemotron-3.5-lightning-free": (262144, 262144),
    "longcat-2.5-free": (1000000, 262144),
    "beam-free": (1048576, 131072),
    "hy4-flash-free": (1048576, 65536),
    "inkling-2-small-free": (1048576, 131072),
    "nemotron-3.5-super-vl-free": (1048576, 131072),
    "tidepool-alpha-free": (1048576, 131072),
}
FAILURE_RULES = [
    ("quota-daily", False, "stop-or-takeover",
     r"used today's free messages|free usage limit reached|daily free|free messages.*reset"),
    ("rate-limit", True, "retry-then-switch",
     r"rate limit exceeded|rate_limit|too many requests|\b429\b"),
    ("context-overflow", False, "split-task",
     r"context (length|window|limit)|maximum context|context_length_exceeded|too many tokens|prompt is too long|reduce the length"),
    ("model-not-found", False, "re-resolve-model",
     r"ProviderModelNotFoundError|model.*not found|unknown model|no such model|model unavailable|no-route"),
    ("geo-restricted", False, "switch-model",
     r"not available in your (country|region)|geo.?restrict|unsupported (country|region)|provider\.auth"),
    ("auth", False, "stop-report",
     r"\b401\b|\b403\b|unauthorized|invalid api key|authentication|forbidden"),
    ("provider-init", False, "fix-config",
     r"ProviderInitError|provider.*init|failed to load provider"),
    ("network", True, "retry-or-proxy",
     r"ECONNRESET|ETIMEDOUT|ENOTFOUND|EAI_AGAIN|fetch failed|network error|socket hang up|ECONNREFUSED"),
    ("server-error", True, "retry-then-switch",
     r"\b500\b|\b502\b|\b503\b|\b504\b|internal server error|service unavailable|overloaded"),
]
STAMP_RE = re.compile(r"<!-- ROUTER:BEGIN -->.*?<!-- ROUTER:END -->\n?", re.S)
TASK_ID_RE = re.compile(r"^TASK_ID:\s*(\S+)", re.M)
DELIVER_RE = re.compile(
    r'^\s*-\s+(?:\[[ xX]\]\s+)?(?:"([^"\n]+)"|\'([^\'\n]+)\'|([A-Za-z]:[\\/][^\s—|]+|/[^\s—|]+))', re.M)
CHECK_RE = re.compile(r"^\s*CHECK:\s*(.+)$", re.M)


def now():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def stamp_slug(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:24] or "task"


def find_cli():
    env = os.environ.get("OPENCODE_CLI")
    if env and Path(env).exists():
        return env, "env:OPENCODE_CLI"
    for name in ("opencode", "opencode-cli"):
        p = shutil.which(name)
        if p:
            return p, "PATH"
    home = Path.home()
    cands = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        base = Path(local) / "Programs"
        cands.append(base / "ai.opencode.desktop" / "resources" / "opencode-cli.exe")
        if base.exists():
            cands += sorted(base.glob("ai.opencode.desktop.update-*/resources/opencode-cli.exe"), reverse=True)
        cands.append(Path(local) / "opencode" / "bin" / "opencode.exe")
    cands += [
        home / ".opencode" / "bin" / "opencode.exe",
        home / ".opencode" / "bin" / "opencode",
        home / ".bun" / "bin" / "opencode.exe",
        home / ".bun" / "bin" / "opencode",
        home / "AppData" / "Roaming" / "npm" / "opencode.cmd",
        Path("/usr/local/bin/opencode"),
        Path("/opt/homebrew/bin/opencode"),
    ]
    for c in cands:
        if c.exists():
            return str(c), "desktop-bundled" if "ai.opencode.desktop" in str(c) else "known-location"
    return None, None


def run_cli(cli, args, cwd=None, timeout=120, proxy=None):
    env = dict(os.environ)
    if proxy:
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = proxy
    return subprocess.run(
        [cli] + args, cwd=cwd, env=env, capture_output=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def list_models(cli, proxy=None):
    r = run_cli(cli, ["models"], timeout=120, proxy=proxy)
    return [l.strip() for l in r.stdout.splitlines() if "/" in l and not l.startswith(" ")]


def default_model(models):
    base, _, var = DEFAULT_MODEL.partition("#")
    if base not in models:
        hits = [m for m in models if "deepseek" in m and "flash" in m]
        if not hits:
            raise SystemExit(f"默认模型不可用，请用 --model 指定。可用：{', '.join(models[:8])}")
        base = hits[0]
    return f"{base}#{var}"


def resolve_model(spec, models):
    spec = (spec or "").strip()
    if not spec:
        return default_model(models)
    var = ""
    if "#" in spec:
        spec, var = spec.split("#", 1)
    tokens = spec.lower().split()
    if tokens and tokens[-1] in VARIANTS:
        var = tokens.pop()
    if not tokens:
        base = default_model(models).split("#")[0]
    elif "/" in tokens[-1]:
        base = tokens[-1]
        if base not in models:
            tail = base.split("/")[-1]
            hits = [m for m in models if m.split("/")[-1] == tail]
            if not hits:
                raise SystemExit(f"模型不存在：{base}")
            base = hits[0]
    else:
        hits = [m for m in models if all(t in m.lower() for t in tokens)]
        if not hits:
            raise SystemExit(f"无匹配模型：{spec}。用 models 子命令查看可用模型")
        if len(hits) > 1:
            pref = [m for m in hits if m.startswith("opencode/")]
            hits = pref or hits
        base = sorted(hits, key=len)[0]
    var = var or "high"
    if var not in VARIANTS:
        raise SystemExit(f"未知变体：{var}（可选 {', '.join(sorted(VARIANTS))}）")
    return f"{base}#{var}"


def model_limits(model):
    key = (model or "").split("#")[0].split("/")[-1]
    return MODEL_LIMITS.get(key)


def est_tokens(text):
    return int(len(text or "") / 3)


def classify_failure(haystack, code, timed_out, report_exists, stray):
    low = (haystack or "").lower()
    for name, retryable, action, pat in FAILURE_RULES:
        m = re.search(pat, low, re.I)
        if m:
            return name, retryable, action, m.group(0)[:80]
    if timed_out:
        return "timeout", True, "shrink-or-extend", "local timeout kill"
    if stray:
        return "out-of-scope", False, "re-dispatch", "wrote outside task scope"
    if code != 0:
        return "unknown-error", False, "stop-report", f"exit={code}"
    if not report_exists:
        return "no-report", True, "revise", "run finished without report.md"
    return "none", False, "accept", ""


def budget_of(d, extra_files=()):
    model = load_meta(d).get("model") or DEFAULT_MODEL
    lim = model_limits(model)
    ctx, out = lim if lim else (200000, 32000)
    plan = (d / "plan.md").read_text(encoding="utf-8") if (d / "plan.md").exists() else ""
    tpl = (d / "report-template.md").read_text(encoding="utf-8") if (d / "report-template.md").exists() else ""
    base = SYSTEM_PREFIX_EST + est_tokens(plan) + est_tokens(tpl)
    extra = 0
    for f in extra_files:
        p = Path(f)
        if p.is_file():
            extra += est_tokens(p.read_text(encoding="utf-8", errors="replace"))
    usable = int(ctx * SAFE_WATERLINE)
    total = base + extra
    ratio = total / usable if usable else 99
    grade = "GREEN" if ratio < 0.3 else ("YELLOW" if ratio < 0.6 else "RED")
    return {"model": model, "ctx": ctx, "out": out, "known": bool(lim), "base": base,
            "extra": extra, "total": total, "usable": usable, "ratio": round(ratio, 3), "grade": grade}


def health_path(root):
    return root / "model-health.json"


def load_health(root):
    p = health_path(root)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def record_health(root, model, cls):
    h = load_health(root)
    h[model.split("#")[0]] = {"status": "ok" if cls == "none" else cls, "at": now()}
    health_path(root).write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")


def root_dir(args):
    r = Path(args.root).expanduser() if getattr(args, "root", None) else Path.cwd() / "opencode-tasks"
    r.mkdir(parents=True, exist_ok=True)
    return r.resolve()


def task_dir(root, task_id):
    d = root / task_id
    if not d.is_dir():
        raise SystemExit(f"任务不存在：{task_id}")
    return d


def load_meta(d):
    return json.loads((d / "meta.json").read_text(encoding="utf-8"))


def save_meta(d, meta):
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def stamp_plan(d, meta):
    p = d / "plan.md"
    body = p.read_text(encoding="utf-8") if p.exists() else ""
    block = (
        "<!-- ROUTER:BEGIN -->\n"
        f"TASK_ID: {meta['task_id']}\n"
        f"CREATED_AT: {meta['created_at']}\n"
        f"DELIVER_DIR: {meta['deliver_dir']}\n"
        "<!-- ROUTER:END -->\n"
    )
    body = STAMP_RE.sub("", body)
    p.write_text(block + "\n" + body.lstrip("\n"), encoding="utf-8")


def index_append(root, meta, status, note=""):
    f = root / "INDEX.md"
    if not f.exists():
        f.write_text(
            "# OpenCode 外包台账\n\n"
            "> 本页由 router.py 自动维护，供人阅读溯源；Qoder 侧默认不读本页。\n\n"
            "| 任务编号 | 标题 | 时间 | 模型 | 状态 | 备注 |\n"
            "|---|---|---|---|---|---|\n", encoding="utf-8")
    model = (meta.get("model") or "-").replace("opencode/", "")
    f.open("a", encoding="utf-8").write(
        f"| {meta['task_id']} | {meta.get('title','')} | {now()} | {model} | {status} | {note} |\n")


def parse_events(path):
    info = {"session": None, "texts": [], "tools": 0, "tool_errors": [], "errors": [], "writes": [], "tokens": {"input": 0, "output": 0, "cache_read": 0}, "reason": None}
    if not path.exists():
        return info
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        info["session"] = o.get("sessionID") or info["session"]
        p = o.get("part") or {}
        t = o.get("type")
        if t == "error":
            e = o.get("error") or {}
            info["errors"].append(f"{e.get('type', '')}: {e.get('message', '')}"[:200])
        if t == "text" and p.get("text"):
            info["texts"].append(p["text"])
        elif t == "tool_use":
            info["tools"] += 1
            st = p.get("state") or {}
            if p.get("tool") in ("write", "edit", "patch"):
                wp = (st.get("input") or {}).get("path") or (st.get("input") or {}).get("filePath")
                if wp:
                    info["writes"].append(str(wp))
            if st.get("status") == "error":
                info["tool_errors"].append(f"{p.get('tool')}: {str(st.get('error') or st.get('output'))[:160]}")
        elif t == "step_finish":
            tk = p.get("tokens") or {}
            info["tokens"]["input"] += tk.get("input", 0)
            info["tokens"]["output"] += tk.get("output", 0)
            info["tokens"]["cache_read"] += (tk.get("cache") or {}).get("read", 0)
            info["reason"] = p.get("reason") or info["reason"]
    return info


def invoke(cli, d, meta, model, prompt, timeout, proxy, session=None, tag="dispatch"):
    log = d / f"run-{tag}.jsonl"
    err = d / f"run-{tag}.err"
    cmd = [cli, "run", "--auto", "--archived", "--format", "json", "--model", model, "--title", meta["task_id"]]
    if session:
        cmd += ["--session", session]
    cmd.append(prompt)
    env = dict(os.environ)
    env["PWD"] = str(d)
    env.pop("OLDPWD", None)
    if proxy:
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = proxy
    started = now()
    start_epoch = time.time()
    code, timed_out = 0, False
    with log.open("w", encoding="utf-8") as out, err.open("w", encoding="utf-8") as efp:
        proc = subprocess.Popen(cmd, cwd=str(d), env=env, stdout=out, stderr=efp,
                                encoding="utf-8", errors="replace")
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            timed_out = True
            code = -1
    info = parse_events(log)
    report = d / "report.md"
    fresh = report.exists() and report.stat().st_mtime >= start_epoch - 2
    allowed = [os.path.normcase(str(d)), os.path.normcase(str(meta.get("deliver_dir") or ""))]
    stray = [w for w in info["writes"] if not any(os.path.normcase(w).startswith(a) for a in allowed if a)]
    meta["model"] = model
    meta["session_id"] = info["session"] or meta.get("session_id")
    meta["status"] = "out-of-scope" if stray else ("delivered" if fresh else ("stale-report" if report.exists() else "no-report"))
    meta.setdefault("runs", []).append({
        "tag": tag, "at": started, "model": model, "exit": code, "timeout": timed_out,
        "tools": info["tools"], "tokens": info["tokens"], "tool_errors": info["tool_errors"][:3],
        "errors": info["errors"][:3], "stray_writes": stray[:5],
    })
    save_meta(d, meta)
    index_append(d.parent, meta, meta["status"], tag)
    tk = info["tokens"]
    print(f"TASK_ID: {meta['task_id']}")
    print(f"MODEL: {model}")
    print(f"EXIT: {code}{' (TIMEOUT)' if timed_out else ''}  TOOLS: {info['tools']}  SESSION: {meta['session_id']}")
    print(f"TOKENS: in={tk['input']} out={tk['output']} cache_read={tk['cache_read']}")
    print(f"REPORT: {'yes' if fresh else ('STALE(上一轮遗留)' if report.exists() else 'MISSING')}")
    if stray:
        print("OUT_OF_SCOPE: 写入了任务范围外的文件 -> " + " | ".join(stray[:3]))
    if info["tool_errors"]:
        print("TOOL_ERRORS: " + " | ".join(info["tool_errors"][:2]))
    err_text = err.read_text(encoding="utf-8", errors="replace")
    if code != 0 or not fresh:
        tail = err_text.strip().splitlines()[-6:]
        if tail:
            print("STDERR_TAIL: " + " / ".join(tail))
    if info["texts"]:
        print("LAST_TEXT: " + info["texts"][-1].strip().replace("\n", " ")[:240])
    haystack = " ".join([err_text, " ".join(info["errors"]), " ".join(info["texts"]), " ".join(info["tool_errors"])])
    if info["errors"]:
        print("ERROR_EVENT: " + " | ".join(info["errors"][:2]))
    if code == 0 and fresh and not stray and not info["tool_errors"] and not info["errors"]:
        cls, retryable, action, evidence = "none", False, "accept", ""
    else:
        cls, retryable, action, evidence = classify_failure(haystack, code, timed_out, fresh, stray)
        if cls == "no-report" and report.exists():
            cls, action = "stale-report", "re-dispatch"
    meta["failure_class"] = cls
    record_health(d.parent, model, cls)
    if cls != "none":
        meta["status"] = f"failed:{cls}"
        save_meta(d, meta)
        index_append(d.parent, meta, meta["status"], tag)
        print(f"FAILURE_CLASS: {cls}  RETRYABLE: {str(retryable).lower()}  ACTION: {action}")
        if evidence:
            print(f"EVIDENCE: {evidence}")
        if cls == "quota-daily":
            print("NOTE: 账号级每日免费额度耗尽，换其他免费模型通常同样失败；优先接管或上报等重置")
        if cls == "context-overflow":
            print("NOTE: 爆上下文，换模型无用；拆分子任务或精简契约后重派")
    print(f"LOG: {log}")
    return 0 if (code == 0 and fresh and not stray and cls == "none") else 2


def cmd_doctor(args):
    cli, src = find_cli()
    print(f"PYTHON: {sys.version.split()[0]}")
    if not cli:
        print("CLI: NOT FOUND")
        print("FIX_WINDOWS: 安装 OpenCode 桌面版（自带 resources/opencode-cli.exe），或 npm i -g opencode-ai")
        print("FIX_MAC_LINUX: curl -fsSL https://opencode.ai/install | bash")
        print("FIX_PROXY: 下载失败时设 HTTPS_PROXY=http://127.0.0.1:7897 后重试；或设 OPENCODE_CLI 指向已有可执行文件")
        return 3
    ver = run_cli(cli, ["--version"], timeout=60, proxy=args.proxy)
    print(f"CLI: {cli}")
    print(f"SOURCE: {src}  VERSION: {ver.stdout.strip() or ver.stderr.strip()[:80]}")
    models = list_models(cli, args.proxy)
    print(f"MODELS: {len(models)} available")
    try:
        dm = resolve_model(None, models)
        print(f"DEFAULT_MODEL: {dm}")
        lim = model_limits(dm)
        print(f"LIMITS: ctx={lim[0]} out={lim[1]} (snapshot {SNAPSHOT_AT})" if lim else "LIMITS: unknown，按 200K/32K 保守估")
        free = [m for m in models if m.endswith("-free") or m.split("/")[-1] in MODEL_LIMITS]
        print(f"FREE_MODELS: {len(free)}（中断时可作降级候选，跑 fallback 查看）")
    except SystemExit as e:
        print(f"DEFAULT_MODEL: UNRESOLVED ({e})")
    print(f"ROOT: {root_dir(args)}")
    if args.smoke:
        tmp = root_dir(args) / "_smoke"
        tmp.mkdir(parents=True, exist_ok=True)
        r = run_cli(cli, ["run", "--auto", "--archived", "--model", resolve_model(None, models),
                          "只回复两个字母：OK"], cwd=str(tmp), timeout=args.timeout, proxy=args.proxy)
        ok = "OK" in r.stdout
        print(f"SMOKE: {'PASS' if ok else 'FAIL'} {r.stdout.strip()[-120:] if ok else r.stderr.strip()[-200:]}")
        return 0 if ok else 4
    return 0


def cmd_models(args):
    cli, _ = find_cli()
    if not cli:
        raise SystemExit("未找到 opencode CLI，先跑 doctor")
    ms = list_models(cli, args.proxy)
    if args.filter:
        ms = [m for m in ms if args.filter.lower() in m.lower()]
    for m in ms:
        print(m)
    print(f"TOTAL: {len(ms)}")
    return 0


def cmd_new(args):
    root = root_dir(args)
    base = f"T{datetime.now():%Y%m%d-%H%M%S}-{stamp_slug(args.title)}"
    tid, n = base, 1
    while (root / tid).exists():
        n += 1
        tid = f"{base}-{n}"
    d = root / tid
    d.mkdir(parents=True)
    deliver = str(Path(args.deliver_dir).expanduser().resolve()) if args.deliver_dir else str(d / "out")
    Path(deliver).mkdir(parents=True, exist_ok=True)
    meta = {"task_id": tid, "title": args.title, "created_at": now(), "deliver_dir": deliver,
            "status": "planned", "session_id": None, "model": None, "runs": []}
    save_meta(d, meta)
    tpl = Path(__file__).resolve().parent.parent / "references" / "plan-template.md"
    body = tpl.read_text(encoding="utf-8") if tpl.exists() else "# 任务\n"
    body = (body.replace("{{TASK_ID}}", tid).replace("{{CREATED_AT}}", meta["created_at"])
                .replace("{{DELIVER_DIR}}", deliver).replace("{{TITLE}}", args.title))
    (d / "plan.md").write_text(body, encoding="utf-8")
    rtpl = Path(__file__).resolve().parent.parent / "references" / "report-template.md"
    if rtpl.exists():
        shutil.copyfile(rtpl, d / "report-template.md")
    stamp_plan(d, meta)
    print(f"TASK_ID: {tid}")
    print(f"TASK_DIR: {d}")
    print(f"PLAN: {d / 'plan.md'}")
    print(f"DELIVER_DIR: {deliver}")
    print("NEXT: 填写 plan.md 正文（保留 ROUTER 头部），然后 dispatch")
    return 0


def plan_prompt(d):
    return (f"读取 {d / 'plan.md'} 这个文件，严格按照其中的要求执行全部步骤。"
            f"完成后按 plan.md 的规定把 report.md 写到 {d / 'report.md'}（必须原样回写 TASK_ID）。"
            "只读这份 plan.md 与同目录的 report-template.md，不要读取其他目录的 plan.md、其他任务目录或历史台账。")


def cmd_limits(args):
    if args.model:
        lim = model_limits(args.model)
        if not lim:
            print(f"MODEL: {args.model}\nKNOWN: no（快照无此模型，按 200K/32K 保守估）")
            return 0
        print(f"MODEL: {args.model}\nCONTEXT: {lim[0]}\nOUTPUT: {lim[1]}\nSNAPSHOT_AT: {SNAPSHOT_AT}")
        return 0
    print(f"SNAPSHOT_AT: {SNAPSHOT_AT}（不保证更新，运行时以 models 与实际报错为准）")
    for k, (c, o) in sorted(MODEL_LIMITS.items(), key=lambda x: -x[1][0]):
        print(f"{k:32s} ctx={c:<8} out={o}")
    return 0


def cmd_budget(args):
    d = task_dir(root_dir(args), args.task)
    b = budget_of(d, args.files)
    print(f"TASK_ID: {d.name}")
    print(f"MODEL: {b['model']}  KNOWN_LIMITS: {str(b['known']).lower()}")
    print(f"CONTEXT: {b['ctx']}  OUTPUT: {b['out']}  SNAPSHOT_AT: {SNAPSHOT_AT}")
    print(f"EST: prefix+plan+template={b['base']} extra_files={b['extra']} total={b['total']}")
    print(f"WATERLINE: {b['usable']}（上下文的 {int(SAFE_WATERLINE*100)}%，其余留给工具输出与文件读取）")
    print(f"RATIO: {b['ratio']}  GRADE: {b['grade']}")
    if b["grade"] == "RED":
        print("ACTION: 拆分子任务或精简契约；大文件改为让 opencode 写脚本处理，不要读入上下文")
    elif b["grade"] == "YELLOW":
        print("ACTION: 限制读取范围、分文件写交付物、必要时拆阶段")
    else:
        print("ACTION: 可直接派单")
    return 0 if b["grade"] != "RED" else 3


def cmd_fallback(args):
    cli, _ = find_cli()
    if not cli:
        raise SystemExit("未找到 opencode CLI，先跑 doctor")
    root = root_dir(args)
    d = task_dir(root, args.task)
    meta = load_meta(d)
    models = list_models(cli, args.proxy)
    health = load_health(root)
    failed = (meta.get("model") or "").split("#")[0]
    bad = {"geo-restricted", "auth", "model-not-found"}
    cands = [m for m in models
             if m != failed and (m.endswith("-free") or m.split("/")[-1] in MODEL_LIMITS)
             and health.get(m, {}).get("status") not in bad]
    cands.sort(key=lambda m: (0 if health.get(m, {}).get("status") == "ok" else 1,
                              -(model_limits(m) or (0, 0))[0], m))
    if meta.get("failure_class") == "quota-daily":
        print("WARN: 账号级每日免费额度耗尽，换免费模型通常同样失败；建议接管或上报等重置")
    if meta.get("failure_class") == "context-overflow":
        print("WARN: 爆上下文应拆任务而非换模型；下列候选仅供需要更大窗口时参考")
    skipped = [m for m, v in health.items() if v.get("status") in bad]
    if skipped:
        print("SKIPPED(已知不可用): " + ", ".join(f"{m}({health[m]['status']})" for m in skipped))
    print(f"FAILED_MODEL: {failed or '-'}  FAILURE_CLASS: {meta.get('failure_class') or '-'}")
    for m in cands[:8]:
        lim = model_limits(m)
        print(f"CANDIDATE: {m}  ctx={lim[0] if lim else '?'} out={lim[1] if lim else '?'}"
              f"  health={health.get(m, {}).get('status', 'untested')}")
    if not cands:
        print("NO_CANDIDATE: 无可用免费模型，走接管或上报")
        return 4
    if getattr(args, "try_model", False):
        for m in cands[:3]:
            pick = m + "#high"
            print(f"TRYING: {pick}（新会话，不复用旧上下文）")
            rc = invoke(cli, d, meta, pick, plan_prompt(d), args.timeout, args.proxy, tag="fallback")
            if rc == 0:
                return 0
            meta = load_meta(d)
            if meta.get("failure_class") in ("quota-daily", "context-overflow"):
                print("STOP: 该失败换模型无用，转接管或上报")
                return 2
        print("EXHAUSTED: 候选均失败，转接管或上报")
        return 2
    print("NEXT: 选定后跑 dispatch --model <候选>，或加 --try 自动依次试跑（最多 3 个）")
    return 0


def cmd_dispatch(args):
    cli, _ = find_cli()
    if not cli:
        raise SystemExit("未找到 opencode CLI，先跑 doctor")
    root = root_dir(args)
    d = task_dir(root, args.task)
    meta = load_meta(d)
    stamp_plan(d, meta)
    model = resolve_model(args.model or meta.get("model"), list_models(cli, args.proxy))
    meta["model"] = model
    save_meta(d, meta)
    if not args.force:
        b = budget_of(d, args.files)
        print(f"BUDGET: ctx={b['ctx']} out={b['out']} est_input={b['total']} waterline={b['usable']} ratio={b['ratio']} {b['grade']}"
              + ("" if b["known"] else " (模型上限未知，按 200K 保守估)"))
        if b["grade"] == "RED":
            print("BLOCKED: 契约+预期读取量超过安全水位，派单已阻止")
            print("ACTION: 拆成多个子任务（各自 TASK_ID），或精简 plan、改为让 opencode 写脚本处理大文件而非读入上下文；确需强推加 --force")
            return 3
        if b["grade"] == "YELLOW":
            print("WARN: 上下文余量偏紧，建议限制 opencode 的读取范围、分文件写交付物")
    prompt = args.prompt or plan_prompt(d)
    return invoke(cli, d, meta, model, prompt, args.timeout, args.proxy, tag="dispatch")


def cmd_revise(args):
    cli, _ = find_cli()
    if not cli:
        raise SystemExit("未找到 opencode CLI，先跑 doctor")
    root = root_dir(args)
    d = task_dir(root, args.task)
    meta = load_meta(d)
    note = d / args.note
    if not note.exists():
        raise SystemExit(f"返工说明不存在：{note}")
    model = resolve_model(args.model or meta.get("model"), list_models(cli, args.proxy))
    prompt = (f"这是返工轮次。读取 {note} 这个文件，只处理其中列出的问题，"
              f"不要重做已完成部分。完成后更新 {d / 'report.md'}（保留 TASK_ID 头部，追加返工记录）。")
    return invoke(cli, d, meta, model, prompt, args.timeout, args.proxy,
                  session=meta.get("session_id"), tag=f"revise-{len(meta.get('runs', []))}")


def cmd_verify(args):
    root = root_dir(args)
    d = task_dir(root, args.task)
    meta = load_meta(d)
    fails, lines = [], []
    rp = d / "report.md"
    if not rp.exists():
        fails.append("report.md 缺失")
        report = ""
    else:
        report = rp.read_text(encoding="utf-8", errors="replace")
        m = TASK_ID_RE.search(report)
        if not m:
            fails.append("report.md 未回写 TASK_ID")
        elif m.group(1) != meta["task_id"]:
            fails.append(f"TASK_ID 串号：report={m.group(1)} plan={meta['task_id']}")
        else:
            lines.append(f"TASK_ID 对齐: {m.group(1)}")
        if len(report.strip()) < 80:
            fails.append("report.md 内容过短，疑似敷衍")
    plan = (d / "plan.md").read_text(encoding="utf-8") if (d / "plan.md").exists() else ""
    delivers = [next(g for g in m if g) for m in DELIVER_RE.findall(plan)]
    if not delivers:
        fails.append("plan.md 未声明交付物路径（## 交付物 小节每行以 - 绝对路径 开头）")
    for raw in delivers:
        p = Path(raw.rstrip(".,;，。"))
        if not p.exists():
            fails.append(f"交付物缺失: {p}")
        elif p.is_file() and p.stat().st_size == 0:
            fails.append(f"交付物为空: {p}")
        else:
            lines.append(f"交付物存在: {p} ({p.stat().st_size if p.is_file() else 'dir'} bytes)")
    if args.run_checks:
        for c in CHECK_RE.findall(plan):
            try:
                r = subprocess.run(shlex.split(c), cwd=str(d), capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=args.check_timeout)
                ok = r.returncode == 0
                lines.append(f"CHECK {'PASS' if ok else 'FAIL'}: {c} -> {(r.stdout or r.stderr).strip()[-120:]}")
                if not ok:
                    fails.append(f"CHECK 失败: {c}")
            except Exception as e:
                fails.append(f"CHECK 无法执行: {c} ({e})")
    meta["status"] = "verified" if not fails else "failed"
    meta["verified_at"] = now()
    save_meta(d, meta)
    index_append(root, meta, meta["status"], "verify")
    print(f"TASK_ID: {meta['task_id']}")
    for l in lines[:10]:
        print(l)
    if fails:
        print("RESULT: FAIL")
        for f in fails[:8]:
            print(" - " + f)
        return 1
    print("RESULT: PASS（结构校验通过，语义验收仍需 Qoder 读 report.md）")
    return 0


def cmd_takeover(args):
    root = root_dir(args)
    d = task_dir(root, args.task)
    meta = load_meta(d)
    meta["executor"] = "qoder-takeover"
    meta["takeover_note"] = args.note
    meta["takeover_at"] = now()
    meta["status"] = "takeover"
    save_meta(d, meta)
    index_append(root, meta, "takeover", args.note[:40])
    print(f"TASK_ID: {meta['task_id']}")
    print("EXECUTOR: qoder-takeover")
    print(f"LAST_FAILURE: {meta.get('failure_class') or '-'}")
    print("NEXT: Qoder 完成剩余步骤 → 亲自写 report.md（保留 TASK_ID、ROUND+1、加 EXECUTOR: qoder-takeover、追加接管记录）→ verify")
    return 0


def cmd_index(args):
    root = root_dir(args)
    metas = []
    for p in sorted(root.glob("T*/meta.json")):
        try:
            metas.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    f = root / "INDEX.md"
    f.write_text(
        "# OpenCode 外包台账\n\n"
        "> 本页由 router.py 自动维护，供人阅读溯源；Qoder 侧默认不读本页。\n\n"
        "| 任务编号 | 标题 | 创建时间 | 模型 | 状态 | 交付目录 |\n|---|---|---|---|---|---|\n",
        encoding="utf-8")
    with f.open("a", encoding="utf-8") as fh:
        for m in metas:
            chain = []
            for r in m.get("runs", []):
                v = (r.get("model") or "").replace("opencode/", "")
                if v and v not in chain:
                    chain.append(v)
            model = " → ".join(chain) or (m.get("model") or "-").replace("opencode/", "")
            fh.write(f"| {m['task_id']} | {m.get('title','')} | {m.get('created_at','')} | "
                     f"{model} | {m.get('status','')} | {m.get('deliver_dir','')} |\n")
    print(f"INDEX: {f}")
    print(f"TASKS: {len(metas)}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="router.py", description="Qoder -> opencode 外包路由器")
    ap.add_argument("--root", help="任务工作区根目录（默认 ./opencode-tasks）")
    ap.add_argument("--proxy", help="给 opencode 子进程设 HTTP(S)_PROXY，如 http://127.0.0.1:7897")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor", help="检测 CLI/模型/默认模型是否可用")
    p.add_argument("--smoke", action="store_true", help="额外跑一次极简连通性测试")
    p.add_argument("--timeout", type=int, default=180)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("models", help="列出 opencode 可用模型")
    p.add_argument("--filter", help="按关键字过滤，如 deepseek")
    p.set_defaults(fn=cmd_models)

    p = sub.add_parser("new", help="开新任务目录并生成 plan.md 骨架")
    p.add_argument("--title", required=True)
    p.add_argument("--deliver-dir", help="交付物目录（绝对路径），默认 <任务目录>/out")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("limits", help="查看模型上下文/输出上限（本地快照）")
    p.add_argument("--model", help="只看某个模型")
    p.set_defaults(fn=cmd_limits)

    p = sub.add_parser("budget", help="估算任务上下文占用并给出分配建议")
    p.add_argument("--task", required=True)
    p.add_argument("--files", nargs="*", default=[], help="计划让 opencode 读入的文件，计入估算")
    p.set_defaults(fn=cmd_budget)

    p = sub.add_parser("fallback", help="列出其他免费模型候选，可选自动试跑")
    p.add_argument("--task", required=True)
    p.add_argument("--try", dest="try_model", action="store_true", help="用第一个候选新会话重派")
    p.add_argument("--timeout", type=int, default=900)
    p.set_defaults(fn=cmd_fallback)

    p = sub.add_parser("dispatch", help="派单给 opencode 执行 plan.md")
    p.add_argument("--task", required=True)
    p.add_argument("--model", help="模型，如 'deepseek flash low' 或 provider/model#variant")
    p.add_argument("--prompt", help="覆盖默认派单提示词")
    p.add_argument("--files", nargs="*", default=[], help="计划让 opencode 读入的文件，计入预算")
    p.add_argument("--force", action="store_true", help="越过上下文预算红线")
    p.add_argument("--timeout", type=int, default=900)
    p.set_defaults(fn=cmd_dispatch)

    p = sub.add_parser("revise", help="同会话返工，复用缓存前缀")
    p.add_argument("--task", required=True)
    p.add_argument("--note", required=True, help="任务目录内的返工说明文件名，如 revision-01.md")
    p.add_argument("--model")
    p.add_argument("--timeout", type=int, default=900)
    p.set_defaults(fn=cmd_revise)

    p = sub.add_parser("verify", help="结构校验：TASK_ID 对齐 + 交付物存在")
    p.add_argument("--task", required=True)
    p.add_argument("--run-checks", action="store_true", help="执行 plan.md 中 CHECK: 声明的命令")
    p.add_argument("--check-timeout", type=int, default=120)
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("takeover", help="标记由 Qoder 接管完成（中断后）")
    p.add_argument("--task", required=True)
    p.add_argument("--note", required=True, help="接管原因一句话")
    p.set_defaults(fn=cmd_takeover)

    p = sub.add_parser("index", help="重建用户可读台账 INDEX.md")
    p.set_defaults(fn=cmd_index)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
