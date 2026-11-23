CLS = "?i wdt:P31/wdt:P279* wd:%s ."
OCC = "?i wdt:P31 wd:Q5 . ?i wdt:P106 wd:%s ."


def cls(q):
    return CLS % q


def occ(q):
    return OCC % q


def works(prop, m):
    return " { SELECT ?i (COUNT(DISTINCT ?w) AS ?nw) WHERE { ?w wdt:%s ?i } GROUP BY ?i HAVING (COUNT(DISTINCT ?w) >= %d) }" % (prop, m)


R = []
AWARD = r"(Prize|Award|Medal|Golden Globe|BAFTA|Emmy|Grammy|Oscar|Cup|Trophy)"
POST = r"^(Prime Minister|President|Minister|Governor|Mayor|Chancellor|Speaker|Secretary) of (?!the Duchy)"


def F(key, kind, prop, tpl, base, min_n=40, top=30, ok=None, rx=None):
    return {"key": key, "kind": kind, "prop": prop, "tpl": tpl, "base": base, "min_n": min_n, "top": top, "ok": ok, "rx": rx}


def add(cat, key, pat, min_sl, facets, noun=None, label="l", title=False, w=1.0, s=None, P=None):
    R.append({"cat": cat, "key": key, "pat": pat, "min_sl": min_sl, "facets": facets, "label": label, "noun": noun, "title": title, "w": w, "s": s, "P": P})


TITLE_WORDS = [
    "love", "night", "day", "dream", "fire", "heart", "star", "sun", "moon", "black", "blue", "red", "white", "gold",
    "king", "queen", "girl", "boy", "man", "world", "time", "life", "dance", "rock", "blood", "ghost", "angel",
    "devil", "summer", "rain", "road", "home", "death", "war", "island", "city", "money", "baby", "dark", "light",
]
TITLE_RX = [
    ("colour", r"\\b(red|blue|green|black|white|yellow|pink|purple|golden|gold|silver|orange|brown|grey|gray)\\b", "with a colour in the title", 1.4),
    ("number", r"\\b(one|two|three|four|five|six|seven|eight|nine|ten)\\b|[0-9]", "with a number in the title", 2.0),
    ("animal", r"\\b(dog|cat|wolf|lion|tiger|bear|bird|eagle|horse|snake|fox|fish|shark|rabbit|monkey|dragon|spider|bull|crow|raven|mouse|rat|pig|cow|duck|bee|butterfly)s?\\b", "with an animal in the title", 2.0),
    ("body", r"\\b(heart|eye|eyes|hand|hands|head|blood|bone|bones|skin|face|soul|mind|lips|tongue|arm|arms|leg|legs)\\b", "with a body part in the title", 2.2),
    ("oneword", r"^[^ ]+$", "with a one-word title", 1.4),
    ("twowords", r"^[^ ]+ [^ ]+$", "with a two-word title", 1.4),
    ("long", r"^([^ ]+ ){5,}[^ ]+$", "with a title of six words or more", 2.6),
    ("question", r"\\?", "with a question mark in the title", 3.0),
    ("name", r"\\b(john|mary|david|michael|james|peter|paul|anna|sarah|jack|tom|billy|johnny|maria|lucy|jane|alice|rose)\\b", "with a first name in the title", 2.4),
    ("place", r"\\b(paris|london|new york|america|africa|texas|california|china|rome|berlin|tokyo|vegas|miami|chicago|hollywood|jamaica|brooklyn)\\b", "with a place name in the title", 2.4),
]


def title_facets(noun_plural_phrase):
    out = []
    for k, rx, ph, b in TITLE_RX:
        out.append(F("t_" + k, "regex", None, "Name %s " % noun_plural_phrase + ph + ".", b, 150, 1, None, rx))
    for w in TITLE_WORDS:
        out.append(F("w_" + w, "regex", None, "Name %s with \"%s\" in the title." % (noun_plural_phrase, w.capitalize()), 1.5, 150, 1, None, r"\\b%s\\b" % w))
    return out


