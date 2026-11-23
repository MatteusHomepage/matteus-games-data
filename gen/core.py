import hashlib
import json
import math
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
os.makedirs(CACHE, exist_ok=True)

ENDPOINT = "https://qlever.cs.uni-freiburg.de/api/wikidata"
UA = "MatteusGames-generator/1.0 (matteus-aydin.se)"

PFX = (
    "PREFIX wd: <http://www.wikidata.org/entity/>\n"
    "PREFIX wdt: <http://www.wikidata.org/prop/direct/>\n"
    "PREFIX wikibase: <http://wikiba.se/ontology#>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
    "PREFIX p: <http://www.wikidata.org/prop/>\n"
    "PREFIX psn: <http://www.wikidata.org/prop/statement/value-normalized/>\n"
    "PREFIX wikibase_: <http://wikiba.se/ontology#>\n"
)

LETTER_ADJ = {"Q": 1.2, "X": 1.2, "Z": 1.0, "Y": 0.8, "U": 0.7, "V": 0.6, "K": 0.4, "J": 0.4, "W": 0.4, "I": 0.5, "O": 0.5, "E": 0.4, "F": 0.2, "G": 0.2, "H": 0.2, "L": 0.2, "N": 0.3, "R": 0.2, "D": 0.1}
LEVELS = ["easy", "medium", "hard", "expert", "impossible"]
CATS = ["general", "geography", "food", "nature", "history", "words", "movies", "music", "games", "sport", "science"]
EDGE = [0, 0.2, 0.4, 0.6, 0.8, 0.98, 1.0]
B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


DEFAULTS = {
    "output": "qdata",
    "workers": 4,
    "producers": 3,
    "buffer": 36,
    "buffer_cell": 4,
    "num_ctx": 3072,
    "sparql_gap": 2.0,
    "likely_rounds": 1,
    "recall_count": 40,
    "publish_every": 12,
    "publish_min_minutes": 20,
    "max_answers": 6000,
    "breadth": 0.5,
    "auto_min_sl": 3,
    "auto_min_answers": 100,
    "max_misfit": 0.25,
    "rescue": True,
    "rescue_per_run": 25,
    "use_seeds": True,
    "run_minutes": 0,
    "cell_target": {"easy": 150, "medium": 150, "hard": 120, "expert": 90, "impossible": 70},
    "min_answers": {"easy": 300, "medium": 200, "hard": 120, "expert": 100, "impossible": 100},
    "level_cuts": [1.8, 2.5, 3.3, 4.2],
    "zipf": 0.85,
    "mass_edges": [0, 0.3, 0.58, 0.8, 0.92, 0.99, 1.0],
}


def settings():
    p = os.path.join(BASE, "settings.json")
    d = dict(DEFAULTS)
    if os.path.exists(p):
        d.update(json.load(open(p, encoding="utf-8")))
    return d


LAST = [0.0]
GAP = [3.0]
LOCK = threading.Lock()


def sparql(q, timeout=240, tries=4):
    q = PFX + q
    key = hashlib.md5(q.encode()).hexdigest()
    f = os.path.join(CACHE, key + ".json")
    if os.path.exists(f):
        try:
            return json.load(open(f, encoding="utf-8"))
        except Exception:
            pass
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
    err = None
    for t in range(tries):
        try:
            with LOCK:
                wait = GAP[0] - (time.time() - LAST[0])
                if wait > 0:
                    time.sleep(wait)
                LAST[0] = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            rows = d["results"]["bindings"]
            out = [{k: v["value"] for k, v in b.items()} for b in rows]
            tmp = f + "." + str(threading.get_ident()) + ".tmp"
            json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            os.replace(tmp, f)
            return out
        except Exception as e:
            err = e
            time.sleep(60 * (t + 1) if getattr(e, "code", 0) == 429 else 5 * (t + 1))
    raise RuntimeError("query failed: %s" % err)


