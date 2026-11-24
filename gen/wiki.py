import json
import re
import time
import urllib.parse
import urllib.request

import core

API = "https://en.wikipedia.org/w/api.php"
SCHEMA = "PREFIX schema: <http://schema.org/>\n"


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def variants(name):
    out = []
    for v in (name, name.lower(), name[:1].upper() + name[1:], name.title()):
        if v and v not in out:
            out.append(v)
    return out


def ground(names, min_sl=1, thorough=True):
    names = [n for n in dict.fromkeys(x.strip() for x in names) if n and len(n) <= 80]
    got = {}
    for prop in ("rdfs:label", "skos:altLabel"):
        todo = names if (thorough or not got) else [n for n in names if n not in got]
        for i in range(0, len(todo), 50):
            chunk = todo[i : i + 50]
            vals = " ".join('"%s"@en' % esc(v) for n in chunk for v in variants(n))
            try:
                rows = core.sparql("SELECT ?lab ?x ?sl WHERE { VALUES ?lab { %s } ?x %s ?lab . ?x wikibase:sitelinks ?sl . FILTER(?sl >= %d) }" % (vals, prop, min_sl))
            except Exception:
                continue
            by = {}
            for r in rows:
                by.setdefault(r["lab"].lower(), []).append((int(float(r["sl"])), r["x"].rsplit("/", 1)[-1], r["lab"]))
            for n in chunk:
                k = n.lower()
                if k in by and (n not in got or max(by[k])[0] > got[n][1]):
                    sl, q, lab = max(by[k])
                    got[n] = (q, sl, lab)
    return got


def class_ids(labels):
    ids = []
    for lab in labels[:4]:
        lab = lab.strip()
        if not lab:
            continue
        best = None
        for prop in ("rdfs:label", "skos:altLabel"):
            for v in variants(lab)[:3]:
                try:
                    rows = core.sparql('SELECT ?x ?sl WHERE { ?x %s "%s"@en . ?x wikibase:sitelinks ?sl } ORDER BY DESC(?sl) LIMIT 1' % (prop, esc(v)))
                except Exception:
                    rows = []
                if rows and (best is None or int(float(rows[0]["sl"])) > best[0]):
                    best = (int(float(rows[0]["sl"])), rows[0]["x"].rsplit("/", 1)[-1])
            if best:
                break
        if best and best[1] not in ids:
            ids.append(best[1])
    return ids


def taxa_of(ids):
    if not ids:
        return set()
    try:
        rows = core.sparql("SELECT DISTINCT ?x WHERE { VALUES ?x { %s } ?x wdt:P105 ?r }" % " ".join("wd:" + q for q in ids))
    except Exception:
        return set()
    return {r["x"].rsplit("/", 1)[-1] for r in rows}


def class_rows(ids, min_sl, limit):
    if not ids:
        return []
    tx = taxa_of(ids)
    plain = [q for q in ids if q not in tx]
    out = []
    alts = 'OPTIONAL { ?i skos:altLabel ?al . FILTER(LANG(?al) = "en") }'
    head = 'SELECT ?i ?l ?sl (GROUP_CONCAT(DISTINCT ?al; separator="|") AS ?als) WHERE { '
    tail = " ?i wikibase:sitelinks ?sl . FILTER(?sl >= %d) " % min_sl
    end = " } GROUP BY ?i ?l ?sl ORDER BY DESC(?sl) LIMIT %d" % limit
    if plain:
        vals = " ".join("wd:" + q for q in plain)
        out += core.sparql(head + "VALUES ?c { %s } ?i wdt:P31/wdt:P279* ?c ." % vals + tail + '?i rdfs:label ?l . FILTER(LANG(?l) = "en") ' + alts + end)
    for q in tx:
        out += core.sparql(head + "?i wdt:P171+ wd:%s . ?i wdt:P105 wd:Q7432 . ?i wdt:P1843 ?l . FILTER(LANG(?l) = \"en\") " % q + tail + alts + end)
    return out


def http_json(params, tries=2):
    url = API + "?" + urllib.parse.urlencode(params)
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": core.UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            time.sleep(4 * (t + 1))
    return None


def list_titles(page):
    d = http_json({"action": "parse", "page": page, "prop": "links", "format": "json", "redirects": 1, "formatversion": 2})
    if not d or "parse" not in d:
        return []
    out = []
    for x in d["parse"].get("links", []):
        if x.get("ns") == 0 and x.get("exists", True):
            t = x["title"]
            if not re.match(r"^(List of|Lists of|Index of|Outline of|\d{3,4}$)", t):
                out.append(t)
    return out


def title_rows(titles, min_sl):
    rows = []
    titles = list(dict.fromkeys(titles))
    for i in range(0, len(titles), 80):
        chunk = titles[i : i + 80]
        vals = " ".join("<https://en.wikipedia.org/wiki/%s>" % urllib.parse.quote(t.replace(" ", "_"), safe="_(),'!*-.~:") for t in chunk)
        try:
            rs = core.sparql(
                SCHEMA + "SELECT ?i ?l ?sl WHERE { VALUES ?art { %s } ?art schema:about ?i . ?i wikibase:sitelinks ?sl . FILTER(?sl >= %d) ?i rdfs:label ?l . FILTER(LANG(?l) = \"en\") }" % (vals, min_sl)
            )
        except Exception:
            continue
        rows.extend(rs)
    return rows


def rows_from_grounded(g):
    out = []
    for n, (q, sl, lab) in g.items():
        out.append({"i": "http://www.wikidata.org/entity/" + q, "l": n, "sl": str(sl), "als": ""})
    return out
