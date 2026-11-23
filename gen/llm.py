import random
import time

import core
from providers import Pool, NoProvider

CAT_DESC = {
    "general": "everyday things, objects, jobs, household items, brands and odd topics",
    "geography": "countries, cities, rivers, mountains, islands, flags, borders and landmarks",
    "food": "dishes, snacks, drinks, ingredients, cuisines and food brands",
    "nature": "animals, plants, wildlife, pets, habitats and natural things",
    "history": "people, empires, wars, events, rulers, inventions and eras",
    "words": "languages, spelling, grammar, word patterns, names and letters",
    "movies": "films, TV shows, characters, actors, directors and studios",
    "music": "artists, bands, songs, albums, instruments and genres",
    "games": "video games, board games, characters, consoles and game companies",
    "sport": "sports, teams, athletes, leagues, tournaments and equipment",
    "science": "chemistry, physics, biology, space, medicine, technology and inventions",
}

LEVEL_DESC = {
    "easy": "Easy: almost every adult can name five or more answers in ten seconds, and there are hundreds of valid answers (Name a country. Name a fruit. Name a farm animal.)",
    "medium": "Medium: most adults can name five, but the full list is long (Name a footballer. Name a car brand. Name a dog breed. Name a Disney movie.)",
    "hard": "Hard: about half of adults can name five, and the rest have to think (Name a river longer than 1,000 km. Name a programming language. Name a 1990s band.)",
    "expert": "Expert: only people with a real interest can name five (Name a 2010s band. Name a cricketer. Name a mountain over 6,000 metres.)",
    "impossible": "Impossible: almost nobody can name five, but many valid answers exist for specialists (Name a mollusk. Name a bishop. Name an album from 1974. Name a beetle.)",
}


