import json
import os
import queue
import random
import re
import sys
import threading
import time

import auto
import core
import gen as G
import repair
import rescue
from providers import NoProvider

BASE = core.BASE
LEVEL_RECALL = {"easy": 1, "medium": 2, "hard": 3, "expert": 4, "impossible": 5}
RECALL_LEVEL = {v: k for k, v in LEVEL_RECALL.items()}
CELLS = [(c, l) for c in core.CATS for l in core.LEVELS]


def words(q):
    return set(re.sub(r"[^a-z0-9 ]+", "", q.lower()).split()) - {"name", "a", "an", "the", "of", "in", "that", "is", "for", "with", "type", "kind"}


def predict(score, cfg):
    T = cfg["level_cuts"]
    i = 0
    while i < 4 and score >= T[i]:
        i += 1
    return core.LEVELS[i]


def load_manifest(out):
    mp = os.path.join(out, "manifest.json")
    if os.path.exists(mp):
        return json.load(open(mp, encoding="utf-8"))
    return {"v": 0, "n": 0, "idx": []}


def bootstrap(st, cfg, log):
    out = G.out_dir(cfg)
    man = load_manifest(out)
    ids = {e[0] for e in man["idx"]}
    if man["idx"] and not st.get("sigs"):
        files = sorted({e[5] for e in man["idx"]})
        n = 0
        for f in files:
            p = os.path.join(out, f)
            if not os.path.exists(p):
                continue
            raw = json.load(open(p, encoding="utf-8"))
            for cat in raw:
                for lvl in raw[cat]:
                    for it in raw[cat][lvl]:
                        st["sigs"].append([core.norm(x.split("|")[0]) for x in it[2][:30]])
                        st["texts"].append(it[1])
                        n += 1
        log("rebuilt the memory of %d questions from the saved files" % n)
    return ids, man


def base_counts(man, sigs):
    c = {}
    for cat, lvl, _ in sigs:
        c[(cat, lvl)] = c.get((cat, lvl), 0) + 1.0
    for e in man["idx"]:
        if len(e[0]) >= 9 and re.search(r"x\d$", e[0]):
            continue
        k = (e[1], e[2])
        c[k] = c.get(k, 0) + (1.0 if e[6] == 0 else 0.4)
    return c


class Scheduler:
    def __init__(self, cfg, counts):
        self.cfg = cfg
        self.counts = counts
        self.infl = {}
        self.ready = {}
        self.blocked = {}
        self.fails = {}

    def target(self, lvl):
        return float(self.cfg["cell_target"][lvl])

    def scale(self):
        s = 1.0
        for _ in range(8):
            if min(self.fill(c) / (self.target(c[1]) * s) for c in CELLS) < 1.0:
                return s
            s *= 1.5
        return s

    def fill(self, c):
        return self.counts.get(c, 0) + self.infl.get(c, 0) + 0.5 * len(self.ready.get(c, []))

    def order(self):
        s = self.scale()
        now = time.time()
        rows = [(self.fill(c) / (self.target(c[1]) * s), random.random(), c) for c in CELLS if self.blocked.get(c, 0) <= now]
        rows.sort()
        return [c for _, _, c in rows]

    def stuck(self, c):
        self.fails[c] = self.fails.get(c, 0) + 1
        if self.fails[c] >= 5:
            self.fails[c] = 0
            self.blocked[c] = time.time() + 900

    def ok(self, c):
        self.fails[c] = 0