add("geography", "city", cls("Q515"), 4, [
    F("country", "entity", "P17", "Name a city in {v}.", 2.0),
    F("letter", "letter", None, "Name a city starting with the letter {v}.", 1.8, 80, 22),
], "city")
add("geography", "river", cls("Q4022"), 2, [F("country", "entity", "P17", "Name a river in {v}.", 2.8, 30)])
add("geography", "mountain", cls("Q8502"), 3, [F("country", "entity", "P17", "Name a mountain in {v}.", 2.8, 30)])
add("geography", "lake", cls("Q23397"), 2, [F("country", "entity", "P17", "Name a lake in {v}.", 3.0, 30)])
add("geography", "island", cls("Q23442"), 2, [F("country", "entity", "P17", "Name an island belonging to {v}.", 3.0, 30)])
add("geography", "airport", cls("Q1248784"), 2, [F("country", "entity", "P17", "Name an airport in {v}.", 3.2, 30)])
add("geography", "castle", cls("Q23413"), 2, [F("country", "entity", "P17", "Name a castle in {v}.", 3.0, 30)])
add("geography", "bridge", cls("Q12280"), 2, [F("country", "entity", "P17", "Name a bridge in {v}.", 3.4, 30)])
add("geography", "museum", cls("Q33506"), 2, [F("country", "entity", "P17", "Name a museum in {v}.", 3.4, 40)])
add("geography", "stadium", cls("Q483110"), 2, [F("country", "entity", "P17", "Name a stadium in {v}.", 3.0, 40)])
add("geography", "university", cls("Q3918"), 2, [F("country", "entity", "P17", "Name a university in {v}.", 2.6, 60)])

add("movies", "film", cls("Q11424"), 2, [
    F("country", "entity", "P495", "Name a film from {v}.", 2.4, 60),
    F("genre", "entity", "P136", "Name a {v}.", 1.2, 80),
    F("decade", "decade", "P577", "Name a film released in the {v}s.", 1.6, 100),
    F("director", "entity", "P57", "Name a film directed by {v}.", 2.3, 30),
    F("cast", "entity", "P161", "Name a film starring {v}.", 1.8, 30),
] + title_facets("a film"), "film", title=True)
add("movies", "series", cls("Q5398426"), 3, [
    F("country", "entity", "P495", "Name a TV series from {v}.", 2.4, 40),
    F("cast", "entity", "P161", "Name a TV series starring {v}.", 2.4, 25),
    F("decade", "decade", "P580", "Name a TV series that started in the {v}s.", 1.8, 60),
] + title_facets("a TV series"), "TV series", title=True)
add("movies", "animated", cls("Q202866"), 3, [F("country", "entity", "P495", "Name an animated film from {v}.", 2.4, 40)])
add("movies", "actor", occ("Q33999") + works("P161", 3), 6, [
    F("country", "entity", "P27", "Name an actor from {v}.", 2.0, 60),
    F("award", "entity", "P166", "Name an actor who won the {v}.", 2.4, 40, 30, AWARD),
])
add("movies", "director", occ("Q2526255") + works("P57", 3), 5, [F("country", "entity", "P27", "Name a film director from {v}.", 3.2, 40)])

add("music", "album", cls("Q482994"), 2, [
    F("artist", "entity", "P175", "Name an album by {v}.", 1.6, 15),
    F("genre", "entity", "P136", "Name an album in the {v} genre.", 2.6, 80),
    F("decade", "decade", "P577", "Name an album released in the {v}s.", 1.8, 100),
] + title_facets("an album"), "album", title=True)
add("music", "song", cls("Q7366"), 2, [
    F("artist", "entity", "P175", "Name a song by {v}.", 1.5, 20),
    F("decade", "decade", "P577", "Name a song released in the {v}s.", 1.8, 100),
] + title_facets("a song"), "song", title=True)
add("music", "band", cls("Q215380"), 4, [F("country", "entity", "P495", "Name a band from {v}.", 2.2, 60)])
add("music", "singer", occ("Q177220") + works("P175", 3), 5, [F("country", "entity", "P27", "Name a singer from {v}.", 2.2, 60)])
add("music", "composer", occ("Q36834") + works("P86", 3), 5, [F("country", "entity", "P27", "Name a composer from {v}.", 3.4, 50)])

