import hashlib
import json
import os
import random
import re
import queue
import sys
import threading
import time

import core
import recipes
from llm import LLM
import krill
import auto
import quality
import wiki

BASE = core.BASE
STATE = os.path.join(BASE, "state.json")
PROF = os.path.join(core.CACHE, "profiles")
os.makedirs(PROF, exist_ok=True)

THE = {
    "United States of America", "United Kingdom", "Netherlands", "Philippines", "Czech Republic", "Bahamas",
    "Gambia", "Maldives", "Comoros", "Seychelles", "Marshall Islands", "Solomon Islands", "Cayman Islands",
    "Central African Republic", "Democratic Republic of the Congo", "Republic of the Congo",
    "United Arab Emirates", "Soviet Union", "Faroe Islands", "Vatican City", "United States",
}


def state_path(cfg=None):
    cfg = cfg or {}
    d = cfg.get("state_dir")
    if d:
        d = d if os.path.isabs(d) else os.path.join(BASE, d)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "state.json")
    return STATE


def blank_state():
    return {"done": {}, "counts": {}, "pending": [], "version": 0, "batches": {}, "sigs": [], "texts": [], "rej_done": {}}


def load_state(cfg=None):
    p = state_path(cfg)
    if os.path.exists(p):
        st = json.load(open(p, encoding="utf-8"))
        for k, v in blank_state().items():
            st.setdefault(k, v)
        return st
    return blank_state()


def save_state(st, cfg=None):
    p = state_path(cfg or st.get("_cfg"))
    tmp = p + ".tmp"
    json.dump({k: v for k, v in st.items() if not k.startswith("_")}, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)


def exists_sigs():
    p = os.path.join(BASE, "existing.json")
    rows = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
    return [(r[0], r[1], set(r[3])) for r in rows]


def dup(sigs, top):
    a = set(top[:30])
    if not a:
        return True
    for _, _, b in sigs:
        m = min(len(a), len(b))
        if m and len(a & b) / m >= 0.6:
            return True
    return False


def values(r, f):
    if f["kind"] == "custom":
        out = []
        for p in f["params"]:
            try:
                tok = p[1]
                res = core.resolve(tok[1:]) if tok.startswith("@") else tok
            except Exception:
                continue
            out.append({"v": res, "label": p[0], "n": 0, "rk": 99, "add": p[2] if len(p) > 2 else 0.0})
        random.Random(r["key"] + f["key"]).shuffle(out)
        return out
    if f["kind"] == "letter":
        L = list("ABCDEFGHIJKLMNOPRSTUVW")
        random.Random(r["key"]).shuffle(L)
        return [{"v": x, "label": x, "n": 0, "rk": 99} for x in L[: f["top"]]]
    base = r["pat"]
    if f["kind"] == "regex":
        return [{"v": f["key"], "label": f["key"], "n": 0, "rk": 99}]
    if f["kind"] == "decade":
        q = (
            "SELECT ?dec (COUNT(DISTINCT ?i) AS ?n) WHERE { %s ?i wdt:%s ?d . ?i wikibase:sitelinks ?sl . FILTER(?sl >= %d) "
            "BIND(FLOOR(YEAR(?d)/10)*10 AS ?dec) } GROUP BY ?dec HAVING (COUNT(DISTINCT ?i) >= %d) ORDER BY DESC(?n) LIMIT 40"
            % (base, f["prop"], r["min_sl"], f["min_n"])
        )
        rows = core.sparql(q)
        out = []
        for x in rows:
            y = int(float(x["dec"]))
            if 1900 <= y <= 2020:
                out.append({"v": str(y), "label": str(y), "n": int(float(x["n"])), "rk": 99})
        return out[: f["top"]]
    q = (
        "SELECT ?v ?vl (MAX(?vsl) AS ?vs) (COUNT(DISTINCT ?i) AS ?n) WHERE { %s ?i wdt:%s ?v . ?i wikibase:sitelinks ?sl . FILTER(?sl >= %d) "
        "?v rdfs:label ?vl . FILTER(LANG(?vl) = \"en\") OPTIONAL { ?v wikibase:sitelinks ?vsl } } GROUP BY ?v ?vl HAVING (COUNT(DISTINCT ?i) >= %d) "
        "ORDER BY DESC(?n) LIMIT 300" % (base, f["prop"], r["min_sl"], f["min_n"])
    )
    rows = core.sparql(q)
    byn = sorted(rows, key=lambda x: -int(float(x["n"])))
    rank = {x["v"]: i for i, x in enumerate(byn)}
    rows = sorted(rows, key=lambda x: -int(float(x.get("vs") or 0)))
    out = []
    for x in rows:
        if core.BAD_LABEL.search(x["vl"]) or len(x["vl"]) > 45:
            continue
        if f.get("ok") and not re.search(f["ok"], x["vl"]):
            continue
        out.append({"v": x["v"].rsplit("/", 1)[-1], "label": x["vl"], "n": int(float(x["n"])), "vs": int(float(x.get("vs") or 0)), "rk": rank[x["v"]]})
    out = out[: f["top"] * 2]
    random.Random(f["key"] + str(len(out))).shuffle(out)
    return out[: f["top"]]