def run(args, llm=None):
    cfg = core.settings()
    core.GAP[0] = float(cfg.get("sparql_gap", 2.0))
    test = "--test" in args
    in_actions = bool(os.environ.get("GITHUB_ACTIONS"))
    if in_actions:
        cfg["repo"] = os.path.dirname(BASE)
        cfg["state_dir"] = os.path.join(cfg["repo"], "state")
        cfg["review_file"] = False
    if test:
        cfg = dict(cfg)
        cfg["output"] = "qdata_test"
        cfg["state_dir"] = "state_test"
        cfg["_test"] = True
        cfg["review_file"] = False
        cfg.pop("repo", None)
    use_llm = "--no-llm" not in args
    limit = int(cfg.get("max_new_per_run") or 0)
    minutes = float(cfg.get("run_minutes", 0) or 0)
    workers = max(1, int(cfg.get("workers", 4)))
    for a in args:
        if a.startswith("--max="):
            limit = int(a[6:])
        if a.startswith("--minutes="):
            minutes = float(a[10:])
        if a.startswith("--workers="):
            workers = max(1, int(a[10:]))
    if not use_llm:
        workers = 1
    wlock = threading.RLock()

    def log(s):
        line = time.strftime("%H:%M:%S ") + s
        with wlock:
            print(line, flush=True)
            try:
                open(os.path.join(BASE, "run.log"), "a", encoding="utf-8").write(line + "\n")
            except Exception:
                pass

    if use_llm and llm is None:
        from llm import LLM
        llm = LLM(cfg, log=log)
    if use_llm and not llm.alive():
        log("No AI service has a key yet. Add at least one key (see SETUP.txt), or use --no-llm for a plumbing test.")
        return
    if use_llm:
        log("AI services in use: %s" % ", ".join(llm.pool.names()) if hasattr(llm, "pool") else "AI: custom")
    st = G.load_state(cfg)
    st["_cfg"] = cfg
    ids, man = bootstrap(st, cfg, log)
    sigs = G.exists_sigs()
    gen_sigs = [("", "", set(s)) for s in st.get("sigs", [])]
    known_words = [words(x) for x in st.get("texts", [])]
    ex_rows = json.load(open(os.path.join(BASE, "existing.json"), encoding="utf-8"))
    known_words += [words(r[2]) for r in ex_rows]
    ex_by_cell = {}
    for r in ex_rows:
        ex_by_cell.setdefault((r[0], r[1]), []).append(r[2])
    texts_by_cat = {}
    for r in ex_rows:
        texts_by_cat.setdefault(r[0], []).append(r[2])
    sch = Scheduler(cfg, base_counts(man, sigs))
    deadline = time.time() + minutes * 60 if minutes else 0
    state = {"made": 0, "active": 0, "stop": False, "noai": False}
    buf_total = int(cfg.get("buffer", 36))
    buf_cell = int(cfg.get("buffer_cell", 4))
    jobs = queue.Queue()
    plock = threading.Lock()
    claimed = set()
    recent = {"f": [], "v": []}

    def done_key(key):
        return key in st["done"] or core.make_id(key) in ids or key in claimed

    def similar(q):
        w = words(q)
        if not w:
            return True
        for o in known_words:
            if not o:
                continue
            inter = len(w & o)
            if inter and inter / float(len(w | o)) >= 0.8:
                return True
        return False

    by_cell = {}
    for r, f in G.candidates():
        lv0 = predict(f["base"], cfg)
        by_cell.setdefault((r["cat"], lv0), []).append((r, f))
        if f["kind"] == "custom":
            for pr in f["params"]:
                lv1 = predict(f["base"] + (pr[2] if len(pr) > 2 else 0.0), cfg)
                if lv1 != lv0:
                    by_cell.setdefault((r["cat"], lv1), []).append((r, f))
    vals = {}
    fills = {}

    def rweight(rf):
        r, f = rf
        w = r.get("w", 1.0)
        if f["kind"] == "regex":
            w *= 0.3
        return w

    def recipe_candidate(cell):
        pool = list(by_cell.get(cell, []))
        near = []
        li = core.LEVELS.index(cell[1])
        for j in (li - 1, li + 1):
            if 0 <= j < 5:
                near += by_cell.get((cell[0], core.LEVELS[j]), [])
        order = sorted(pool, key=lambda rf: -(random.random() ** (1.0 / rweight(rf)))) + sorted(near, key=lambda rf: -(random.random() ** (1.0 / (rweight(rf) * 0.5))))
        with plock:
            for r, f in order:
                if state["stop"]:
                    return None
                k = r["key"] + "." + f["key"]
                if k not in vals:
                    try:
                        vals[k] = G.values(r, f)
                    except Exception as e:
                        log("discovery failed for %s: %s" % (k, e))
                        vals[k] = []
                    fills[k] = 0
                lst = vals[k]
                while fills[k] < len(lst):
                    v = lst[fills[k]]
                    fills[k] += 1
                    key = G.cand_key(r, f, v)
                    with wlock:
                        if done_key(key):
                            continue
                    claimed.add(key)
                    return r, f, v, key
        return None

    seedq = {}
    seeds_ready = threading.Event()

    def seed_loader():
        try:
            lines = [x.strip() for x in open(os.path.join(BASE, "seeds_krillion.txt"), encoding="utf-8") if x.strip().lower().startswith("name ")]
            cl = st.setdefault("seeds", {})
            todo = [q for q in lines if q not in cl]
            for i in range(0, len(todo), 40):
                if state["stop"]:
                    break
                chunk = todo[i : i + 40]
                res = llm.classify(chunk)
                with wlock:
                    for j, q in enumerate(chunk):
                        if j in res:
                            cl[q] = list(res[j])
            with wlock:
                for q, v in cl.items():
                    if not v[0]:
                        continue
                    key = auto.key_of(q)
                    if done_key(key):
                        continue
                    seedq.setdefault((v[0], RECALL_LEVEL.get(int(v[1]), "medium")), []).append({"q": q if q.endswith(".") else q + ".", "cat": v[0], "recall": int(v[1]), "key": key, "src": "seed"})
                for k in seedq:
                    random.shuffle(seedq[k])
        except NoProvider:
            state["noai"] = True
        except Exception as e:
            log("seed list problem: %s" % e)
        finally:
            seeds_ready.set()

    brainq = {}
    block_lock = {}

    def brain_candidate(cell):
        with wlock:
            lk = block_lock.setdefault(cell, threading.Lock())
        with lk:
            q = brainq.get(cell, [])
            if not q:
                avoid = (ex_by_cell.get(cell, []) + texts_by_cat.get(cell[0], []))[-25:]
                with wlock:
                    avoid = avoid + [t for t in st.get("texts", [])][-25:]
                seeds = random.sample(ex_by_cell.get(cell, []), min(3, len(ex_by_cell.get(cell, [])))) if ex_by_cell.get(cell) else []
                got = llm.brainstorm(cell[0], cell[1], 14, avoid[-40:], seeds)
                new = []
                for t in got:
                    key = auto.key_of(t)
                    with wlock:
                        if done_key(key) or similar(t):
                            continue
                        known_words.append(words(t))
                    new.append({"q": t, "cat": cell[0], "recall": LEVEL_RECALL[cell[1]], "key": key, "src": "ai"})
                brainq[cell] = new
                q = new
            if not q:
                return None
            return q.pop(0)

    def seed_candidate(cell):
        li = core.LEVELS.index(cell[1])
        for j in (li, li - 1, li + 1):
            if not 0 <= j < 5:
                continue
            c = (cell[0], core.LEVELS[j])
            with wlock:
                lst = seedq.get(c, [])
                while lst:
                    aq = lst.pop()
                    if not done_key(aq["key"]) and not similar_exact(aq["q"]):
                        claimed.add(aq["key"])
                        return aq
        return None

    def similar_exact(q):
        w = words(q)
        return any(o == w for o in known_words)

    def make_candidate(cell):
        opts = []
        if use_llm:
            if any(seedq.get((cell[0], l)) for l in core.LEVELS[max(0, core.LEVELS.index(cell[1]) - 1) : core.LEVELS.index(cell[1]) + 2]):
                opts.append(("seed", 0.35))
            opts.append(("brain", 0.3))
        if by_cell.get(cell) or any(by_cell.get((cell[0], l)) for l in core.LEVELS):
            opts.append(("recipe", 0.4 if by_cell.get(cell) else 0.15))
        if not opts:
            return None
        pick = random.choices([o[0] for o in opts], weights=[o[1] for o in opts])[0]
        if pick == "recipe":
            c = recipe_candidate(cell)
            if c is None:
                return None
            r, f, v, key = c
            try:
                p = G.profile(r, f, v, cfg)
            except Exception as e:
                log("query failed for %s: %s" % (key, e))
                return None
            if p["level"] is None:
                with wlock:
                    st["done"][key] = "small"
                return None
            p["src_kind"] = "recipe"
            return p
        aq = seed_candidate(cell) if pick == "seed" else brain_candidate(cell)
        if aq is None:
            return None
        p = auto.profile(aq, llm, cfg, log)
        if p is None:
            with wlock:
                st["done"][aq["key"]] = "small"
            return None
        p["src_kind"] = aq["src"]
        return p

    def producer():
        while not state["stop"]:
            with wlock:
                total = sum(len(v) for v in sch.ready.values())
            if total >= buf_total:
                time.sleep(1)
                continue
            cell = None
            with wlock:
                for c in sch.order():
                    if len(sch.ready.get(c, [])) < buf_cell:
                        cell = c
                        break
            if cell is None:
                time.sleep(2)
                continue
            try:
                p = make_candidate(cell)
            except NoProvider:
                state["noai"] = True
                state["stop"] = True
                return
            except Exception as e:
                log("candidate problem: %s" % e)
                time.sleep(2)
                continue
            if p is None:
                sch.stuck(cell)
                continue
            sch.ok(cell)
            hint = p["level"] if p.get("level") else RECALL_LEVEL.get(int(p.get("hint", 3)), "hard")
            with wlock:
                sch.ready.setdefault((p["cat"], hint), []).append(p)

    def bump(item):
        lv = item.get("lv") or [item["lvl"]]
        for l in lv:
            k = (item["cat"], l)
            sch.counts[k] = sch.counts.get(k, 0) + (1.0 if l == item["lvl"] else 0.4)

    def process(picked):
        key = picked["key"]
        if G.dup(sigs + gen_sigs, [core.norm(a["n"]) for a in picked["ans"][:30]]):
            with wlock:
                st["done"][key] = "seen"
            log("skip %s (too close to an existing question)" % picked["q"])
            return
        p = picked
        if use_llm:
            p = G.refine(llm, picked, cfg, log)
            if p is None:
                with wlock:
                    st["done"][key] = "rejected"
                return
        item = G.finish(p, cfg)
        item["sig"] = [core.norm(a["n"]) for a in p["ans"][:30]]
        with wlock:
            if G.dup(gen_sigs, item["sig"]):
                st["done"][key] = "seen"
                return
            st["pending"].append(item)
            gen_sigs.append(("", "", set(item["sig"])))
            known_words.append(words(p["q"]))
            bump(item)
            st["done"][key] = "made"
            ids.add(core.make_id(key))
            st.setdefault("fixed", {})[core.make_id(key)] = int(cfg.get("repair_version", 1))
            state["made"] += 1
            recent["f"].append(p["fam"])
            recent["v"].append(p["vl"])
            multi = ""
            if len(item["lv"]) > 1:
                multi = "  [also %s]" % ", ".join(item["lv"][1:])
            line = "%-9s %-10s %5d answers  %s%s" % (item["cat"], item["lvl"], item["n"], p["q"], multi)
        log(line)
        with wlock:
            if len(st["pending"]) >= cfg["publish_every"]:
                G.flush(st, cfg, log)
            elif not test:
                G.save_state(st, cfg)

    def worker():
        while True:
            try:
                picked = jobs.get(timeout=1)
            except queue.Empty:
                if state["stop"]:
                    return
                continue
            ck = picked["_cell"]
            try:
                process(picked)
            except NoProvider:
                state["noai"] = True
                state["stop"] = True
            except Exception as e:
                log("problem with one question, skipped: %s" % e)
            finally:
                with wlock:
                    state["active"] -= 1
                    sch.infl[ck] = max(0, sch.infl.get(ck, 1) - 1)

    if use_llm and cfg.get("use_seeds", True):
        threading.Thread(target=seed_loader, daemon=True).start()
    else:
        seeds_ready.set()
    if use_llm and cfg.get("rescue", True) and not test:
        try:
            n = rescue.judge_all(st, cfg, llm, log, G.out_dir(cfg))
            if n:
                log("fixed %d questions from rejected guesses" % n)
                G.save_state(st, cfg)
        except NoProvider:
            state["noai"] = True
        except Exception as e:
            log("rescue problem: %s" % e)
    if use_llm and cfg.get("repair", True) and not test and not state["noai"]:
        try:
            rm = float(cfg.get("repair_minutes", 200))
            if deadline:
                rm = min(rm, (deadline - time.time()) / 60.0 - 20)
            if rm > 5:
                repair.run(st, cfg, llm, log, G.out_dir(cfg), rm, G.flush, wlock, workers)
                G.save_state(st, cfg)
        except NoProvider:
            state["noai"] = True
        except Exception as e:
            log("repair problem: %s" % e)
    for _ in range(max(1, int(cfg.get("producers", 3)))):
        threading.Thread(target=producer, daemon=True).start()
    ths = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in ths:
        t.start()
    log("started with %d worker%s%s" % (workers, "" if workers == 1 else "s", (", will stop after %d minutes" % minutes) if minutes else ""))
    last_rescue = time.time()
    last_report = time.time()
    try:
        while True:
            if state["noai"]:
                log("The free AI requests are used up for now, stopping. The next run continues.")
                break
            if deadline and time.time() > deadline:
                log("time is up")
                break
            with wlock:
                done_n = state["made"] + state["active"]
                total_ready = sum(len(v) for v in sch.ready.values())
                idle = state["active"] == 0 and total_ready == 0
            if limit and done_n >= limit:
                if state["active"] == 0:
                    break
                time.sleep(1)
                continue
            if time.time() - last_report > 600:
                last_report = time.time()
                log("progress: %d made, AI: %s" % (state["made"], llm.pool.status() if use_llm and hasattr(llm, "pool") else "-"))
            if use_llm and cfg.get("rescue", True) and not test and time.time() - last_rescue > 2400 and state["active"] == 0:
                last_rescue = time.time()
                try:
                    with wlock:
                        G.flush(st, cfg, log)
                        n = rescue.judge_all(st, cfg, llm, log, G.out_dir(cfg))
                        if n:
                            G.save_state(st, cfg)
                except NoProvider:
                    state["noai"] = True
                except Exception as e:
                    log("rescue problem: %s" % e)
            with wlock:
                busy = state["active"] >= workers
            if busy:
                time.sleep(0.5)
                continue
            picked = None
            with wlock:
                for c in sch.order():
                    lst = sch.ready.get(c, [])
                    if not lst:
                        continue
                    good = [p for p in lst if p["fam"] not in recent["f"][-4:] and p["vl"] not in recent["v"][-8:]]
                    picked = (good or lst)[0]
                    lst.remove(picked)
                    picked["_cell"] = c
                    state["active"] += 1
                    sch.infl[c] = sch.infl.get(c, 0) + 1
                    break
            if picked is None:
                time.sleep(1)
                continue
            jobs.put(picked)
    except KeyboardInterrupt:
        log("stopping, finishing the questions that are in progress")
    state["stop"] = True
    t_end = time.time() + 180
    while time.time() < t_end and any(t.is_alive() for t in ths):
        try:
            time.sleep(0.5)
        except KeyboardInterrupt:
            break
    with wlock:
        G.flush(st, cfg, log)
        G.publish(st, cfg, log, True)
    log("finished, %d new questions this run" % state["made"])


