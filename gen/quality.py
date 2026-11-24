import math
import re

import auto
import core
import wiki


def squash(s):
    return core.fold(s).replace(" ", "")


def uk(k):
    if len(k) < 5:
        return k
    k = re.sub(r"([^aeiou])re$", r"\1er", k)
    k = re.sub(r"our(s?)$", r"or\1", k)
    k = re.sub(r"is(e|es|ed|ing|ation|ations)$", r"iz\1", k)
    k = re.sub(r"yse$", "yze", k)
    k = re.sub(r"ogue$", "og", k)
    k = re.sub(r"ence$", "ense", k)
    k = re.sub(r"([aeiou])ll(ing|ed|er|ers)$", r"\1l\2", k)
    return k.replace("ae", "e")


def keys_of(name):
    f = core.fold(name)
    s = f.replace(" ", "")
    g = re.sub(r"^(the|a|an) ", "", f).replace(" ", "")
    out = []
    for k in (s, g):
        if not k:
            continue
        for v in (k, uk(k)):
            out.append(v)
            if len(v) > 4 and v.endswith("s"):
                out.append(v[:-1])
            elif len(v) > 3:
                out.append(v + "s")
    return list(dict.fromkeys(out))


def to_ans(names):
    out = []
    for i, g in enumerate(names):
        parts = [x for x in g.split("|") if x.strip()]
        if not parts:
            continue
        out.append({"n": parts[0], "al": parts[1:], "sl": 0, "k": 0, "sv": False, "nw": 0, "id": "s" + squash(parts[0])[:40], "pos": i, "hits": 0})
    return out


def to_names(ans):
    return ["|".join([a["n"].replace("|", "/")] + [x.replace("|", "/") for x in a["al"]]) for a in ans]


def build_index(ans):
    ix = {}
    for i, a in enumerate(ans):
        for nm in [a["n"]] + a["al"]:
            for k in keys_of(nm):
                ix.setdefault(k, i)
    return ix


def find(ix, name):
    for k in keys_of(name):
        if k in ix:
            return ix[k]
    return None


def ground_top(ans, limit=150):
    todo = [a for a in ans[:limit] if not a["sl"]]
    if not todo:
        return
    g = wiki.ground([a["n"] for a in todo], 1, False)
    for a in todo:
        hit = g.get(a["n"])
        if hit:
            a["id"] = hit[0]
            a["sl"] = hit[1]
            a["k"] = hit[1]


def survey(llm, q, cfg, log):
    ns = int(cfg.get("survey_samples", 3))
    cnt = int(cfg.get("survey_count", 60))
    lists = []
    tries = 0
    while len(lists) < ns and tries < ns + 2:
        who = llm.PERSONAS[tries % len(llm.PERSONAS)]
        tries += 1
        r = llm.survey_once(q, cnt, who)
        if r and len(r) >= 8:
            lists.append(r)
    return lists


def consensus(lists):
    sc = {}
    for lst in lists:
        n = float(len(lst))
        for r, name in enumerate(lst):
            k = squash(name)
            if not k:
                continue
            e = sc.setdefault(k, {"name": name, "hits": 0, "pts": 0.0})
            e["hits"] += 1
            e["pts"] += 1.0 - r / n
    order = sorted(sc.values(), key=lambda e: (-e["pts"], -e["hits"]))
    for i, e in enumerate(order):
        e["rank"] = i
    return order


def blend(ans, cons, cfg, log):
    ix = build_index(ans)
    ns = len(cons)
    miss = []
    for e in cons:
        i = find(ix, e["name"])
        if i is None:
            miss.append(e)
        else:
            a = ans[i]
            if "srank" not in a or e["rank"] < a["srank"]:
                a["srank"] = e["rank"]
            a["hits"] = max(a.get("hits", 0), e["hits"])
    added = 0
    if miss:
        g = wiki.ground([e["name"] for e in miss], 1)
        by_sl = sorted((a["sl"] for a in ans if a["sl"]), reverse=True)
        for e in miss:
            hit = g.get(e["name"])
            if not hit and e["hits"] < 2:
                continue
            sl = hit[1] if hit else 0
            if hit and hit[1] < 2 and e["hits"] < 2:
                continue
            if find(ix, e["name"]) is not None:
                continue
            ps = sum(1 for v in by_sl if v > sl) if sl else int(len(ans) * 0.5)
            a = {"n": e["name"], "al": [], "sl": sl, "k": sl, "sv": False, "nw": 0, "id": hit[0] if hit else "s" + squash(e["name"])[:40], "pos": ps, "hits": e["hits"], "srank": e["rank"]}
            ans.append(a)
            for k in keys_of(a["n"]):
                ix.setdefault(k, len(ans) - 1)
            added += 1
    for a in ans:
        ps = a["pos"]
        if "srank" in a:
            a["key"] = 0.8 * math.log(a["srank"] + 1) + 0.2 * math.log(ps + 1)
        else:
            a["key"] = 0.8 * math.log(ns + 0.5 * ps + 1) + 0.2 * math.log(ps + 1)
    ans.sort(key=lambda a: (a["key"], a["pos"]))
    for i, a in enumerate(ans):
        a["pos"] = i
    return ans, added


