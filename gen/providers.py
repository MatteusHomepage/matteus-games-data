import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

UA = "MatteusGames-generator/4.0 (matteus-aydin.se)"

OPENAI_STYLE = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "env": "GROQ_API_KEY",
        "models": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "rpm": 20,
        "rpd": 900,
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "env": "CEREBRAS_API_KEY",
        "models": ["gpt-oss-120b", "llama-3.3-70b", "qwen-3-32b"],
        "rpm": 20,
        "rpd": 1200,
    },
    "mistral": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "env": "MISTRAL_API_KEY",
        "models": ["mistral-small-latest", "open-mistral-nemo"],
        "rpm": 25,
        "rpd": 3000,
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "env": "OPENROUTER_API_KEY",
        "models": ["meta-llama/llama-3.3-70b-instruct:free", "openai/gpt-oss-120b:free", "google/gemma-3-27b-it:free"],
        "rpm": 10,
        "rpd": 45,
    },
    "github": {
        "url": "https://models.github.ai/inference/chat/completions",
        "env": "GITHUB_MODELS_TOKEN",
        "models": ["openai/gpt-4.1-mini", "meta/Llama-3.3-70B-Instruct", "openai/gpt-4o-mini"],
        "rpm": 10,
        "rpd": 120,
    },
}

GEMINI = {"env": "GEMINI_API_KEY", "models": ["gemini-2.5-flash-lite", "gemini-2.5-flash"], "rpm": 10, "rpd": 400}
CLOUDFLARE = {"models": ["@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/meta/llama-3.1-8b-instruct"], "rpm": 20, "rpd": 150}


class ProviderError(Exception):
    pass


class NoProvider(Exception):
    pass


class BadReply(Exception):
    pass


def schema_hint(schema):
    if not schema:
        return ""
    props = schema.get("properties", {})
    parts = []
    for k, v in props.items():
        t = v.get("type", "string")
        if t == "array":
            it = v.get("items", {})
            if it.get("type") == "object":
                inner = ", ".join('"%s": %s' % (a, b.get("type", "string")) for a, b in it.get("properties", {}).items())
                t = "array of {%s}" % inner
            else:
                t = "array of %s" % it.get("type", "string")
        parts.append('"%s": %s' % (k, t))
    return "Reply with one JSON object only, no other text, with exactly these keys: {%s}." % ", ".join(parts)


def parse_json(txt):
    txt = re.sub(r"<think>.*?</think>", "", txt or "", flags=re.S).strip()
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt).strip()
    try:
        return json.loads(txt)
    except Exception:
        pass
    a = txt.find("{")
    b = txt.rfind("}")
    if a >= 0 and b > a:
        try:
            return json.loads(txt[a : b + 1])
        except Exception:
            pass
    raise BadReply("not json: %s" % txt[:120])