add("sport", "footballer", occ("Q937857") + " ?i wdt:P413 ?pos .", 4, [
    F("club", "entity", "P54", "Name a footballer who played for {v}.", 2.2, 60),
    F("country", "entity", "P27", "Name a footballer from {v}.", 1.8, 100),
])
add("sport", "hockey", occ("Q11774891") + " ?i wdt:P54 ?tm .", 3, [
    F("club", "entity", "P54", "Name an ice hockey player who played for {v}.", 3.0, 40),
    F("country", "entity", "P27", "Name an ice hockey player from {v}.", 2.8, 60),
])
add("sport", "tennis", occ("Q10833314"), 3, [F("country", "entity", "P27", "Name a tennis player from {v}.", 2.8, 40)])
add("sport", "basketball", occ("Q3665646") + " ?i wdt:P54 ?tm .", 4, [
    F("club", "entity", "P54", "Name a basketball player who played for {v}.", 2.8, 40),
    F("country", "entity", "P27", "Name a basketball player from {v}.", 2.6, 50),
])
add("sport", "driver", occ("Q378622"), 3, [F("country", "entity", "P27", "Name a racing driver from {v}.", 3.6, 40)])
add("sport", "club", cls("Q476028"), 3, [
    F("country", "entity", "P17", "Name a football club in {v}.", 2.4, 40),
    F("league", "entity", "P118", "Name a team that has played in the {v}.", 2.8, 20),
])

add("games", "videogame", cls("Q7889"), 2, [
    F("genre", "entity", "P136", "Name a {v}.", 1.4, 60),
    F("platform", "entity", "P400", "Name a video game released for {v}.", 1.8, 80),
    F("decade", "decade", "P577", "Name a video game released in the {v}s.", 2.0, 100),
    F("country", "entity", "P495", "Name a video game from {v}.", 2.8, 60),
    F("developer", "entity", "P178", "Name a video game developed by {v}.", 2.8, 60),
] + title_facets("a video game"), "video game", title=True)

add("science", "scientist", occ("Q901"), 5, [
    F("country", "entity", "P27", "Name a scientist from {v}.", 3.2, 60),
    F("award", "entity", "P166", "Name a scientist who won the {v}.", 3.4, 30, 30, AWARD),
])
add("science", "physicist", occ("Q169470"), 4, [F("country", "entity", "P27", "Name a physicist from {v}.", 3.5, 40)])
add("science", "chemist", occ("Q593644"), 4, [F("country", "entity", "P27", "Name a chemist from {v}.", 3.6, 40)])
add("science", "mathematician", occ("Q170790"), 4, [F("country", "entity", "P27", "Name a mathematician from {v}.", 3.6, 40)])

add("history", "politician", occ("Q82955"), 5, [
    F("country", "entity", "P27", "Name a politician from {v}.", 2.4, 80),
    F("position", "entity", "P39", "Name a person who served as {v}.", 2.6, 30, 30, POST),
])
add("history", "battle", cls("Q178561"), 2, [
    F("country", "entity", "P17", "Name a battle that took place in {v}.", 3.0, 30),
    F("war", "entity", "P361", "Name a battle that was part of the {v}.", 3.0, 25),
])

add("food", "dish", cls("Q746549"), 2, [F("country", "entity", "P495", "Name a dish from {v}.", 1.8, 25)])
add("food", "food", cls("Q2095"), 2, [F("country", "entity", "P495", "Name a food from {v}.", 1.8, 25)])
add("food", "drink", cls("Q40050"), 2, [F("country", "entity", "P495", "Name a drink from {v}.", 2.0, 25)])

add("general", "writer", occ("Q36180") + works("P50", 2), 5, [F("country", "entity", "P27", "Name a writer from {v}.", 2.8, 60)])
add("general", "book", cls("Q7725634"), 3, [
    F("author", "entity", "P50", "Name a book by {v}.", 2.0, 15),
    F("country", "entity", "P495", "Name a book from {v}.", 2.6, 80),
] + title_facets("a book"), "book", title=True)

add("nature", "endemic", "?i wdt:P31 wd:Q16521 . ?i wdt:P105 wd:Q7432 . ?i wdt:P1843 ?l .", 1, [
    F("country", "entity", "P183", "Name an animal or plant that is native only to {v}.", 3.4, 40),
], label="pat")


DULL = {
    "actor": 0.15, "director": 0.1, "singer": 0.15, "composer": 0.1, "tennis": 0.12, "driver": 0.08,
    "scientist": 0.1, "physicist": 0.08, "chemist": 0.06, "mathematician": 0.06, "hockey": 0.08, "basketball": 0.12,
    "writer": 0.12, "politician": 0.12, "museum": 0.1, "stadium": 0.12, "university": 0.08, "bridge": 0.08,
    "airport": 0.08, "castle": 0.1, "lake": 0.12, "island": 0.12, "battle": 0.2, "band": 0.25, "footballer": 0.3,
    "club": 0.2, "river": 0.2, "mountain": 0.2, "endemic": 0.5,
}
for _r in R:
    if _r["key"] in DULL:
        _r["w"] = DULL[_r["key"]]


