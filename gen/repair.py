import json
import os
import queue
import re
import threading
import time

import core
import quality
import rescue
from providers import NoProvider

BASE = core.BASE
PRIO_LETTER = re.compile(r"\b(?:starts?|starting|begins?|beginning) with\b", re.I)


def static_items():
    p = os.path.join(BASE, "static_bank.json")
    if not os.path.exists(p):
        return []
    out = []
    for r in json.load(open(p, encoding="utf-8")):
        out.append({"kind": "static", "id": r[0], "cat": r[1], "lvl": r[2], "text": r[3], "names": r[4], "fam": r[6], "sub": r[7]})
    return out


def generated_items(out):
    where = rescue.manifest_index(out)
    items = []
    files = {}
    for qid, (f, cat, lvl) in where.items():
        files.setdefault(f, []).append((qid, cat, lvl))
    for f, lst in files.items():
        path = os.path.join(out, f)
        try:
            raw = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        for qid, cat, lvl in lst:
            for it in raw.get(cat, {}).get(lvl, []):
                if it[0] == qid:
                    items.append({"kind": "gen", "id": qid, "cat": cat, "lvl": lvl, "text": it[1], "names": it[2], "fam": it[4], "sub": it[5], "file": f})
                    break
    return items


def priority(it):
    n = len(it["names"])
    p = n
    if PRIO_LETTER.search(it["text"]):
        p -= 25
    if n < 40:
        p -= 100
    return p


def todo_list(st, cfg, out):
    ver = int(cfg.get("repair_version", 1))
    fixed = st.setdefault("fixed", {})
    items = static_items() + generated_items(out)
    todo = [it for it in items if fixed.get(it["id"], 0) < ver]
    todo.sort(key=priority)
    return todo, len(items)


def process(it, llm, cfg, log, st, out, lock):
    q = it["text"]
    ans = quality.to_ans(it["names"])
    old_n = len(ans)
    new, s = quality.improve(llm, q, ans, cfg, log, level=it["lvl"])
    if s["survey"] == 0:
        return "nolm"
    cap = int(cfg.get("repair_max_answers", 2500))
    new = new[:cap]
    minimum = int(cfg.get("repair_min", 30))
    ver = int(cfg.get("repair_version", 1))
    cov = ("%d of %d common answers were there" % (s["covered"], s.get("top", 0))) if s.get("top") else "no survey"
    if len(new) < minimum:
        with lock:
            if it["kind"] == "static":
                st.setdefault("hide_new", []).append(it["id"])
            st["fixed"][it["id"]] = ver
        log("   retired (only %d answers possible): %s" % (len(new), q))
        return "hide"
    if it["kind"] == "static":
        qid = it["id"] + "x%d" % ver
        item = core.encode_question(qid, q, new, cfg, it["fam"], it["sub"])
        entry = {"cat": it["cat"], "lvl": it["lvl"], "lv": [it["lvl"]], "item": item, "key": "fix." + it["id"], "n": len(new), "sig": [core.norm(a["n"]) for a in new[:30]]}
        with lock:
            st["pending"].append(entry)
            st.setdefault("hide_new", []).append(it["id"])
            st["fixed"][it["id"]] = ver
            st["fixed"][qid] = ver
    else:
        with lock:
            path = os.path.join(out, it["file"])
            raw = json.load(open(path, encoding="utf-8"))
            for row in raw.get(it["cat"], {}).get(it["lvl"], []):
                if row[0] == it["id"]:
                    enc = core.encode_question(it["id"], q, new, cfg, row[4], row[5])
                    row[2] = enc[2]
                    row[3] = enc[3]
                    break
            tmp = path + ".tmp"
            json.dump(raw, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)
            st["fixed"][it["id"]] = ver
            st["dirty"] = True
    log("   fixed %-10s %4d -> %4d answers, %s, moved %d, aliases +%d: %s" % (it["lvl"], old_n, len(new), cov, s["moved"], s["aliases"], q))
    return "ok"


def run(st, cfg, llm, log, out, minutes, flush, wlock, workers):
    todo, total = todo_list(st, cfg, out)
    if not todo:
        log("repair: all %d questions are already checked" % total)
        return 0
    log("repair: %d of %d questions still to check" % (len(todo), total))
    core.GAP[0] = min(core.GAP[0], float(cfg.get("repair_gap", 1.0)))
    deadline = time.time() + minutes * 60
    jobs = queue.Queue()
    for it in todo:
        jobs.put(it)
    state = {"done": 0, "stop": False, "noai": False, "nolm": 0}
    every = int(cfg.get("publish_every", 8))

    def worker():
        while not state["stop"] and time.time() < deadline:
            try:
                it = jobs.get_nowait()
            except queue.Empty:
                return
            try:
                r = process(it, llm, cfg, log, st, out, wlock)
                if r == "nolm":
                    state["nolm"] += 1
                    if state["nolm"] >= 6:
                        state["stop"] = True
                        state["noai"] = True
                else:
                    state["nolm"] = 0
                    with wlock:
                        state["done"] += 1
                        if len(st["pending"]) >= every or len(st.get("hide_new", [])) >= every or st.get("dirty"):
                            flush(st, cfg, log)
            except NoProvider:
                state["stop"] = True
                state["noai"] = True
            except Exception as e:
                log("repair problem with one question, skipped: %s" % e)

    ths = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, workers))]
    for t in ths:
        t.start()
    last = time.time()
    while any(t.is_alive() for t in ths):
        time.sleep(1)
        if time.time() - last > 600:
            last = time.time()
            log("repair progress: %d checked, %d left" % (state["done"], jobs.qsize()))
    with wlock:
        flush(st, cfg, log)
    if state["noai"]:
        log("repair stopped, the free AI requests are used up for now. The next run continues.")
    log("repair: %d questions checked this run, %d left" % (state["done"], jobs.qsize()))
    return state["done"]