class Provider:
    def __init__(self, name, kind, models, key="", url="", rpm=10, rpd=0, weight=1.0, extra=None):
        self.name = name
        self.kind = kind
        self.models = list(models)
        self.dead_models = set()
        self.key = key
        self.url = url
        self.gap = 60.0 / max(1, rpm)
        self.rpd = rpd
        self.weight = weight
        self.extra = extra or {}
        self.next_ok = 0.0
        self.dead_until = 0.0
        self.fails = 0
        self.used = 0
        self.day = time.strftime("%Y-%m-%d", time.gmtime())
        self.lock = threading.Lock()
        self.warned = False

    def roll(self):
        d = time.strftime("%Y-%m-%d", time.gmtime())
        if d != self.day:
            self.day = d
            self.used = 0
            self.dead_until = 0.0
            self.fails = 0

    def usable(self, now):
        self.roll()
        if not self.models or all(m in self.dead_models for m in self.models):
            return False
        if self.rpd and self.used >= self.rpd:
            return False
        return now >= self.dead_until

    def model(self):
        for m in self.models:
            if m not in self.dead_models:
                return m
        return None

    def kill_model(self):
        m = self.model()
        if m:
            self.dead_models.add(m)

    def request(self, model, system, user, schema, max_tokens, temp, timeout):
        hint = schema_hint(schema)
        u = user + ("\n\n" + hint if hint and self.kind != "ollama" else "")
        if self.kind == "gemini":
            body = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": u}]}],
                "generationConfig": {"temperature": temp, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"},
            }
            if "2.5" in model:
                body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
            url = "%s/models/%s:generateContent?key=%s" % (self.extra.get("base", "https://generativelanguage.googleapis.com/v1beta"), model, self.key)
            d = self.post(url, body, {}, timeout)
            try:
                return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
            except Exception:
                raise BadReply("empty gemini reply: %s" % str(d)[:150])
        if self.kind == "cloudflare":
            url = "%s/accounts/%s/ai/run/%s" % (self.extra.get("base", "https://api.cloudflare.com/client/v4"), self.extra.get("account", ""), model)
            body = {
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": u}],
                "max_tokens": max_tokens,
                "temperature": temp,
            }
            d = self.post(url, body, {"Authorization": "Bearer " + self.key}, timeout)
            res = d.get("result") or {}
            r = res.get("response")
            if isinstance(r, (dict, list)):
                return json.dumps(r)
            if r is None:
                raise BadReply("empty cloudflare reply")
            return r
        if self.kind == "ollama":
            body = {
                "model": model,
                "stream": False,
                "think": False,
                "format": schema if schema else "json",
                "keep_alive": "10m",
                "options": {"temperature": temp, "num_ctx": int(self.extra.get("num_ctx", 3072)), "num_predict": max_tokens},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            }
            d = self.post(self.url, body, {}, timeout)
            return d.get("message", {}).get("content", "")
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": u}],
            "temperature": temp,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if "gpt-oss" in model:
            body["reasoning_effort"] = "low"
        hdr = {"Authorization": "Bearer " + self.key}
        if self.name == "openrouter":
            hdr["HTTP-Referer"] = "https://matteus-aydin.se"
            hdr["X-Title"] = "Matteus Games"
        d = self.post(self.url, body, hdr, timeout)
        try:
            return d["choices"][0]["message"]["content"] or ""
        except Exception:
            raise BadReply("empty reply: %s" % str(d)[:150])

    def post(self, url, body, headers, timeout):
        h = {"Content-Type": "application/json", "User-Agent": UA}
        h.update(headers)
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "replace")
            try:
                return json.loads(body)
            except Exception:
                raise BadReply("not json from server: %s" % (body[:150] or "empty"))
        except urllib.error.HTTPError as e:
            txt = ""
            try:
                txt = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            err = ProviderError("%s %s" % (e.code, txt))
            err.code = e.code
            err.retry = e.headers.get("Retry-After") if e.headers else None
            err.text = txt
            raise err