LETTERS = list("ABCDEFGHIJKLMNOPRSTUVW")
ENDINGS_PLACE = [
    ("ton", r"(ton|town)$", "ending in -ton or -town"),
    ("ville", r"ville$", "ending in -ville"),
    ("burg", r"(burg|burgh|berg)$", "ending in -burg, -burgh or -berg"),
    ("land", r"land$", "ending in -land"),
    ("ford", r"(ford|field)$", "ending in -ford or -field"),
    ("by", r"(by|köping|stad)$", "ending in -by, -köping or -stad"),
]
ENDINGS_PERSON = [
    ("son", r"son$", "whose name ends in -son"),
    ("sen", r"(sen|ssen)$", "whose name ends in -sen"),
    ("ski", r"(ski|sky)$", "whose name ends in -ski"),
    ("ov", r"(ov|off|ova)$", "whose name ends in -ov"),
    ("ez", r"(ez|es)$", "whose name ends in -ez"),
    ("mc", r"\\b(Mc|Mac)[A-Z]", "whose name starts with Mc or Mac"),
]
GENERIC_TW = [
    ("one", r"^[^ ]+$", "with a one-word name", 0.2),
    ("two", r"^[^ ]+ [^ ]+$", "with a two-word name", 0.2),
    ("five", r"^[A-Za-z]{5}$", "with exactly five letters", 0.9),
    ("six", r"^[A-Za-z]{6}$", "with exactly six letters", 0.9),
    ("four", r"^[A-Za-z]{4}$", "with exactly four letters", 0.9),
    ("dbl", r"(aa|bb|cc|dd|ee|ff|gg|ll|mm|nn|oo|pp|rr|ss|tt|zz)", "containing a double letter", 0.4),
    ("z", r"[zZ]", "containing the letter Z", 0.8),
    ("q", r"[qQ]", "containing the letter Q", 1.2),
    ("x", r"[xX]", "containing the letter X", 1.0),
]
WORDS = [
    ("colour", r"\\b(red|blue|green|black|white|yellow|pink|purple|golden|gold|silver|orange|brown|grey|gray)\\b", "containing a colour", 0.1),
    ("animal", r"\\b(dog|cat|wolf|lion|tiger|bear|bird|eagle|horse|snake|fox|fish|shark|rabbit|monkey|dragon|spider|bull|crow|raven|mouse|pig|duck|bee)s?\\b", "containing an animal", 0.3),
    ("body", r"\\b(heart|eye|eyes|hand|hands|head|blood|bone|bones|skin|face|soul|mind|lips|arm|leg|legs)\\b", "containing a body part", 0.4),
    ("number", r"\\b(one|two|three|four|five|six|seven|eight|nine|ten)\\b|[0-9]", "containing a number", 0.2),
    ("place", r"\\b(paris|london|new york|america|africa|texas|california|china|rome|berlin|tokyo|vegas|miami|chicago|hollywood|jamaica|brooklyn)\\b", "containing a place", 0.4),
    ("name", r"\\b(john|mary|david|michael|james|peter|paul|anna|sarah|jack|tom|billy|johnny|maria|lucy|jane|alice|rose)\\b", "containing a first name", 0.3),
]
TEMPL_LETTER = [
    "Name {a} that starts with the letter {v}.",
    "{P} that start with the letter {v}.",
    "Think of {a} beginning with {v}.",
    "Give me {a} that starts with {v}.",
    "Can you name {a} starting with {v}?",
]
TEMPL_TW = [
    "Name {a} {w}.",
    "{P} {w}.",
    "Think of {a} {w}.",
    "Give me {a} {w}.",
    "Can you name {a} {w}?",
]


TEMPL_LETTER_P = [
    "Name {a} whose name starts with {v}.",
    "{P} whose names start with {v}.",
    "Think of {a} whose name begins with {v}.",
    "Give me {a} with a name starting with {v}.",
    "Can you name {a} whose name starts with {v}?",
]