def b36(n, w=2):
    o = ""
    while n:
        o = B36[n % 36] + o
        n //= 36
    return o.rjust(w, "0")


def norm(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9åäöéèüñç ]+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def fold(s):
    s = unicodedata.normalize("NFD", s.lower().replace("&", " and "))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"['\u2019`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"^(the|a|an) ", "", s)


SV_LETTERS = re.compile(r"[åäöÅÄÖ]")
SV_WORDS = re.compile(r"\b(och|från|för|är|på|inte)\b", re.I)
SV_BOOST = 1.6


BAD_LABEL = re.compile(r"^(q\d+|list of|lists of|category:)|\(disambiguation\)|^\d+$|^\d+(st|nd|rd|th) ", re.I)


def clean_answers(rows, skip_names=(), sv_rows=None):
    sv_ids = set()
    if sv_rows:
        have = {r["i"] for r in rows}
        for r in sv_rows:
            sv_ids.add(r["i"])
            if r["i"] not in have:
                rows = rows + [r]
                have.add(r["i"])
    seen = set()
    out = []
    skip = {norm(x) for x in skip_names}
    for r in rows:
        name = r["l"].strip()
        if not name or len(name) > 60 or BAD_LABEL.search(name) or re.search(r",\s+[a-z]", name):
            continue
        k = norm(name)
        if not k or k in seen or k in skip:
            continue
        seen.add(k)
        als = []
        for a in (r.get("als") or "").split("|"):
            a = a.strip()
            ka = norm(a)
            if (SV_LETTERS.search(a) and not SV_LETTERS.search(name)) or (SV_WORDS.search(a) and not SV_WORDS.search(name)):
                continue
            if a and len(a) <= 40 and ka and ka != k and ka not in seen and not BAD_LABEL.search(a) and len(als) < 5:
                als.append(a)
        for a in als:
            seen.add(norm(a))
        sl = int(float(r["sl"]))
        sv = r["i"] in sv_ids
        out.append({"n": name, "al": als, "sl": sl, "k": sl * SV_BOOST if sv else sl, "sv": sv, "nw": int(float(r["nw"])) if r.get("nw") else 0, "id": r["i"].rsplit("/", 1)[-1]})
    out.sort(key=lambda x: -x["k"])
    cnt = {}
    kept = []
    for a in out:
        m = re.match(r"^(.{3,}?)\s*[:\u2013-]\s", a["n"])
        if m:
            k = m.group(1).lower()
            cnt[k] = cnt.get(k, 0) + 1
            if cnt[k] > 2:
                continue
        kept.append(a)
    out = kept
    if any(a["nw"] for a in out):
        by_nw = sorted(range(len(out)), key=lambda i: -out[i]["nw"])
        rk = [0] * len(out)
        for pos, i in enumerate(by_nw):
            rk[i] = pos
        order = sorted(range(len(out)), key=lambda i: (i + rk[i], i))
        out = [out[i] for i in order]
    return out


def fame_counts(ans, scale=1.0):
    hc, kc, fc = 60 * scale, 25 * scale, 10 * scale
    h = sum(1 for a in ans if a["sl"] >= hc)
    k = sum(1 for a in ans if kc <= a["sl"] < hc)
    f = sum(1 for a in ans if fc <= a["sl"] < kc)
    return h, k, f


def level_of(ans, cfg, scale, base, adj):
    n = len(ans)
    if n < cfg["min_answers"]["impossible"]:
        return None
    top = sorted((x["sl"] for x in ans), reverse=True)[:10]
    avg = sum(top) / max(1, len(top))
    r = avg / max(1.0, scale * 150.0)
    score = base + adj
    T = cfg["level_cuts"]
    i = 0
    while i < 4 and score >= T[i]:
        i += 1
    if n < cfg["min_answers"][LEVELS[i]]:
        return None
    return LEVELS[i]