class Pool:
    def __init__(self, cfg, env=None, log=print):
        self.log = log
        self.env = env if env is not None else os.environ
        self.cfg = cfg
        self.providers = []
        self.lock = threading.Lock()
        self.calls = 0
        self.errors = 0
        conf = cfg.get("providers", {}) or {}
        for name, d in OPENAI_STYLE.items():
            key = self.env.get(d["env"], "")
            if name == "github" and not key:
                key = self.env.get("GITHUB_TOKEN", "") if self.env.get("GITHUB_ACTIONS") and cfg.get("use_github_models", True) else ""
            self.add(name, "openai", key, d["url"], d["models"], d["rpm"], d["rpd"], conf.get(name, {}))
        self.add("gemini", "gemini", self.env.get(GEMINI["env"], ""), "", GEMINI["models"], GEMINI["rpm"], GEMINI["rpd"], conf.get("gemini", {}))
        acct = self.env.get("CLOUDFLARE_ACCOUNT_ID", "")
        tok = self.env.get("CLOUDFLARE_API_TOKEN", "")
        self.add("cloudflare", "cloudflare", tok if acct else "", "", CLOUDFLARE["models"], CLOUDFLARE["rpm"], CLOUDFLARE["rpd"], conf.get("cloudflare", {}), {"account": acct})
        if cfg.get("ollama_url") and cfg.get("use_ollama", False):
            m = cfg.get("model", "qwen3:8b")
            self.add("ollama", "ollama", "local", cfg["ollama_url"].rstrip("/") + "/api/chat", [m], 600, 0, conf.get("ollama", {}), {"num_ctx": cfg.get("num_ctx", 3072)})

    def add(self, name, kind, key, url, models, rpm, rpd, over, extra=None):
        if not key:
            return
        if over.get("off"):
            return
        ms = over.get("models") or models
        p = Provider(name, kind, ms, key, url, over.get("rpm", rpm), over.get("rpd", rpd), over.get("weight", 1.0), extra)
        self.providers.append(p)

    def names(self):
        return [p.name for p in self.providers]

    def alive(self):
        return bool(self.providers)

    def pick(self, avoid=()):
        now = time.time()
        best = None
        for p in self.providers:
            if p.name in avoid or not p.usable(now):
                continue
            score = max(p.next_ok, now) + p.used * p.gap / max(0.1, p.weight) * 0.02
            if best is None or score < best[0]:
                best = (score, p)
        return best[1] if best else None

    def chat_json(self, system, user, schema=None, max_tokens=1500, temp=0.2, timeout=120, tries=6):
        waited = 0.0
        tried = []
        last = None
        for _ in range(tries):
            p = self.pick(avoid=tried[-2:] if len(self.providers) > 2 else ())
            if p is None:
                if not any(q.usable(time.time() + 3600) for q in self.providers):
                    raise NoProvider("every provider is out of free requests for now")
                soon = min((q.dead_until for q in self.providers if q.usable(time.time() + 3600)), default=0)
                nap = max(5, min(90, soon - time.time()))
                if waited > float(self.cfg.get("llm_wait", 240)):
                    raise NoProvider("waited too long for a free provider")
                time.sleep(nap)
                waited += nap
                continue
            with p.lock:
                now = time.time()
                if p.next_ok > now:
                    time.sleep(min(60, p.next_ok - now))
                p.next_ok = time.time() + p.gap
            model = p.model()
            if not model:
                continue
            tried.append(p.name)
            try:
                p.used += 1
                self.calls += 1
                txt = p.request(model, system, user, schema, max_tokens, temp, timeout)
                d = parse_json(txt)
                p.fails = 0
                return d
            except BadReply as e:
                last = e
                self.errors += 1
                p.fails += 1
                if p.fails >= 3:
                    p.dead_until = time.time() + 1800
            except ProviderError as e:
                last = e
                self.errors += 1
                code = getattr(e, "code", 0)
                text = (getattr(e, "text", "") or "").lower()
                if code == 429:
                    p.fails += 1
                    if re.search(r"per day|daily|day\b|quota|exhaust|credits", text) and p.fails >= 2:
                        p.dead_until = time.time() + 3600 * 3
                        self.log("%s looks out of requests for today, resting it for a while" % p.name)
                    else:
                        try:
                            wait = float(getattr(e, "retry", None) or 0)
                        except Exception:
                            wait = 0
                        p.dead_until = time.time() + max(wait, min(600, 20 * p.fails))
                elif code in (401, 403):
                    p.dead_until = time.time() + 86400
                    if not p.warned:
                        p.warned = True
                        self.log("%s refused the key (%s). Check the key in your secrets." % (p.name, code))
                elif code == 404 or (code == 400 and "model" in text):
                    p.kill_model()
                elif code == 400:
                    last = ProviderError("bad request: " + text[:120])
                else:
                    p.fails += 1
                    p.dead_until = time.time() + min(300, 15 * p.fails)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
                self.errors += 1
                p.fails += 1
                p.dead_until = time.time() + min(300, 15 * p.fails)
        raise NoProvider("no answer from any provider (%s)" % last)

    def status(self):
        out = []
        now = time.time()
        for p in self.providers:
            out.append("%s:%s used %d%s" % (p.name, p.model() or "none", p.used, " (resting)" if p.dead_until > now else ""))
        return ", ".join(out)

    def ping(self):
        out = []
        for p in self.providers:
            msg = ""
            for attempt in range(3):
                try:
                    m = p.model()
                    txt = p.request(m, "Reply with JSON only.", 'Return {"ok": true}', None, 60, 0.0, 40)
                    parse_json(txt)
                    out.append((p.name, True, "answers with %s" % m))
                    msg = ""
                    break
                except Exception as e:
                    msg = "%s" % str(e)[:200]
                    if "429" in msg and attempt < 2:
                        time.sleep(8)
                        continue
                    break
            if msg:
                out.append((p.name, False, msg))
        return out
