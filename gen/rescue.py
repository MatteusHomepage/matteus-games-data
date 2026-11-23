import json
import os
import time
import urllib.parse
import urllib.request

import core
import wiki

DEFAULT_URL = "https://mrrixocnhsfulglipvek.supabase.co"
DEFAULT_KEY = "sb_publishable_fIFvv3lqR66EOuclo_bscg_Qv8OKNt1"


def fetch(cfg, limit=400):
    url = (cfg.get("supabase_url") or DEFAULT_URL).rstrip("/")
    key = cfg.get("supabase_anon_key") or DEFAULT_KEY
    q = url + "/rest/v1/rare_rejects?select=qid,guess,n&order=n.desc,last_at.desc&limit=%d" % limit
    req = urllib.request.Request(q, headers={"apikey": key, "Authorization": "Bearer " + key, "User-Agent": core.UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def manifest_index(out):
    mp = os.path.join(out, "manifest.json")
    if not os.path.exists(mp):
        return {}
    man = json.load(open(mp, encoding="utf-8"))
    where = {}
    for e in man.get("idx", []):
        if e[6] == 0:
            where[e[0]] = (e[5], e[1], e[2])
    return where


def load_item(out, where, qid):
    f, cat, lvl = where[qid]
    path = os.path.join(out, f)
    raw = json.load(open(path, encoding="utf-8"))
    for i, it in enumerate(raw.get(cat, {}).get(lvl, [])):
        if it[0] == qid:
            return path, raw, cat, lvl, i
    return None


def position(names, new_sl):
    head = names[:150]
    g = wiki.ground([n.split("|")[0] for n in head], 1)
    last = None
    for i, n in enumerate(head):
        sl = g.get(n.split("|")[0], (None, None))[1]
        if sl is None:
            continue
        last = i
        if sl < new_sl:
            return i
    return min(len(names), (last + 1) if last is not None else 40)


def judge_all(st, cfg, llm, log, out):
    where = manifest_index(out)
    if not where:
        return 0
    try:
        rows = fetch(cfg)
    except Exception as e:
        log("could not read the rejected guesses: %s" % e)
        return 0
    done = st.setdefault("rej_done", {})
    todo = []
    for r in rows:
        k = r["qid"] + "|" + r["guess"]
        if r["qid"] in where and k not in done:
            todo.append(r)
    maxn = int(cfg.get("rescue_per_run", 25))
    todo.sort(key=lambda r: -int(r.get("n") or 1))
    todo = todo[:maxn]
    if not todo:
        return 0
    changed = 0
    by = {}
    for r in todo:
        by.setdefault(r["qid"], []).append(r)
    for qid, lst in by.items():
        try:
            loc = load_item(out, where, qid)
        except Exception:
            loc = None
        if not loc:
            for r in lst:
                done[qid + "|" + r["guess"]] = "missing"
            continue
        path, raw, cat, lvl, i = loc
        it = raw[cat][lvl][i]
        names = list(it[2])
        firsts = [n.split("|")[0] for n in names]
        known = {}
        for j, n in enumerate(names):
            for a in n.split("|"):
                known.setdefault(core.fold(a), j)
        edited = False
        for r in lst:
            g = r["guess"]
            k = qid + "|" + g
            fg = core.fold(g)
            if not fg or fg in known:
                done[k] = "known"
                continue
            d = llm.judge_guess(it[1], firsts, g)
            if d is None:
                continue
            if not d["valid"]:
                done[k] = "no"
                log("   rejected guess stays out: %s -> %s" % (it[1], g))
                continue
            same = d["same_as"]
            if same:
                j = known.get(core.fold(same))
                if j is not None:
                    parts = names[j].split("|")
                    if len(parts) < 9 and g not in parts:
                        parts.append(g)
                        names[j] = "|".join(parts)
                        known[fg] = j
                        edited = True
                        done[k] = "alias"
                        log("   added alias: %s -> %s (%s)" % (it[1], g, same))
                        continue
            canon = d["canonical"] or g
            fc = core.fold(canon)
            if fc in known:
                j = known[fc]
                parts = names[j].split("|")
                if len(parts) < 9 and g not in parts:
                    parts.append(g)
                    names[j] = "|".join(parts)
                    known[fg] = j
                    edited = True
                done[k] = "alias"
                continue
            gr = wiki.ground([canon, g], 2)
            sl = max([v[1] for v in gr.values()] or [0])
            n_rep = int(r.get("n") or 1)
            if sl < 3 and n_rep < 3:
                done[k] = "unverified"
                continue
            if sl < 3:
                sl = 3
            parts = [canon.replace("|", "/")]
            if core.fold(g) != fc:
                parts.append(g.replace("|", "/"))
            for a in d["aliases"]:
                if core.fold(a) not in known and len(parts) < 6:
                    parts.append(a.replace("|", "/"))
            pos = position(names, sl)
            names.insert(pos, "|".join(parts))
            known = {}
            for j, n in enumerate(names):
                for a in n.split("|"):
                    known.setdefault(core.fold(a), j)
            edited = True
            done[k] = "added"
            log("   rescued answer: %s -> %s at place %d" % (it[1], canon, pos + 1))
        if edited:
            n = len(names)
            vals = core.rarity_values(n, cfg)
            rar = "".join(core.b36(min(1295, round(v * 1000))) for v in vals)
            it[2] = names
            it[3] = rar
            tmp = path + ".tmp"
            json.dump(raw, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)
            changed += 1
    return changed