def stats(args=None):
    cfg = core.settings()
    out = os.path.join(os.path.dirname(BASE), "qdata")
    if not os.path.exists(os.path.join(out, "manifest.json")):
        out = G.out_dir(cfg)
    man = load_manifest(out)
    sigs = G.exists_sigs()
    c = base_counts(man, sigs)
    print("%-10s" % "" + "".join("%12s" % l for l in core.LEVELS))
    for cat in core.CATS:
        print("%-10s" % cat + "".join("%12d" % c.get((cat, l), 0) for l in core.LEVELS))
    print("questions made by the generator: %d" % len({e[0] for e in man["idx"]}))


def check():
    from llm import LLM
    cfg = core.settings()
    print("Matteus Games generator check")
    llm = LLM(cfg)
    names = llm.pool.names()
    if not names:
        print("  PROBLEM  no AI key found. Add a key as a secret (see SETUP.txt).")
    for name, ok, msg in llm.pool.ping():
        print("  %-8s %s" % ("OK" if ok else "PROBLEM", "%s: %s" % (name, msg)))
    for p in llm.pool.providers:
        if p.name == "github":
            import urllib.request
            try:
                rq = urllib.request.Request("https://models.github.ai/catalog/models", headers={"Authorization": "Bearer " + p.key, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "MatteusGames"})
                with urllib.request.urlopen(rq, timeout=30) as r:
                    print("  INFO     github model list: status %s, starts with: %s" % (r.status, r.read(300).decode("utf-8", "replace").replace("\n", " ")))
            except Exception as e:
                print("  INFO     github model list failed: %s" % str(e)[:300])
    try:
        core.sparql("SELECT ?x WHERE { ?x wdt:P31 wd:Q6256 } LIMIT 1", tries=1)
        print("  OK       Wikidata (QLever) answers")
    except Exception as e:
        print("  PROBLEM  Wikidata (QLever) does not answer: %s" % e)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print("usage: main.py run [--minutes=N] [--max=N] | check | stats")
    elif a[0] == "run":
        run(a[1:])
    elif a[0] == "check":
        check()
    elif a[0] == "stats":
        stats(a[1:])