def broad(cat, key, pat, min_sl, s, P, base, w=2.0, label="l", people=False, place=False, words=True, generic=True, extra=None, letters_w=1):
    TL = TEMPL_LETTER_P if people else TEMPL_LETTER
    fac = [F("letter", "letter", None, TL, base, 80, 22)]
    if generic:
        for k, rx, ph, add_ in GENERIC_TW:
            fac.append(F("g_" + k, "regex", None, TEMPL_TW, base + add_, 150, 1, None, rx))
            fac[-1]["w_"] = ph
    if words:
        for k, rx, ph, add_ in WORDS:
            fac.append(F("x_" + k, "regex", None, TEMPL_TW, base + add_, 150, 1, None, rx))
            fac[-1]["w_"] = ph
    for k, rx, ph in (ENDINGS_PERSON if people else (ENDINGS_PLACE if place else [])):
        fac.append(F("e_" + k, "regex", None, TEMPL_TW, base + 0.5, 150, 1, None, rx))
        fac[-1]["w_"] = ph
    for e in extra or []:
        fac.append(e)
    for f_ in fac:
        if f_["tpl"] is TL:
            f_["w_"] = ""
    add(cat, key, pat, min_sl, fac, w=w, s=s, P=P, label=label)


ANIMAL = "?i wdt:P31 wd:Q16521 . ?i wdt:P105 wd:Q7432 . ?i wdt:P171* wd:%s . ?i wdt:P1843 ?l ."
broad("nature", "animal", ANIMAL % "Q729", 2, "animal", "Animals", 1.2, 2.5, label="pat", words=False)
broad("nature", "bird", ANIMAL % "Q5113", 2, "bird", "Birds", 1.7, 1.5, label="pat", words=False)
broad("nature", "mammal", ANIMAL % "Q7377", 2, "mammal", "Mammals", 1.5, 1.5, label="pat", words=False)
broad("nature", "plant", "?i wdt:P31 wd:Q16521 . ?i wdt:P105 wd:Q7432 . ?i wdt:P171* wd:Q756 . ?i wdt:P1843 ?l .", 2, "plant", "Plants", 1.8, 1.5, label="pat", words=False)
broad("geography", "bcity", cls("Q515"), 4, "city", "Cities", 1.4, 2.0, place=True, words=False)
broad("movies", "bfilm", cls("Q11424"), 2, "film", "Films", 1.4, 2.5, extra=[
    F("series", "entity", "P179", "Name {a} that is part of {v}.", 1.6, 8, 40),
])
broad("movies", "bseries", cls("Q5398426"), 3, "TV series", "TV series", 1.6, 1.5)
broad("music", "bsong", cls("Q7366"), 2, "song", "Songs", 1.5, 2.5)
broad("music", "balbum", cls("Q482994"), 2, "album", "Albums", 1.8, 1.2)
broad("music", "bband", cls("Q215380"), 3, "band", "Bands", 1.8, 1.5, extra=[
    F("the", "regex", None, "Name {a} with \"The\" at the start of its name.", 1.2, 150, 1, None, r"^The ")
])
broad("games", "bgame", cls("Q7889"), 2, "video game", "Video games", 1.8, 2.0, extra=[
    F("series", "entity", "P179", "Name {a} that is part of {v}.", 1.8, 8, 40),
])
broad("general", "bbook", cls("Q7725634"), 3, "book", "Books", 2.0, 1.2)
broad("general", "bbrand", cls("Q431289"), 5, "brand", "Brands", 1.5, 2.0)
broad("food", "bfood", cls("Q2095"), 2, "food or dish", "Foods and dishes", 1.2, 2.0, words=False)
broad("food", "bdrink", cls("Q40050"), 2, "drink", "Drinks", 1.4, 1.5, words=False)
broad("sport", "bplayer", occ("Q937857") + " ?i wdt:P413 ?pos .", 4, "footballer", "Footballers", 1.8, 1.5, people=True, words=False, generic=False)
broad("movies", "bperson", "?i wdt:P31 wd:Q5 .", 25, "famous person", "Famous people", 1.8, 3.0, people=True, words=False, generic=False, extra=[
    F("given", "entity", "P735", ["Name {a} named {v}.", "Famous people called {v}.", "Think of someone called {v}.", "Name a famous {v}."], 1.6, 60, 40, r"^[A-Z][a-zåäöé]+$"),
    F("surname", "entity", "P734", ["Name a famous person with the surname {v}.", "Famous people with the last name {v}.", "Think of someone whose last name is {v}."], 1.8, 40, 40),
])
broad("movies", "bchar", cls("Q95074"), 3, "fictional character", "Fictional characters", 1.7, 3.0, words=False, generic=False, extra=[
    F("work", "entity", "P1441", ["Name a character from {v}.", "Think of a character in {v}.", "Characters from {v}."], 1.8, 30, 40),
    F("universe", "entity", "P1080", ["Name a character from the {v} universe.", "Think of a {v} character."], 1.9, 30, 30),
])
