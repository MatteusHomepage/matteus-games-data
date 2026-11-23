import random
import re

import core
import wiki

RECALL_BASE = {1: 1.4, 2: 2.1, 3: 2.9, 4: 3.8, 5: 4.6}


def norm_q(q):
    return re.sub(r"[^a-z0-9 ]+", "", q.lower()).strip()


def key_of(q):
    return "auto." + norm_q(q).replace(" ", "-")[:70]


def gather(q, spec, cfg, log):
    msl = int(cfg.get("auto_min_sl", 3))
    limit = int(cfg.get("max_answers", 6000))
    rows = []
    src = []
    names = spec.get("names", [])
    g = wiki.ground(names, 2) if names else {}
    if g:
        rows += wiki.rows_from_grounded(g)
        src.append("names %d" % len(g))
    ids = []
    try:
        ids = wiki.class_ids(spec.get("classes", []))
    except Exception as e:
        log("   class lookup failed: %s" % e)
    if ids:
        try:
            cr = wiki.class_rows(ids, msl, limit)
            rows += cr
            src.append("classes %d" % len(cr))
        except Exception as e:
            log("   class query failed: %s" % e)
    for page in spec.get("lists", [])[:3]:
        ts = wiki.list_titles(page)
        if ts:
            lr = wiki.title_rows(ts, msl)
            rows += lr
            src.append("list %s %d" % (page, len(lr)))
    return rows, src, g


def profile(aq, llm, cfg, log):
    q = aq["q"]
    sp = llm.spec(q)
    if not sp:
        return None
    rows, src, g = gather(q, sp, cfg, log)
    seen = set()
    uniq = []
    for r in rows:
        if r["i"] in seen:
            continue
        seen.add(r["i"])
        uniq.append(r)
    ans = core.clean_answers(uniq, skip_names=[])
    if len(ans) < int(cfg.get("auto_min_answers", 100)):
        log("   too few answers (%d) for: %s" % (len(ans), q))
        return None
    ans = ans[: int(cfg.get("max_answers", 6000))]
    top = sorted((x["sl"] for x in ans), reverse=True)[:5]
    p = {
        "scale": 1.0,
        "key": aq.get("key") or key_of(q),
        "cat": aq["cat"],
        "fam": "a" + core.b36(int(__import__("hashlib").md5(norm_q(q).encode()).hexdigest()[:6], 16), 4),
        "sub": "x",
        "vl": q,
        "ans": ans,
        "q": q,
        "n": len(ans),
        "level": None,
        "auto": True,
        "src": src,
        "hint": aq.get("recall", 3),
        "obvious": [n for n in sp.get("names", [])[:25] if n in g],
    }
    return p


def tail_sample(ans, k=12):
    n = len(ans)
    if n < 80:
        return []
    idx = list(range(40, n))
    rnd = random.Random(n * 7 + ans[0]["sl"])
    pick = rnd.sample(idx, min(k, len(idx)))
    return [ans[i]["n"] for i in sorted(pick)]


def level_for(p, recall, cfg):
    ans = p["ans"]
    base = RECALL_BASE.get(int(recall), 2.9)
    cfg2 = dict(cfg)
    cfg2["min_answers"] = {k: min(v, 100) for k, v in cfg["min_answers"].items()} if cfg.get("auto_relax", True) else cfg["min_answers"]
    lvl = core.level_of(ans, cfg2, 1.0, base, 0.0)
    if not lvl:
        return None
    t5 = sorted((x["sl"] for x in ans), reverse=True)[:5]
    top5 = sum(t5) / max(1, len(t5))
    n30 = sum(1 for x in ans if x["sl"] >= 30)
    p["n30"] = n30
    i = core.LEVELS.index(lvl)
    if i == 0 and (top5 < 60 or n30 < 18):
        i = 1
    if i == 1 and (top5 < 40 or n30 < 10):
        i = 2
    if i == 2 and n30 < 5:
        i = 3
    return core.LEVELS[i]