class LLM:
    def __init__(self, cfg, log=print):
        self.cfg = cfg
        self.pool = Pool(cfg, log=log)
        self.rounds = int(cfg.get("likely_rounds", 1))
        self.log = log

    def alive(self):
        return self.pool.alive()

    def ask(self, system, user, schema, max_tokens=1500, temp=0.2):
        try:
            return self.pool.chat_json(system, user, schema, max_tokens=max_tokens, temp=temp)
        except NoProvider:
            raise
        except Exception:
            return None

    def review(self, question, names, tail=None):
        schema = {
            "type": "object",
            "properties": {
                "keep": {"type": "boolean"},
                "fun": {"type": "integer"},
                "better": {"type": "string"},
                "words_known": {"type": "boolean"},
                "ten": {"type": "boolean"},
                "recall": {"type": "integer"},
                "misfits": {"type": "array", "items": {"type": "string"}},
            },
        }
        system = (
            "You check and grade trivia questions for a typing game where players type any valid answer from memory. "
            "The players are ordinary adults, mostly from Sweden and the rest from the US and the UK. Most of them are not experts in anything. "
            "Grade recall from 1 to 5 by how many different valid answers an ordinary adult could name in ten seconds. "
            "1 = almost everyone can name five or more. 2 = most adults can name five. 3 = about half can name five. 4 = only people with a real interest can. 5 = almost nobody can. "
            "Examples: Name a country = 1. Name an animal = 1. Name a fruit = 1. Name a Swedish city = 1. Name a Disney movie = 1. "
            "Name a footballer = 2. Name a car brand = 2. Name a Formula 1 driver = 2. Name a river longer than 1,000 km = 3. Name a programming language = 3. "
            "Name a band that formed in the 1990s = 3. Name a band that formed in the 2010s = 4. Name a cricketer = 4. Name a mountain taller than 6,000 metres = 4. "
            "Name a mollusk = 5. Name a Swedish painter = 4. Name an album that came out in 1974 = 5."
        )
        t = ""
        if tail:
            t = "\nLess famous answers picked from further down the list: %s\n" % "; ".join(tail)
        user = (
            'Question: "%s"\nFamous valid answers: %s%s\n'
            "Return JSON. keep: true only if the question is clear, natural English and the famous answers really fit it. "
            "fun: 1 to 5, how interesting the question is for players. "
            "better: a cleaner wording of the same question starting with the word Name, or an empty string if the wording is already fine. "
            "words_known: false if the question uses a word or category that most ordinary adults would not know or could not explain, otherwise true. "
            "ten: true only if an ordinary adult could name ten different valid answers. "
            "recall: 1 to 5 as explained. "
            "misfits: the answers from the less famous list that do NOT fit the question (empty list if all fit)."
            % (question, "; ".join(names), t)
        )
        for _ in range(2):
            d = self.ask(system, user, schema, max_tokens=600)
            if isinstance(d, dict) and isinstance(d.get("keep"), bool) and isinstance(d.get("recall"), (int, float)):
                d["recall"] = max(1, min(5, int(d["recall"])))
                d["fun"] = int(d.get("fun") or 3) if isinstance(d.get("fun"), (int, float)) else 3
                if not isinstance(d.get("words_known"), bool):
                    d["words_known"] = True
                if not isinstance(d.get("ten"), bool):
                    d["ten"] = d["recall"] <= 2
                if not isinstance(d.get("better"), str):
                    d["better"] = ""
                d["misfits"] = [x for x in d.get("misfits", []) if isinstance(x, str)] if isinstance(d.get("misfits"), list) else []
                return d
            time.sleep(1)
        return None

    def recall(self, question, count=40):
        schema = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "string"}}}}
        system = "You are an expert at trivia and know what ordinary people say first. The players are mostly from Sweden, so Swedish answers are familiar to them when they fit the question."
        user = (
            'Question: "%s"\nList the %d answers that ordinary people would say first when asked this, '
            "most likely first. Use the common English name of each answer. Real, correct answers only. Return JSON." % (question, count)
        )
        for _ in range(2):
            d = self.ask(system, user, schema, max_tokens=1200, temp=0.3)
            if isinstance(d, dict):
                out = [x.strip() for x in d.get("answers", []) if isinstance(x, str) and x.strip()]
                if out:
                    return out
        return None

    def likely(self, question, names, rounds=None):
        rounds = rounds or self.rounds
        schema = {
            "type": "object",
            "properties": {
                "scores": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"name": {"type": "string"}, "pct": {"type": "integer"}}},
                }
            },
        }
        system = "You estimate how people answer trivia questions. Be realistic: most answers are named by very few people. The players are mostly from Sweden, so Swedish answers are more familiar to them than to most people."
        tot = {n: [] for n in names}
        ok = 0
        for r in range(rounds):
            order = names[:]
            random.shuffle(order)
            user = (
                'Question: "%s"\nCandidate answers in random order:\n%s\n\n'
                "For each candidate give pct, from 0 to 100, the share of people who would name it among their first answers "
                "if asked this question out loud. Return JSON with one entry per candidate, using the exact names."
                % (question, "\n".join(order))
            )
            d = self.ask(system, user, schema, max_tokens=2200)
            if not isinstance(d, dict):
                continue
            got = {}
            for s in d.get("scores", []) if isinstance(d.get("scores"), list) else []:
                if isinstance(s, dict) and s.get("name") in tot and isinstance(s.get("pct"), (int, float)):
                    got[s["name"]] = max(0, min(100, s["pct"]))
            if len(got) >= 0.8 * len(names):
                ok += 1
                for n, v in got.items():
                    tot[n].append(v)
        if ok == 0:
            return None
        return {n: (sum(v) / len(v) if v else None) for n, v in tot.items()}

    def brainstorm(self, cat, level, n, avoid, seeds=()):
        schema = {"type": "object", "properties": {"questions": {"type": "array", "items": {"type": "string"}}}}
        system = (
            "You write short trivia prompts for a typing game. A player sees a prompt like 'Name a river in Europe.' and types any valid answer from memory. "
            "The more valid answers a prompt has, the better; a good prompt has hundreds or thousands of valid answers that can be checked against a public database such as Wikipedia or Wikidata. "
            "The prompt must be clear, start with 'Name', and have a clear yes or no test for every answer. "
            "No opinions, no 'best', no 'favourite', no prompts about the present moment, no prompts that need a picture."
        )
        ex = ""
        if seeds:
            ex = "Style examples: %s.\n" % "; ".join(seeds)
        av = ""
        if avoid:
            av = "Do not repeat or rephrase these prompts that already exist: %s.\n" % "; ".join(avoid)
        user = (
            "Category: %s (%s).\nTarget difficulty: %s\n%sWrite %d new, different prompts for this category at exactly this difficulty. Mix broad prompts and narrower ones (by country, decade, letter, type or other limit). "
            "%sReturn JSON with the key questions."
            % (cat, CAT_DESC.get(cat, ""), LEVEL_DESC[level], ex, n, av)
        )
        d = self.ask(system, user, schema, max_tokens=1400, temp=0.9)
        if not isinstance(d, dict):
            return []
        out = []
        for q in d.get("questions", []) if isinstance(d.get("questions"), list) else []:
            if isinstance(q, str):
                q = q.strip().rstrip("?")
                if q.lower().startswith("name ") and 12 <= len(q) <= 110:
                    out.append(q if q.endswith(".") else q + ".")
        return out

    def classify(self, questions):
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"q": {"type": "integer"}, "cat": {"type": "string"}, "recall": {"type": "integer"}}},
                }
            },
        }
        system = "You sort trivia prompts for a typing game into categories and grade how hard they are."
        cats = "; ".join("%s = %s" % (k, v) for k, v in CAT_DESC.items())
        lst = "\n".join("%d. %s" % (i, q) for i, q in enumerate(questions))
        user = (
            "Categories: %s.\n\nFor each numbered prompt give cat (one of the category names) and recall, 1 to 5: how many ordinary adults can name five valid answers in ten seconds "
            "(1 = almost everyone, 3 = about half, 5 = almost nobody).\n\n%s\n\nReturn JSON with the key items, one entry per prompt, q being its number." % (cats, lst)
        )
        d = self.ask(system, user, schema, max_tokens=3000, temp=0.1)
        out = {}
        if isinstance(d, dict) and isinstance(d.get("items"), list):
            for x in d["items"]:
                try:
                    i = int(x["q"])
                    c = str(x["cat"]).strip().lower()
                    r = max(1, min(5, int(x["recall"])))
                except Exception:
                    continue
                if c in CAT_DESC and 0 <= i < len(questions):
                    out[i] = (c, r)
        return out

    def spec(self, question):
        schema = {
            "type": "object",
            "properties": {
                "classes": {"type": "array", "items": {"type": "string"}},
                "lists": {"type": "array", "items": {"type": "string"}},
                "names": {"type": "array", "items": {"type": "string"}},
            },
        }
        system = "You prepare answer lists for trivia prompts using Wikipedia and Wikidata."
        user = (
            'Prompt: "%s"\n'
            "Return JSON. classes: up to 4 English names of Wikidata classes whose members are all valid answers (for example 'mollusc', 'fruit', 'rapper', 'film', 'lake'), most useful first. "
            "lists: up to 3 exact titles of English Wikipedia list pages that list valid answers (for example 'List of fruits'), only titles you are sure exist. "
            "names: 40 valid answers, the ones people would think of first, using their Wikipedia article titles." % question
        )
        d = self.ask(system, user, schema, max_tokens=1500, temp=0.2)
        if not isinstance(d, dict):
            return None
        out = {}
        for k in ("classes", "lists", "names"):
            v = d.get(k)
            out[k] = [x.strip() for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []
        return out

    def judge_guess(self, question, names, guess):
        schema = {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "canonical": {"type": "string"},
                "same_as": {"type": "string"},
                "aliases": {"type": "array", "items": {"type": "string"}},
            },
        }
        system = (
            "You judge guesses in a trivia typing game. The player had to type a valid answer to the prompt. "
            "A guess is valid only if it is a real, correct answer; typos of a real answer are valid. Be strict about made up names, jokes and wrong categories."
        )
        user = (
            'Prompt: "%s"\nSome answers already accepted: %s\n\nPlayer guess: "%s"\n'
            "Return JSON. valid: true if the guess is a real, correct answer to the prompt. canonical: the correct common English name of that answer. "
            "same_as: if it is just another spelling or name for one of the accepted answers, that accepted answer exactly as written, otherwise an empty string. "
            "aliases: up to 3 other common spellings of it." % (question, "; ".join(names[:60]), guess)
        )
        d = self.ask(system, user, schema, max_tokens=300, temp=0.0)
        if not isinstance(d, dict) or not isinstance(d.get("valid"), bool):
            return None
        d["canonical"] = d.get("canonical").strip() if isinstance(d.get("canonical"), str) else ""
        d["same_as"] = d.get("same_as").strip() if isinstance(d.get("same_as"), str) else ""
        d["aliases"] = [x.strip() for x in d.get("aliases", []) if isinstance(x, str) and x.strip()][:3] if isinstance(d.get("aliases"), list) else []
        return d