SV_CLAUSE = "{ ?i wdt:P27 wd:Q34 } UNION { ?i wdt:P17 wd:Q34 } UNION { ?i wdt:P495 wd:Q34 } UNION { ?i wdt:P159/wdt:P17 wd:Q34 } UNION { ?i wdt:P740/wdt:P17 wd:Q34 }"


def sv_ok(r, f):
    return bool(r.get("sv")) and bool(f.get("sv", True)) and f["kind"] != "regex"


def answers_query(r, f, v, cfg, sv=False):
    parts = [r["pat"]]
    if sv:
        parts.append(SV_CLAUSE)
    if f["kind"] == "entity":
        parts.append("?i wdt:%s wd:%s ." % (f["prop"], v["v"]))
    elif f["kind"] == "decade":
        y = int(v["v"])
        parts.append("?i wdt:%s ?d . FILTER(YEAR(?d) >= %d && YEAR(?d) < %d)" % (f["prop"], y, y + 10))
    msl = max(2, int(round(r["min_sl"] * float(cfg.get("breadth", 0.5)))))
    parts.append("?i wikibase:sitelinks ?sl . FILTER(?sl >= %d)" % (max(2, msl // 3) if sv else msl))
    if r["label"] == "l":
        parts.append("?i rdfs:label ?l . FILTER(LANG(?l) = \"en\") FILTER NOT EXISTS { ?i wdt:P225 ?tn . FILTER(STR(?tn) = STR(?l)) }")
    else:
        parts.append("FILTER(LANG(?l) = \"en\")")
    if f["kind"] == "letter":
        parts.append("FILTER(STRSTARTS(UCASE(?l), \"%s\"))" % v["v"])
    if f["kind"] == "regex":
        parts.append("FILTER(REGEX(?l, \"%s\", \"i\"))" % f["rx"])
    if f["kind"] == "custom" and f["frag"]:
        parts.append(f["frag"].replace("{v}", v["v"]))
    nw = "?nw" if "?nw" in r["pat"] else ""
    return (
        "SELECT ?i ?l ?sl %s (GROUP_CONCAT(DISTINCT ?al; separator=\"|\") AS ?als) WHERE { %s "
        "OPTIONAL { ?i skos:altLabel ?al . FILTER(LANG(?al) = \"en\") } } GROUP BY ?i ?l ?sl %s ORDER BY DESC(?sl) LIMIT %d"
        % (nw, " ".join(parts), nw, cfg["max_answers"])
    )


def art(s):
    return ("an " if re.match(r"^(?!uni|eu|one|us[ei])[aeiouAEIOU]", s) else "a ") + s


def phrase(r, f, v, key):
    h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
    lab = v["label"]
    if f["prop"] in ("P17", "P27", "P495") and lab in THE:
        lab = "the " + lab
    lab = re.sub(r"^the (World War)", r"\1", lab)
    t = f["tpl"]
    multi = isinstance(t, list)
    if multi:
        t = t[h % len(t)]
    s = r.get("s") or r.get("noun") or ""
    t = t.replace("{a}", art(s)).replace("{s}", s).replace("{P}", r.get("P") or s).replace("{w}", f.get("w_", "")).replace("{v}", lab)
    t = re.sub(r"\bthe World War", "World War", t)
    if not multi and t.startswith("Name ") and (h >> 4) % 100 < 40:
        k = (h >> 12) % 5
        body = t[5:]
        if k == 0:
            t = "Think of " + body
        elif k == 1:
            t = "Give me " + body
        elif k == 2:
            t = "Can you name " + body.rstrip(".") + "?"
        elif k == 3:
            t = "Try to name " + body
        else:
            t = "Quick, name " + body
    t = re.sub(r"\b(Name|Think of|Give me|Can you name|Try to name|Quick, name) a ((?!uni|eu|one|us[ei])[AEIOUaeiou])", r"\1 an \2", t)
    t = re.sub(r"\s+", " ", t).replace(" .", ".").replace(" ?", "?")
    return t[0].upper() + t[1:]


KEEP = {"animal", "bird", "mammal", "plant", "bcity", "bfilm", "bgame", "bfood"}


def load_recipes():
    keep = [r for r in recipes.R if r["key"] in KEEP]
    for r in keep:
        r["w"] = r.get("w", 1.0) * 0.4
        r["sv"] = r["key"] in {"bcity", "bfilm", "bgame", "bfood"}
    recipes.R[:] = keep
    try:
        recipes.R.extend(krill.build())
    except Exception as e:
        print("could not load curated families: %s" % e)
    for k, e in krill.MISSING:
        print("skipped %s: %s" % (k, e))


load_recipes()


def candidates():
    out = []
    for r in recipes.R:
        for f in r["facets"]:
            out.append((r, f))
    return out


def cand_key(r, f, v):
    return "%s.%s.%s" % (r["key"], f["key"], v["v"])


def scale_of(r):
    pf = os.path.join(PROF, "scale-" + r["key"] + ".json")
    if os.path.exists(pf):
        return json.load(open(pf))["s"]
    rows = core.sparql("SELECT ?sl WHERE { %s ?i wikibase:sitelinks ?sl . FILTER(?sl >= %d) } ORDER BY DESC(?sl) LIMIT 25" % (r["pat"], r["min_sl"]))
    ref = int(float(rows[-1]["sl"])) if rows else 150
    s = max(0.25, min(2.0, ref / 150.0))
    json.dump({"s": s, "ref": ref}, open(pf, "w"))
    return s


PV = "v5"


def head_sl(ans, n):
    return sorted((x["sl"] for x in ans), reverse=True)[:n]


def assess(r, f, v, p, cfg):
    ans = p["ans"]
    if len(ans) < 100:
        return None
    sc = p["scale"]
    rk = v.get("rk", 99)
    adj = -0.7 if rk < 5 else (-0.35 if rk < 15 else (0.4 if rk >= 40 and rk != 99 else 0.0))
    if f["kind"] == "letter":
        adj += core.LETTER_ADJ.get(v["v"], 0.0)
    cfg2 = cfg
    if r.get("minn"):
        cfg2 = dict(cfg)
        cfg2["min_answers"] = {k: max(100, r["minn"]) for k in cfg["min_answers"]}
    lvl = core.level_of(ans, cfg2, sc, f["base"] + v.get("add", 0.0), adj)
    if not lvl:
        return None
    t5 = head_sl(ans, 5)
    top5 = sum(t5) / max(1, len(t5))
    k = max(0.35, min(1.0, sc))
    n30 = sum(1 for x in ans if x["sl"] >= 30 * k)
    p["n30"] = n30
    i = core.LEVELS.index(lvl)
    if top5 >= 100:
        i = min(i, 3)
    if i == 0 and (top5 < 60 * k or n30 < 18):
        i = 1
    if i == 1 and (top5 < 40 * k or n30 < 10):
        i = 2
    if i == 2 and n30 < 5:
        i = 3
    return core.LEVELS[i]


def profile(r, f, v, cfg):
    key = cand_key(r, f, v)
    svon = sv_ok(r, f)
    qq = answers_query(r, f, v, cfg)
    sq = answers_query(r, f, v, cfg, True) if svon else ""
    pf = os.path.join(PROF, PV + "-" + key.replace("/", "_") + "-" + hashlib.md5((qq + sq).encode()).hexdigest()[:8] + ".json")
    if os.path.exists(pf):
        p = json.load(open(pf, encoding="utf-8"))
    else:
        rows = core.sparql(qq)
        srows = []
        if sq:
            try:
                srows = core.sparql(sq)
            except Exception:
                srows = []
        ans = core.clean_answers(rows, skip_names=[v["label"]], sv_rows=srows)
        p = {"scale": scale_of(r), "key": key, "cat": r["cat"], "fam": r["key"], "sub": r["key"] + "." + f["key"], "vl": v["label"], "ans": ans}
        json.dump(p, open(pf, "w", encoding="utf-8"), ensure_ascii=False)
    p["n"] = len(p["ans"])
    p["level"] = assess(r, f, v, p, cfg)
    p["q"] = phrase(r, f, v, key)
    return p


def cell_counts(sigs, st):
    c = {}
    for cat, lvl, _ in sigs:
        c[(cat, lvl)] = c.get((cat, lvl), 0) + 1
    for k, n in st["counts"].items():
        cat, lvl = k.split(".")
        c[(cat, lvl)] = c.get((cat, lvl), 0) + n
    return c


def build_queue(cfg, st, log):
    queue = []
    pool = candidates()
    random.shuffle(pool)
    return pool


def build_index(ans, limit=500):
    ex = {}
    pre = []
    for i, a in enumerate(ans):
        for nm in [a["n"]] + a["al"]:
            k = core.fold(nm)
            if k:
                ex.setdefault(k, i)
        if i < limit:
            pre.append((i, core.fold(a["n"])))
    return ex, pre


def match_recalled(rec, ans):
    ex, pre = build_index(ans)
    found = []
    seen = set()
    for r in rec:
        k = core.fold(r)
        if not k:
            continue
        i = ex.get(k)
        if i is None and k.endswith("s") and len(k) > 4:
            i = ex.get(k[:-1])
        if i is None and not k.endswith("s"):
            i = ex.get(k + "s")
        if i is None and len(k) >= 4:
            best = None
            for j, nm in pre:
                if nm.startswith(k + " ") or (len(k.split()) == 1 and nm.endswith(" " + k)) or (len(nm) >= 4 and k.startswith(nm + " ")):
                    best = j
                    break
            i = best
        if i is None and len(k) >= 6:
            import difflib
            for j, nm in pre:
                if abs(len(nm) - len(k)) <= 2 and difflib.SequenceMatcher(None, k, nm).ratio() >= 0.9:
                    i = j
                    break
        if i is not None and ans[i]["id"] not in seen:
            seen.add(ans[i]["id"])
            found.append(ans[i])
    return found


def raise_level(p, d, log):
    cur = core.LEVELS.index(p["level"])
    floor = {1: 0, 2: 0, 3: 1, 4: 2, 5: 3}.get(d["recall"], 1)
    if not d.get("ten", True):
        floor = max(floor, 1)
    if not d["words_known"]:
        floor = max(floor, 2)
    new = max(cur, floor)
    log("   AI grade: recall %d, ten answers %s, words %s -> %s%s" % (d["recall"], "yes" if d.get("ten", True) else "no", "known" if d["words_known"] else "unfamiliar", core.LEVELS[new], " (was %s)" % core.LEVELS[cur] if new != cur else ""))
    return core.LEVELS[new]


def add_recalled(ans, rec, cfg, log):
    ex, pre = build_index(ans)
    byid = {a["id"]: a for a in ans}
    found = []
    seen = set()
    miss = []
    for r in rec:
        hit = match_recalled([r], ans)
        if hit:
            a = hit[0]
            if a["id"] not in seen:
                seen.add(a["id"])
                found.append(a)
        else:
            miss.append(r)
    added = 0
    if miss:
        g = wiki.ground(miss[:30], 3)
        for r in miss:
            if r not in g:
                continue
            qid, sl, lab = g[r]
            if qid in byid:
                a = byid[qid]
                if core.fold(r) not in {core.fold(x) for x in [a["n"]] + a["al"]} and len(a["al"]) < 8:
                    a["al"].append(r)
                if a["id"] not in seen:
                    seen.add(a["id"])
                    found.append(a)
                continue
            a = {"n": r, "al": [], "sl": sl, "k": sl, "sv": False, "nw": 0, "id": qid}
            byid[qid] = a
            seen.add(qid)
            found.append(a)
            added += 1
    return found, seen, added


def refine(llm, p, cfg, log):
    ans = p["ans"]
    head = ans[:int(cfg.get("likely_names", 40))]
    names = [a["n"] for a in head]
    q = p["q"]
    tail = auto.tail_sample(ans)
    d = llm.review(q, names[:15], tail)
    if d is None:
        log("   AI check gave no usable answer, skipped")
        return None
    if not d["keep"] or d["fun"] < 3:
        log("   AI rejected (keep=%s fun=%s): %s" % (d["keep"], d["fun"], q))
        return None
    if tail and d["misfits"]:
        bad = {core.fold(x) for x in d["misfits"]}
        share = len([t for t in tail if core.fold(t) in bad]) / float(len(tail))
        if share > float(cfg.get("max_misfit", 0.25)):
            log("   AI says too many answers do not fit (%d%%): %s" % (share * 100, q))
            return None
        if bad:
            ans = [a for a in ans if core.fold(a["n"]) not in bad]
            head = ans[:int(cfg.get("likely_names", 40))]
            names = [a["n"] for a in head]
    b = (d.get("better") or "").strip()
    if b.startswith("Name") and 15 < len(b) < 110 and abs(len(b) - len(q)) < 40:
        q = b
    hn = len(head)
    p = dict(p)
    if p.get("auto"):
        lvl = auto.level_for(dict(p, ans=ans), d["recall"], cfg)
        if not lvl:
            log("   not enough answers for its level: %s" % q)
            return None
        if not d.get("words_known", True) and core.LEVELS.index(lvl) < 2:
            lvl = core.LEVELS[2]
        log("   AI grade: recall %d -> %s" % (d["recall"], lvl))
        level = lvl
    else:
        level = raise_level(p, d, log)
    ans, qs = quality.improve(llm, q, ans, cfg, log, level=level, grow=False)
    if qs.get("survey"):
        log("   survey: %d of the %d most common answers were in the list, %d added, %d moved, %d spellings added" % (qs.get("covered", 0), qs.get("top", 0), qs["added"], qs["moved"], qs["aliases"]))
    p["q"] = q
    p["ans"] = ans
    p["level"] = level
    p["recall"] = d["recall"]
    return p


def finish(p, cfg):
    qid = core.make_id(p["key"])
    n = len(p["ans"])
    lv = core.levels_for(p["level"], n, p.get("n30", 0), p.get("recall"))
    return {"cat": p["cat"], "lvl": p["level"], "lv": lv, "item": core.encode_question(qid, p["q"], p["ans"], cfg, p["fam"], p["sub"]), "key": p["key"], "n": n}


def out_dir(cfg):
    if cfg.get("repo"):
        return os.path.join(cfg["repo"], "qdata")
    return os.path.join(BASE, cfg["output"]) if not os.path.isabs(cfg["output"]) else cfg["output"]


def git(repo, *args):
    import subprocess
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True, timeout=180)
    return r.returncode, (r.stdout + r.stderr).strip()


def publish(st, cfg, log, force=False):
    repo = cfg.get("repo")
    if not repo or cfg.get("_test"):
        return
    if not force and time.time() - st.get("last_push", 0) < cfg.get("publish_min_minutes", 30) * 60:
        return
    try:
        git(repo, "add", "-A")
        code, msg = git(repo, "commit", "-m", "questions v%d" % st.get("version", 0))
        if code != 0 and "nothing to commit" in msg:
            return
        code, msg = git(repo, "push")
        if code != 0:
            git(repo, "pull", "--rebase", "--autostash")
            code, msg = git(repo, "push")
        if code == 0:
            st["last_push"] = time.time()
            save_state(st, cfg)
            log("pushed to GitHub")
        else:
            log("push failed, will try again later: %s" % msg[-200:])
    except Exception as e:
        log("git problem: %s" % e)


def flush(st, cfg, log):
    hide = st.get("hide_new") or []
    if not st["pending"] and not hide and not st.get("dirty"):
        return
    out = out_dir(cfg)
    os.makedirs(out, exist_ok=True)
    mp = os.path.join(out, "manifest.json")
    man = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {"v": 0, "n": 0, "idx": []}
    if st["pending"]:
        man["n"] = man.get("n", 0) + 1
        name = "b%05d.json" % man["n"]
        raw = {}
        for x in st["pending"]:
            raw.setdefault(x["cat"], {}).setdefault(x["lvl"], []).append(x["item"])
            it = x["item"]
            base = core.LEVELS.index(x["lvl"])
            for lv in x.get("lv") or [x["lvl"]]:
                man["idx"].append([it[0], x["cat"], lv, it[4], it[5], name, core.LEVELS.index(lv) - base])
            st.setdefault("sigs", []).append(x.get("sig", []))
            st.setdefault("texts", []).append(it[1])
        json.dump(raw, open(os.path.join(out, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        if cfg.get("review_file", True):
            with open(os.path.join(BASE, "review.txt"), "a", encoding="utf-8") as rv:
                for x in st["pending"]:
                    it = x["item"]
                    lv = x.get("lv") or [x["lvl"]]
                    rv.write("%s / %s%s / %d answers\n  %s\n  %s\n\n" % (x["cat"], x["lvl"], (" (also in " + ", ".join(lv[1:]) + ")") if len(lv) > 1 else "", len(it[2]), it[1], "; ".join(a.split("|")[0] for a in it[2][:10])))
    if hide:
        man["hide"] = sorted(set(man.get("hide", [])) | set(hide))
    if st["pending"] or hide:
        st["version"] += 1
        man["v"] = man.get("v", 0) + 1
        man["t"] = int(time.time())
        tmp = mp + ".tmp"
        json.dump(man, open(tmp, "w", encoding="utf-8"), separators=(",", ":"))
        os.replace(tmp, mp)
    log("saved %d questions, %d retired (manifest v%d, %d in total)" % (len(st["pending"]), len(hide), man["v"], len(man["idx"])))
    st["pending"] = []
    st["hide_new"] = []
    st["dirty"] = False
    save_state(st, cfg)
    publish(st, cfg, log)