def order_fix(llm, q, ans, log):
    n = len(ans)
    if n < 30:
        return ans, 0, 0
    top = [a["n"] for a in ans[:40]]
    pool = ans[40:300]
    if pool:
        step = max(1, len(pool) // 40)
        below = [a["n"] for a in pool[::step][:40]]
    else:
        below = []
    d = llm.order_check(q, top, below)
    if not d:
        return ans, 0, 0
    byname = {core.fold(a["n"]): a for a in ans}
    removed = 0
    moved = 0
    for nm in d["invalid"]:
        a = byname.get(core.fold(nm))
        if a is not None and a.get("hits", 0) < 2 and a.get("srank", 99) > 25 and a in ans:
            ans.remove(a)
            removed += 1
    for j, nm in enumerate(d["too_low"][:8]):
        a = byname.get(core.fold(nm))
        if a is not None and a in ans and ans.index(a) > 40:
            ans.remove(a)
            ans.insert(min(len(ans), 18 + j * 2), a)
            moved += 1
    for nm in d["too_high"][:8]:
        a = byname.get(core.fold(nm))
        if a is not None and a in ans and a.get("hits", 0) == 0:
            i = ans.index(a)
            ans.remove(a)
            ans.insert(min(len(ans), max(i + 25, 60)), a)
            moved += 1
    for i, a in enumerate(ans):
        a["pos"] = i
    return ans, removed, moved


def add_aliases(llm, q, ans, log, limit=150):
    ix = build_index(ans)
    added = 0
    head = [a for a in ans[:limit] if len(a["al"]) < 4]
    for i in range(0, len(head), 30):
        chunk = head[i : i + 30]
        got = llm.alias_batch(q, [a["n"] for a in chunk])
        for a in chunk:
            for al in got.get(a["n"], []):
                if len(a["al"]) >= 8 or len(al) > 40 or len(al) < 2 or re.fullmatch(r"[\d\W_]+", al):
                    continue
                ks = keys_of(al)
                if any(k in ix for k in ks):
                    continue
                a["al"].append(al)
                for k in ks:
                    ix.setdefault(k, a["pos"])
                added += 1
    return added


LETTER = re.compile(r"\b(?:starts?|starting|begins?|beginning) with (?:the )?(?:letter )?([A-Za-z])\b", re.I)


def letter_rule(q):
    m = LETTER.search(q)
    if not m:
        return None
    L = m.group(1).lower()
    return lambda name: core.fold(re.sub(r"^(the|a|an) ", "", name.strip(), flags=re.I))[:1] == L


def expand(llm, q, ans, cfg, log):
    sp = llm.spec(q)
    if not sp:
        return ans, 0
    rows, src, g = auto.gather(q, sp, cfg, log)
    seen = set()
    uniq = []
    for r in rows:
        if r["i"] in seen:
            continue
        seen.add(r["i"])
        uniq.append(r)
    new = core.clean_answers(uniq, skip_names=[])
    rule = letter_rule(q)
    if rule:
        new = [a for a in new if rule(a["n"])]
    ix = build_index(ans)
    fresh = []
    for a in new:
        if find(ix, a["n"]) is None and not any(find(ix, x) is not None for x in a["al"]):
            fresh.append(a)
    if not fresh:
        return ans, 0
    fresh = fresh[: int(cfg.get("max_answers", 6000))]
    tail = auto.tail_sample(fresh + ans[:40], 12) if len(fresh) >= 40 else [a["n"] for a in fresh[:: max(1, len(fresh) // 12)][:12]]
    d = llm.review(q, [a["n"] for a in ans[:15]], tail)
    if d is None:
        return ans, 0
    bad = {core.fold(x) for x in d["misfits"]}
    if tail and len([t for t in tail if core.fold(t) in bad]) / float(len(tail)) > float(cfg.get("expand_misfit", 0.15)):
        log("   class list does not fit, not used: %s" % q)
        return ans, 0
    fresh = [a for a in fresh if core.fold(a["n"]) not in bad]
    base = len(ans)
    for j, a in enumerate(fresh):
        a["pos"] = base + j
        a["hits"] = 0
        ans.append(a)
    return ans, len(fresh)


def improve(llm, q, ans, cfg, log, level=None, grow=True):
    st = {"before": len(ans), "added": 0, "survey": 0, "covered": 0, "aliases": 0, "removed": 0, "moved": 0}
    for i, a in enumerate(ans):
        a["pos"] = i
        a.setdefault("hits", 0)
    ground_top(ans, 150)
    target = cfg["min_answers"].get(level or "medium", 100)
    if grow and len(ans) < target:
        ans, n = expand(llm, q, ans, cfg, log)
        st["added"] += n
    lists = survey(llm, q, cfg, log)
    st["survey"] = len(lists)
    if lists:
        cons = consensus(lists)
        ix = build_index(ans)
        top = cons[:30]
        st["covered"] = sum(1 for e in top if find(ix, e["name"]) is not None)
        st["top"] = len(top)
        ans, n = blend(ans, cons, cfg, log)
        st["added"] += n
        ans, rm, mv = order_fix(llm, q, ans, log)
        st["removed"] = rm
        st["moved"] = mv
    st["aliases"] = add_aliases(llm, q, ans, log)
    st["after"] = len(ans)
    return ans, st