def levels_for(native, n, n30, recall):
    i = LEVELS.index(native)
    if recall is None:
        return [native]
    if native == "easy" and recall <= 1 and n >= 400 and n30 >= 50:
        return LEVELS[:]
    if native == "easy" and recall <= 2 and n >= 250 and n30 >= 30:
        return LEVELS[:3]
    if native == "medium" and recall <= 2 and n >= 300 and n30 >= 40:
        return LEVELS[1:3]
    return [native]


def rarity_values(n, cfg):
    s = cfg["zipf"]
    me = cfg["mass_edges"]
    w = [1.0 / (r ** s) for r in range(1, n + 1)]
    tot = sum(w)
    vals = []
    before = 0.0
    for i in range(n):
        mid = (before + w[i] / 2) / tot
        before += w[i]
        k = 0
        while k < 5 and mid >= me[k + 1]:
            k += 1
        lo, hi = me[k], me[k + 1]
        t = (mid - lo) / (hi - lo) if hi > lo else 0
        vals.append(EDGE[k] + (EDGE[k + 1] - EDGE[k]) * min(1.0, max(0.0, t)))
    return vals


def encode_question(qid, text, ans, cfg, fam, sub):
    n = len(ans)
    vals = rarity_values(n, cfg)
    rar = "".join(b36(min(1295, round(v * 1000))) for v in vals)
    names = ["|".join([a["n"].replace("|", "/")] + [x.replace("|", "/") for x in a["al"]]) for a in ans]
    return [qid, text, names, rar, fam, sub]


def make_id(key):
    h = int(hashlib.md5(key.encode()).hexdigest()[:10], 16)
    return "g" + b36(h, 1)[:7].rjust(7, "0")


def tier_mix(n, cfg):
    vals = rarity_values(n, cfg)
    bins = [0] * 6
    for v in vals:
        k = 0
        while k < 5 and v >= EDGE[k + 1]:
            k += 1
        bins[k] += 1
    return bins


RES = os.path.join(BASE, "resolve.json")


def resolve(label):
    d = json.load(open(RES, encoding="utf-8")) if os.path.exists(RES) else {}
    if label in d:
        return d[label]
    if re.match(r"^Q[0-9]+$", label):
        return label
    lab = label.replace('"', "")
    rows = sparql('SELECT ?x ?sl WHERE { ?x rdfs:label "%s"@en . ?x wikibase:sitelinks ?sl } ORDER BY DESC(?sl) LIMIT 3' % lab)
    if not rows:
        rows = sparql('SELECT ?x ?sl WHERE { ?x skos:altLabel "%s"@en . ?x wikibase:sitelinks ?sl } ORDER BY DESC(?sl) LIMIT 3' % lab)
    if not rows:
        raise RuntimeError("cannot resolve " + label)
    d[label] = rows[0]["x"].rsplit("/", 1)[-1]
    json.dump(d, open(RES, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return d[label]


def resolve_many(labels):
    d = json.load(open(RES, encoding="utf-8")) if os.path.exists(RES) else {}
    todo = sorted({x for x in labels if x not in d and not re.match(r"^Q[0-9]+$", x)})
    for prop in ("rdfs:label", "skos:altLabel"):
        for i in range(0, len(todo), 60):
            chunk = [x for x in todo[i : i + 60] if x not in d]
            if not chunk:
                continue
            vals = " ".join('"%s"@en' % x.replace('"', "") for x in chunk)
            rows = sparql("SELECT ?lab ?x ?sl WHERE { VALUES ?lab { %s } ?x %s ?lab . ?x wikibase:sitelinks ?sl }" % (vals, prop))
            best = {}
            for r in rows:
                k = r["lab"]
                sl = int(float(r["sl"]))
                if k not in best or sl > best[k][0]:
                    best[k] = (sl, r["x"].rsplit("/", 1)[-1])
            for k, (sl, x) in best.items():
                d[k] = x
        todo = [x for x in todo if x not in d]
    json.dump(d, open(RES, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return todo
