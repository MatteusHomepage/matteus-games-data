import core

HUMAN = "?i wdt:P31 wd:Q5 ."
SPECIES = "?i wdt:P31 wd:Q16521 . ?i wdt:P105 wd:Q7432 . ?i wdt:P1843 ?l . ?i wdt:P171* wd:%s ."
OUT = []


def Q(x):
    return core.resolve(x[1:]) if x.startswith("@") else x


def pat_of(cls):
    if cls == "HUMAN":
        return HUMAN
    if cls.startswith("OCC:"):
        return HUMAN + " ?i wdt:P106 wd:%s ." % Q("@" + cls[4:])
    if cls.startswith("RAW:"):
        return cls[4:]
    return "?i wdt:P31/wdt:P279* wd:%s ." % Q("@" + cls)


def fam(key, tpl, frag, params, base, w=1.0):
    return {"key": key, "tpl": tpl, "frag": frag, "params": params, "base": base, "w": w}


def spec(cat, key, cls, min_sl, noun, plural, fams, minn=None, w=1.0, label="l", pat=None, sv=True):
    OUT.append({"cat": cat, "key": key, "cls": cls, "pat": pat, "min_sl": min_sl, "s": noun, "P": plural, "fams": fams, "minn": minn, "w": w, "label": label, "sv": sv})


def years(a, b, step=1):
    return [(str(y), str(y), round(max(0, 2024 - y) * 0.022, 2)) for y in range(a, b + 1, step)]


def decades(a, b):
    return [("%ds" % y, str(y)) for y in range(a, b + 1, 10)]


CITIES = ["London", "Paris", "New York City", "Berlin", "Rome", "Madrid", "Moscow", "Stockholm", "Los Angeles", "Chicago", "Tokyo", "Vienna", "Boston", "Philadelphia", "Manchester", "Liverpool", "Glasgow", "Dublin", "Copenhagen", "Oslo", "Helsinki", "Amsterdam", "Sydney", "Toronto", "Mumbai", "Istanbul", "Cairo", "Buenos Aires", "Barcelona", "Prague"]

spec("movies", "m_gross", "film", 2, "movie", "Movies", [
    fam("gross", "Name a movie that made over {v} at the box office.", "?i wdt:P2142 ?x . FILTER(?x >= {v})", [("$100 million", "100000000", 0), ("$250 million", "250000000", 0.3), ("$500 million", "500000000", 0.6), ("$1 billion", "1000000000", 1.0)], 1.8),
], minn=60, w=1.5)
spec("movies", "m_set", "film", 2, "movie", "Movies", [
    fam("setin", "Name a movie set in {v}.", "?i wdt:P840 wd:{v} .", [(c, "@" + c, 0) for c in ["New York City", "London", "Paris", "Tokyo", "Los Angeles", "Rome", "Chicago", "Las Vegas", "Berlin", "Italy", "France", "Japan", "Germany", "Texas", "California", "Sweden", "Africa", "Spain"]], 2.2),
    fam("based", "Name a movie based on a {v}.", "?i wdt:P144 ?w . ?w wdt:P31/wdt:P279* wd:{v} .", [("novel", "@novel", 0), ("comic book", "@comic book", 0.2), ("video game", "@video game", 0.2), ("fairy tale", "@fairy tale", 0.4), ("play", "@play", 0.4), ("TV series", "@television series", 0.2), ("short story", "@short story", 0.5), ("manga", "@manga", 0.2), ("musical", "@musical", 0.4)], 1.8),
    fam("genre", "Name a {v}.", "?i wdt:P136 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("heist movie", "heist film", 0.2), ("zombie movie", "zombie film", 0.1), ("disaster movie", "disaster film", 0.3), ("Christmas movie", "Christmas film", 0), ("road movie", "road movie", 0.4), ("sports movie", "sports film", 0.2), ("martial arts movie", "martial arts film", 0.2), ("war movie", "war film", 0.1), ("western", "Western film", 0.2), ("superhero movie", "superhero film", 0), ("horror movie", "horror film", 0), ("romantic comedy", "romantic comedy", 0), ("musical movie", "musical film", 0.1), ("spy movie", "spy film", 0.3), ("coming-of-age movie", "coming-of-age film", 0.4), ("slasher movie", "slasher film", 0.3), ("monster movie", "monster film", 0.3), ("space movie", "science fiction film", 0.4), ("courtroom drama", "legal drama film", 0.5), ("mockumentary", "mockumentary", 0.8)]], 1.5),
    fam("year", "Name a movie that came out in {v}.", "?i wdt:P577 ?d . FILTER(YEAR(?d) = {v})", years(1975, 2024, 1), 2.0),
    fam("female", "Name a movie directed by a woman.", "?i wdt:P57 ?d . ?d wdt:P21 wd:Q6581072 . FILTER NOT EXISTS { ?i wdt:P57 ?d2 . ?d2 wdt:P21 ?g2 . FILTER(?g2 != wd:Q6581072) }", [("", "x", 0)], 2.6),
    fam("sequel", "Name a movie that has a sequel.", "?i wdt:P156 ?z .", [("", "x", 0)], 1.5),
    fam("studio", "Name a movie made by {v}.", "?i wdt:P272 wd:{v} .", [(c, "@" + c, a) for c, a in [("Pixar", 0), ("Walt Disney Pictures", 0), ("Warner Bros.", 0.2), ("Universal Pictures", 0.2), ("Paramount Pictures", 0.2), ("Columbia Pictures", 0.3), ("20th Century Studios", 0.3), ("DreamWorks Animation", 0.1), ("Studio Ghibli", 0.2), ("Marvel Studios", 0), ("A24", 0.6), ("Netflix", 0.1), ("Blumhouse Productions", 0.4), ("Lucasfilm", 0.2), ("Illumination", 0.2), ("Metro-Goldwyn-Mayer", 0.4)]], 1.8),
], w=1.5)
spec("movies", "m_tv", "television series", 3, "TV show", "TV shows", [
    fam("net", "Name a TV show that aired on {v}.", "?i wdt:P449 wd:{v} .", [(c, "@" + c, a) for c, a in [("Netflix", 0), ("HBO", 0.1), ("BBC One", 0.2), ("NBC", 0.1), ("ABC", 0.1), ("CBS", 0.1), ("Fox", 0.1), ("Disney+", 0.1), ("Hulu", 0.2), ("Amazon Prime Video", 0.2), ("Cartoon Network", 0.1), ("Nickelodeon", 0.1), ("Sveriges Television", 0.5), ("Disney Channel", 0.1), ("The CW", 0.3), ("Comedy Central", 0.3), ("AMC", 0.3)]], 1.8),
    fam("year", "Name a TV show that premiered in {v}.", "?i wdt:P580 ?d . FILTER(YEAR(?d) = {v})", years(1985, 2024, 1), 2.2),
    fam("seasons", "Name a TV show that ran for {v} or more seasons.", "?i wdt:P2437 ?x . FILTER(?x >= {v})", [("5", "5", 0), ("8", "8", 0.3), ("10", "10", 0.5)], 1.8),
], minn=100, w=1.2)
spec("movies", "m_anim", "animated television series", 3, "cartoon", "Cartoons", [fam("a", "Name an animated TV show.", "", [("", "x", 0)], 1.3)], minn=80, w=1.0)
spec("movies", "m_hero", "superhero", 2, "superhero", "Superheroes", [fam("a", "Name a superhero.", "", [("", "x", 0)], 1.4)], minn=80)
spec("movies", "m_char", "fictional character", 3, "character", "Characters", [
    fam("vg", "Name a video game character.", "?i wdt:P1441 ?w . ?w wdt:P31/wdt:P279* wd:Q7889 .", [("", "x", 0)], 1.7),
    fam("tv", "Name a character from a TV show.", "?i wdt:P1441 ?w . ?w wdt:P31/wdt:P279* wd:Q5398426 .", [("", "x", 0)], 1.7),
    fam("film", "Name a character from a movie.", "?i wdt:P1441 ?w . ?w wdt:P31/wdt:P279* wd:Q11424 .", [("", "x", 0)], 1.7),
    fam("anim", "Name an animated character.", "?i wdt:P1441 ?w . ?w wdt:P31/wdt:P279* wd:Q202866 .", [("", "x", 0)], 1.6),
], minn=100, w=1.5)

spec("music", "mu_kpop", None, 6, "K-pop act", "K-pop acts", [fam("a", ["Name a K-pop group or artist.", "Name a K-pop artist."], "", [("", "x", 0)], 2.3)], minn=120, w=1.2, pat="{ ?i wdt:P31 wd:Q5 } UNION { ?i wdt:P31/wdt:P279* wd:Q215380 } ?i wdt:P136 wd:Q213665 .", sv=False)

spec("music", "mu_band", "musical group", 4, "band", "Bands", [
    fam("from", "Name a band from {v}.", "?i wdt:P740 wd:{v} .", [(c, "@" + c, a) for c, a in [("London", 0), ("Los Angeles", 0.1), ("New York City", 0.1), ("Manchester", 0.3), ("Liverpool", 0.2), ("Stockholm", 0.4), ("Gothenburg", 0.6), ("Seattle", 0.4), ("Berlin", 0.4), ("Seoul", 0.4), ("Tokyo", 0.5), ("Chicago", 0.4), ("Sydney", 0.5), ("Melbourne", 0.5), ("Toronto", 0.5), ("Dublin", 0.5), ("Glasgow", 0.6), ("Paris", 0.5), ("Detroit", 0.6), ("Nashville", 0.7)]], 1.9),
    fam("dec", "Name a band that formed in the {v}s.", "?i wdt:P571 ?d . FILTER(YEAR(?d) >= {v} && YEAR(?d) < {v}+10)", [(str(y), str(y), 0) for y in range(1960, 2020, 10)], 1.8),
], minn=100, w=1.2)
spec("music", "mu_album", "album", 2, "album", "Albums", [fam("year", "Name an album that came out in {v}.", "?i wdt:P577 ?d . FILTER(YEAR(?d) = {v})", years(1965, 2024, 1), 1.8)], minn=100, w=1.3)

spec("games", "g_vg", "video game", 2, "video game", "Video games", [
    fam("made", "Name a video game developed in {v}.", "?i wdt:P178 ?dv . ?dv wdt:P17 wd:{v} .", [(c, "@" + c, a) for c, a in [("Japan", 0), ("Sweden", 0.4), ("Poland", 0.4), ("France", 0.3), ("Canada", 0.3), ("United Kingdom", 0.1), ("South Korea", 0.4), ("China", 0.4), ("Germany", 0.3), ("Finland", 0.6), ("Denmark", 0.6), ("Australia", 0.5)]], 2.0),
    fam("year", "Name a video game that came out in {v}.", "?i wdt:P577 ?d . FILTER(YEAR(?d) = {v})", years(1985, 2024, 1), 2.0),
    fam("mode", "Name {v}.", "?i wdt:P404 wd:{v} .", [("a multiplayer game", "@multiplayer video game", 0), ("a single-player game", "@single-player video game", 0)], 1.5),
    fam("genre", "Name {v}.", "?i wdt:P136 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("a role-playing game", "role-playing video game", 0), ("a platformer", "platform game", 0.1), ("a first-person shooter", "first-person shooter", 0), ("a real-time strategy game", "real-time strategy video game", 0.3), ("a survival game", "survival video game", 0.1), ("a battle royale game", "battle royale game", 0.2), ("a sandbox game", "sandbox video game", 0.2), ("a fighting game", "fighting game", 0.1), ("a racing game", "racing video game", 0), ("a puzzle game", "puzzle video game", 0.1), ("a horror game", "survival horror", 0.2), ("a rhythm game", "rhythm game", 0.3), ("a roguelike", "roguelike", 0.5), ("a visual novel", "visual novel", 0.6), ("a stealth game", "stealth video game", 0.3), ("a tower defense game", "tower defense", 0.4)]], 1.6),
], minn=100, w=1.5)
spec("games", "g_board", "board game", 2, "board game", "Board games", [fam("a", "Name a board game.", "", [("", "x", 0)], 1.6)], minn=100)
spec("games", "g_card", "card game", 2, "card game", "Card games", [fam("a", "Name a card game.", "", [("", "x", 0)], 1.8)], minn=100)

spec("sport", "s_foot", "OCC:association football player", 4, "footballer", "Footballers", [
    fam("league", "Name a footballer who has played in {v}.", "?i wdt:P54 ?t . ?t wdt:P118 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("the Premier League", "Premier League", 0), ("La Liga", "La Liga", 0.1), ("Ligue 1", "Ligue 1", 0.3), ("Allsvenskan", "Allsvenskan", 0.5), ("Major League Soccer", "Major League Soccer", 0.3), ("the Eredivisie", "Eredivisie", 0.5), ("the Scottish Premiership", "Scottish Premiership", 0.5), ("the Süper Lig", "Süper Lig", 0.5)]], 1.9),
    fam("pos", "Name a {v}.", "?i wdt:P413 wd:{v} . ?i wdt:P54 ?tm . ?tm wdt:P118 ?lg0 .", [("goalkeeper", "@association football goalkeeper", 0.2), ("defender", "@defender", 0), ("midfielder", "@midfielder", 0), ("striker", "@forward", 0)], 1.8),
], minn=150, w=1.5)
spec("sport", "s_pro", "HUMAN", 6, "player", "Players", [
    fam("lg", "Name a player who has played in {v}.", "?i wdt:P54 ?t . ?t wdt:P118 wd:{v} .", [("the NBA", "@National Basketball Association", 0), ("the NHL", "@NHL", 0.2), ("MLB", "@Major League Baseball", 0.3), ("the NFL", "@National Football League", 0.1)], 1.8),
    fam("olym", "Name an athlete who competed at the {v}.", "?i wdt:P1344 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("2012 Olympics", "2012 Summer Olympics", 0), ("2016 Olympics", "2016 Summer Olympics", 0), ("2008 Olympics", "2008 Summer Olympics", 0.1), ("2000 Olympics", "2000 Summer Olympics", 0.2), ("1996 Olympics", "1996 Summer Olympics", 0.3), ("2018 Winter Olympics", "2018 Winter Olympics", 0.3), ("2014 Winter Olympics", "2014 Winter Olympics", 0.3), ("2010 Winter Olympics", "2010 Winter Olympics", 0.4), ("2020 Olympics", "2020 Summer Olympics", 0)]], 2.2),
], minn=150, w=1.3)
spec("sport", "s_job", "HUMAN", 6, "athlete", "Athletes", [
    fam("occ", "Name {v}.", "?i wdt:P106 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("a Formula 1 driver", "Formula One driver", 0.2), ("a boxer", "boxer", 0.1), ("a golfer", "golfer", 0.2), ("a swimmer", "swimmer", 0.3), ("a professional wrestler", "professional wrestler", 0.2), ("a chess player", "chess player", 0.4), ("an alpine skier", "alpine skier", 0.4), ("a cyclist", "cyclist", 0.4), ("a sprinter", "sprinter", 0.4), ("a figure skater", "figure skater", 0.5), ("a gymnast", "gymnast", 0.4), ("a cricketer", "cricketer", 0.3), ("a rugby player", "rugby union player", 0.5), ("a mixed martial artist", "mixed martial arts fighter", 0.3), ("a snowboarder", "snowboarder", 0.5), ("a cross-country skier", "cross-country skier", 0.6), ("a handball player", "handball player", 0.5), ("a darts player", "darts player", 0.8)]], 1.8),
], minn=100, w=1.2)
spec("sport", "s_stad", "stadium", 2, "stadium", "Stadiums", [fam("cap", "Name a stadium that holds more than {v} people.", "?i wdt:P1083 ?x . FILTER(?x >= {v})", [("30,000", "30000", 0), ("50,000", "50000", 0.3), ("70,000", "70000", 0.6), ("90,000", "90000", 1.0)], 2.4)], minn=60)
spec("sport", "s_sport", "sport", 2, "sport", "Sports", [fam("a", "Name a sport.", "", [("", "x", 0)], 1.4)], minn=100, w=0.8)

spec("geography", "ge_country", "RAW:?i wdt:P31 wd:Q3624078 .", 3, "country", "Countries", [
    fam("lang", "Name a country where {v} is an official language.", "?i wdt:P37 wd:{v} .", [(d, "@" + d, a) for d, a in [("English", 0.1), ("French", 0.3), ("Spanish", 0.2), ("Arabic", 0.4), ("Portuguese", 0.4), ("German", 0.5), ("Russian", 0.5), ("Dutch", 0.7)]], 2.2),
    fam("euro", "Name a country that uses the euro.", "?i wdt:P38 wd:Q4916 .", [("", "x", 0)], 1.8),
    fam("monarchy", "Name a country that has a monarchy.", "?i wdt:P122 ?g . ?g wdt:P279* wd:Q7269 .", [("", "x", 0)], 2.4),
    fam("island", "Name a country that is an island.", "?i wdt:P31 wd:Q112099 .", [("", "x", 0)], 2.4),
], minn=15, w=0.8)
spec("geography", "ge_city", "city", 3, "city", "Cities", [
    fam("pop", "Name a city with more than {v} people.", "?i wdt:P1082 ?x . FILTER(?x >= {v})", [("500,000", "500000", 0), ("1 million", "1000000", 0.3), ("3 million", "3000000", 0.6)], 2.2),
    fam("person", "Name a city named after a person.", "?i wdt:P138 ?p . ?p wdt:P31 wd:Q5 .", [("", "x", 0)], 2.4),
    fam("cap", "Name a capital city.", "?i wdt:P31/wdt:P279* wd:Q5119 .", [("", "x", 0)], 1.8),
], minn=100, w=1.0)
spec("geography", "ge_mount", "mountain", 2, "mountain", "Mountains", [fam("h", "Name a mountain taller than {v} metres.", "?i p:P2044/psn:P2044/wikibase_:quantityAmount ?x . FILTER(?x >= {v})", [("3,000", "3000", 0), ("4,000", "4000", 0.3), ("5,000", "5000", 0.5), ("6,000", "6000", 0.8), ("8,000", "8000", 1.2)], 2.4)], minn=15, w=1.0)
spec("geography", "ge_river", "river", 2, "river", "Rivers", [fam("l", "Name a river longer than {v} kilometres.", "?i p:P2043/psn:P2043/wikibase_:quantityAmount ?x . FILTER(?x >= {v})", [("500", "500000", 0), ("1,000", "1000000", 0.3), ("2,000", "2000000", 0.7)], 2.6)], minn=60, w=1.0)
spec("geography", "ge_nat", "volcano", 2, "volcano", "Volcanoes", [fam("a", "Name a volcano.", "", [("", "x", 0)], 2.4)], minn=100)
spec("geography", "ge_wf", "waterfall", 2, "waterfall", "Waterfalls", [fam("a", "Name a waterfall.", "", [("", "x", 0)], 2.8)], minn=100)
spec("geography", "ge_in", "RAW:?i wdt:P31/wdt:P279* wd:Q811979 .", 3, "landmark", "Landmarks", [
    fam("in", "Name a famous building in {v}.", "?i wdt:P131* wd:{v} .", [(c, "@" + c, a) for c, a in [("London", 0), ("Paris", 0), ("New York City", 0), ("Rome", 0.2), ("Berlin", 0.3), ("Stockholm", 0.5), ("Moscow", 0.3), ("Istanbul", 0.4), ("Barcelona", 0.4), ("Tokyo", 0.4), ("Vienna", 0.5), ("Chicago", 0.4), ("Madrid", 0.5), ("Amsterdam", 0.5)]], 2.4),
], minn=100, w=1.0)
spec("geography", "ge_street", "street", 2, "street", "Streets", [fam("in", "Name a street in {v}.", "?i wdt:P131* wd:{v} .", [(c, "@" + c, a) for c, a in [("Stockholm", 0.2), ("London", 0.2), ("Paris", 0.2), ("New York City", 0.2), ("Berlin", 0.4), ("Gothenburg", 0.6), ("Rome", 0.5), ("Vienna", 0.5), ("Copenhagen", 0.5)]], 3.0)], minn=100, w=0.8)

spec("food", "f_dish", "dish", 2, "dish", "Dishes", [
    fam("has", "Name a dish that contains {v}.", "{ ?i wdt:P527 wd:{v} } UNION { ?i wdt:P186 wd:{v} }", [(d, "@" + t, a) for d, t, a in [("cheese", "cheese", 0), ("rice", "rice", 0), ("potato", "potato", 0), ("chicken", "chicken meat", 0), ("egg", "egg as food", 0.1), ("tomato", "tomato", 0.1), ("pork", "pork", 0.2), ("beef", "beef", 0.2), ("fish", "fish as food", 0.3), ("chocolate", "chocolate", 0.2)]], 1.7),
], minn=60, w=1.2)
spec("food", "f_type", "RAW:?i wdt:P31/wdt:P279* wd:Q746549 .", 2, "food", "Foods", [
    fam("c", "Name {v}.", "?i wdt:P279* wd:{v} .", [(d, "@" + t, a) for d, t, a in [("a type of pasta", "pasta", 0), ("a type of cheese", "cheese", 0), ("a type of bread", "bread", 0.1), ("a type of cake", "cake", 0), ("a type of soup", "soup", 0.1), ("a type of sandwich", "sandwich", 0.1), ("a type of sausage", "sausage", 0.2), ("a type of pastry", "pastry", 0.2), ("a type of cookie", "cookie", 0.1), ("a cocktail", "cocktail", 0.3), ("a type of candy", "candy", 0.1), ("a type of pie", "pie", 0.2), ("a type of dumpling", "dumpling", 0.4), ("a type of noodle", "noodle", 0.3), ("a type of sushi", "sushi", 0.2), ("a type of curry", "curry", 0.4), ("a type of salad", "salad", 0.2), ("a type of pizza", "pizza", 0.1)]], 1.6),
], minn=40, w=1.3)
spec("food", "f_brand", "brand", 4, "brand", "Brands", [
    fam("own", "Name a brand owned by {v}.", "?i wdt:P127 wd:{v} .", [(c, "@" + c, a) for c, a in [("Nestlé", 0.2), ("Unilever", 0.3), ("Procter & Gamble", 0.4), ("Mars, Incorporated", 0.3), ("PepsiCo", 0.2), ("The Coca-Cola Company", 0.1), ("Mondelez International", 0.4), ("The Walt Disney Company", 0.1), ("Microsoft", 0.2), ("Google", 0.2), ("Meta Platforms", 0.3), ("Sony", 0.3), ("Amazon", 0.2), ("Volkswagen Group", 0.3), ("LVMH", 0.5), ("Toyota", 0.4), ("Samsung", 0.4), ("Nike", 0.4)]], 2.2),
], minn=20, w=1.2)
spec("food", "f_fast", "restaurant chain", 3, "restaurant chain", "Restaurant chains", [fam("a", "Name a restaurant chain.", "", [("", "x", 0)], 1.4)], minn=100)
spec("food", "f_soft", "soft drink", 2, "soft drink", "Soft drinks", [fam("a", "Name a soft drink.", "", [("", "x", 0)], 1.3)], minn=60)

spec("nature", "n_tax", "RAW:?i wdt:P31 wd:Q16521 . ?i wdt:P105 wd:Q7432 . ?i wdt:P1843 ?l .", 2, "animal", "Animals", [
    fam("grp", "Name {v}.", "?i wdt:P171* wd:{v} .", [(d, "@" + t, a) for d, t, a in [("a type of owl", "Strigiformes", 0.2), ("a type of parrot", "Psittaciformes", 0.2), ("a type of shark", "Selachimorpha", 0.2), ("a type of snake", "Serpentes", 0.2), ("a type of spider", "spider", 0.4), ("a type of butterfly", "Papilionoidea", 0.3), ("a type of frog", "Anura", 0.3), ("a type of bat", "Chiroptera", 0.4), ("a type of duck", "Anatidae", 0.3), ("a type of eagle or hawk", "Accipitridae", 0.4), ("a type of whale or dolphin", "Cetacea", 0.2), ("a type of monkey or ape", "simian", 0.2), ("a type of deer or antelope", "Cervidae", 0.5), ("a type of beetle", "Coleoptera", 0.5), ("a type of turtle", "Testudines", 0.4), ("a type of lizard", "Lacertilia", 0.4), ("a type of fish", "Actinopterygii", 0.2), ("a type of rodent", "rodent", 0.3), ("a type of seabird", "Procellariiformes", 0.7), ("a mollusk", "Mollusca", 0.4), ("a type of crab or shrimp", "Decapoda", 0.4), ("a type of bee or wasp", "Hymenoptera", 0.4), ("a type of cat", "Felidae", 0.1), ("a type of bear", "Ursidae", 0.1)]], 1.6),
    fam("iucn", "Name an endangered animal.", "?i wdt:P141 ?st . FILTER(?st IN (wd:Q11394, wd:Q219127, wd:Q278113)) ?i wdt:P171* wd:Q729 .", [("", "x", 0)], 2.2),
], minn=60, w=2.0, label="pat")
spec("nature", "n_breed", "dog breed", 2, "dog breed", "Dog breeds", [fam("a", "Name a dog breed.", "", [("", "x", 0)], 1.3)], minn=100)
spec("nature", "n_cat", "cat breed", 2, "cat breed", "Cat breeds", [fam("a", "Name a cat breed.", "", [("", "x", 0)], 1.6)], minn=40)
spec("nature", "n_fung", "RAW:?i wdt:P31 wd:Q16521 . ?i wdt:P105 wd:Q7432 . ?i wdt:P171* wd:Q764 . ?i wdt:P1843 ?l .", 2, "mushroom", "Mushrooms", [fam("a", "Name a mushroom.", "", [("", "x", 0)], 2.2)], minn=60, label="pat")

spec("science", "sc_tech", "programming language", 2, "programming language", "Programming languages", [fam("a", "Name a programming language.", "", [("", "x", 0)], 2.2)], minn=100, w=0.8)
spec("science", "sc_app", "mobile app", 2, "app", "Apps", [fam("a", "Name a mobile app.", "", [("", "x", 0)], 1.4)], minn=100)
spec("science", "sc_car", "automobile model", 3, "car model", "Car models", [
    fam("make", "Name a car model made by {v}.", "?i wdt:P176 wd:{v} .", [(c, "@" + c, a) for c, a in [("Toyota", 0), ("Ford Motor Company", 0), ("Volkswagen", 0.1), ("BMW", 0.1), ("Mercedes-Benz", 0.1), ("Volvo Cars", 0.2), ("Honda", 0.2), ("Nissan", 0.3), ("Chevrolet", 0.2), ("Audi", 0.2), ("Peugeot", 0.4), ("Renault", 0.4), ("Fiat", 0.4), ("Skoda", 0.5), ("Tesla", 0.3), ("Saab Automobile", 0.6), ("Porsche", 0.4), ("Ferrari", 0.3), ("Volkswagen Group", 0.2)]], 1.8),
], minn=40, w=1.2)
spec("science", "sc_org", "RAW:?i wdt:P31/wdt:P279* wd:Q4830453 .", 5, "company", "Companies", [
    fam("hq", "Name a company headquartered in {v}.", "?i wdt:P159 wd:{v} .", [(c, "@" + c, a) for c, a in [("Stockholm", 0.2), ("London", 0.3), ("New York City", 0.3), ("San Francisco", 0.3), ("Tokyo", 0.5), ("Paris", 0.4), ("Berlin", 0.6), ("Seattle", 0.5), ("Gothenburg", 0.5), ("Munich", 0.6), ("Copenhagen", 0.6), ("Helsinki", 0.6), ("Oslo", 0.6), ("Seoul", 0.5)]], 2.2),
    fam("dec", "Name a company founded in the {v}s.", "?i wdt:P571 ?d . FILTER(YEAR(?d) >= {v} && YEAR(?d) < {v}+10)", [(str(y), str(y), 0) for y in range(1900, 2020, 10)], 2.4),
], minn=100, w=1.0)
spec("science", "sc_air", "airline", 3, "airline", "Airlines", [fam("a", "Name an airline.", "", [("", "x", 0)], 1.8)], minn=100)
spec("science", "sc_dis", "disease", 6, "disease", "Diseases", [fam("a", "Name a disease.", "?i wdt:P31/wdt:P279* wd:Q12136 . FILTER NOT EXISTS { ?i wdt:P31 wd:Q169872 } FILTER(!REGEX(?l, \"pandemic|epidemic|yawn\", \"i\"))", [("", "x", 0)], 2.2)], minn=100)

spec("history", "h_person", "HUMAN", 10, "person", "People", [
    fam("born", "Name a famous person born in {v}.", "?i wdt:P19 wd:{v} .", [(c, "@" + c, 0.0) for c in CITIES], 2.4),
    fam("uni", "Name a person who studied at {v}.", "?i wdt:P69 wd:{v} .", [(c, "@" + c, a) for c, a in [("Harvard University", 0.1), ("University of Oxford", 0.2), ("University of Cambridge", 0.2), ("Yale University", 0.3), ("Stanford University", 0.3), ("Massachusetts Institute of Technology", 0.3), ("Columbia University", 0.3), ("Princeton University", 0.3), ("Sorbonne", 0.5), ("Uppsala University", 0.5), ("Lund University", 0.6), ("KTH Royal Institute of Technology", 0.8)]], 2.6),
    fam("nobel", "Name a Nobel Prize winner.", "?i wdt:P166 ?a . ?a wdt:P279* wd:Q7191 .", [("", "x", 0)], 2.4),
], minn=100, w=1.3)
spec("history", "h_job", "HUMAN", 8, "person", "People", [
    fam("occ", "Name {v}.", "?i wdt:P106 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("a YouTuber", "YouTuber", 0), ("a comedian", "comedian", 0.1), ("a chef", "chef", 0.2), ("an astronaut", "astronaut", 0.3), ("an architect", "architect", 0.5), ("a fashion designer", "fashion designer", 0.4), ("a painter", "painter", 0.2), ("a philosopher", "philosopher", 0.3), ("an inventor", "inventor", 0.3), ("an explorer", "explorer", 0.4), ("a magician", "magician", 0.5), ("a photographer", "photographer", 0.5), ("a film producer", "film producer", 0.4), ("a TV presenter", "television presenter", 0.2), ("a screenwriter", "screenwriter", 0.5), ("a novelist", "novelist", 0.2), ("a physicist", "physicist", 0.5), ("a US senator", "United States senator", 0.5), ("a Prime Minister", "prime minister", 0.4)]], 2.0),
    fam("dec", "Name an actor born in the {v}s.", "?i wdt:P106 wd:Q33999 . ?i wdt:P569 ?b . FILTER(YEAR(?b) >= {v} && YEAR(?b) < {v}+10)", [(str(y), str(y), a) for y, a in [(1930, 0.6), (1940, 0.5), (1950, 0.3), (1960, 0.1), (1970, 0), (1980, 0), (1990, 0.1), (2000, 0.5)]], 1.8),
], minn=100, w=1.2)
spec("history", "h_myth", "deity", 3, "god or goddess", "Gods and goddesses", [fam("a", "Name a god or goddess.", "", [("", "x", 0)], 2.0)], minn=100)
spec("general", "x_tv", "RAW:?i wdt:P31/wdt:P279* wd:Q2001305 .", 4, "TV channel", "TV channels", [fam("a", "Name a TV channel.", "", [("", "x", 0)], 1.8)], minn=100, w=0.8)
spec("general", "x_mag", "magazine", 4, "magazine", "Magazines", [fam("a", "Name a magazine.", "", [("", "x", 0)], 1.8)], minn=100, w=0.8)
spec("general", "x_clothes", "clothing brand", 4, "clothing brand", "Clothing brands", [fam("a", "Name a clothing brand.", "", [("", "x", 0)], 1.4)], minn=100)
spec("general", "x_bank", "bank", 6, "bank", "Banks", [fam("a", "Name a bank.", "", [("", "x", 0)], 2.4)], minn=100, w=0.6)



def tune(sk, fk, base=None, adds=None, total=None):
    for s in OUT:
        if s["key"] != sk:
            continue
        for f in s["fams"]:
            if f["key"] != fk:
                continue
            if base is not None:
                f["base"] = base
            if adds:
                f["params"] = [(p[0], p[1], adds.get(p[0], p[2] if len(p) > 2 else 0)) for p in f["params"]]
            if total:
                f["params"] = [(p[0], p[1], round(total[p[0]] - f["base"], 2) if p[0] in total else (p[2] if len(p) > 2 else 0)) for p in f["params"]]


tune("n_tax", "grp", total={
    "a type of fish": 1.3, "a type of shark": 1.4, "a type of whale or dolphin": 1.4, "a type of monkey or ape": 1.4, "a type of cat": 1.3, "a type of bear": 1.3,
    "a type of snake": 1.5, "a type of parrot": 1.5, "a type of owl": 1.6, "a type of spider": 1.6, "a type of butterfly": 1.6, "a type of frog": 1.6,
    "a type of duck": 1.7, "a type of rodent": 1.6, "a type of turtle": 1.8, "a type of deer or antelope": 2.2, "a type of crab or shrimp": 2.2,
    "a type of eagle or hawk": 2.4, "a type of lizard": 2.4, "a type of bee or wasp": 2.4, "a mollusk": 2.7, "a type of bat": 2.7, "a type of beetle": 2.7, "a type of seabird": 3.0,
})
tune("n_fung", "a", base=2.8)
tune("mu_album", "year", base=2.6)
tune("g_vg", "year", base=2.1)
tune("m_set", "year", base=2.1)
tune("s_pro", "olym", base=2.7)
tune("ge_city", "person", base=2.7)
tune("sc_org", "dec", base=3.2)
tune("h_job", "occ", base=2.2)
tune("h_job", "dec", adds={"1930s": 1.0, "1940s": 0.8, "1950s": 0.4, "1960s": 0.2, "1970s": 0, "1980s": 0, "1990s": 0.1, "2000s": 0.5})
tune("h_person", "born", adds={c: (0 if c in ("London", "Paris", "New York City", "Los Angeles", "Stockholm") else 0.3 if c in ("Rome", "Berlin", "Chicago", "Tokyo", "Moscow", "Madrid", "Boston", "Dublin", "Sydney", "Toronto", "Barcelona", "Manchester", "Liverpool", "Vienna", "Amsterdam") else 0.6) for c in CITIES})
tune("m_set", "setin", adds={"Berlin": 0.4, "Germany": 0.3, "Spain": 0.3, "Texas": 0.3, "Sweden": 0.2, "Africa": 0.2, "Las Vegas": 0.1, "Chicago": 0.1})
tune("m_set", "studio", adds={"A24": 0.9, "Blumhouse Productions": 0.6, "Metro-Goldwyn-Mayer": 0.5})
tune("m_set", "based", adds={"short story": 0.8, "manga": 0.3})
tune("s_foot", "league", adds={"the Süper Lig": 0.8})

def addfam(sk, f):
    for s in OUT:
        if s["key"] == sk:
            s["fams"].append(f)


addfam("ge_country", fam("a", ["Name a country.", "Name any country."], "", [("", "x", 0)], 1.0))
spec("science", "sc_lang", "RAW:?i wdt:P31 wd:Q34770 .", 6, "language", "Languages", [fam("a", ["Name a language.", "Name a language people speak."], "", [("", "x", 0)], 1.6)], minn=100, w=0.8, sv=False)


addfam("m_set", fam("theme", "Name a movie about {v}.", "?i wdt:P921 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("time travel", "time travel", 0.4), ("vampires", "vampire", 0.3), ("dragons", "dragon", 0.5), ("robots", "robot", 0.3), ("pirates", "pirate", 0.3), ("dinosaurs", "dinosaur", 0.3), ("ghosts", "ghost", 0.3), ("aliens", "extraterrestrial life", 0.3), ("magic", "magic", 0.5), ("a prison", "prison", 0.6), ("a road trip", "road trip", 0.7), ("friendship", "friendship", 0.5), ("revenge", "revenge", 0.6), ("a murder", "murder", 0.6), ("a school", "school", 0.5)]], 1.5))
addfam("m_tv", fam("genre", "Name {v}.", "?i wdt:P136 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("a sitcom", "situation comedy", 0), ("a crime show", "Q9335577", 0.2), ("a reality show", "reality television", 0.1), ("an anime series", "anime", 0.1), ("a soap opera", "soap opera", 0.4), ("a game show", "game show", 0.3), ("a medical drama", "medical drama", 0.3), ("a sci-fi show", "science fiction television series", 0.2), ("a fantasy series", "fantasy television series", 0.3), ("a teen drama", "teen drama", 0.3), ("a talk show", "talk show", 0.4), ("a sketch comedy show", "sketch comedy", 0.6), ("a cooking show", "cooking show", 0.5), ("a children's show", "children's television series", 0.1), ("a detective series", "detective fiction", 0.4)]], 1.7))


def T(sk, fk, base, total=None, adds=None):
    tune(sk, fk, base=base, total=total, adds=adds)


T("m_gross", "gross", 1.4)
T("m_set", "setin", 1.6, adds={"New York City": 0, "London": 0, "Paris": 0, "Tokyo": 0.1, "Los Angeles": 0, "Rome": 0.1, "Chicago": 0.2, "Las Vegas": 0.2, "Berlin": 0.5, "Italy": 0.2, "France": 0.2, "Japan": 0.3, "Germany": 0.4, "Texas": 0.4, "California": 0.3, "Sweden": 0.4, "Africa": 0.4, "Spain": 0.4})
T("m_set", "based", 1.5, total={"novel": 1.5, "comic book": 1.6, "video game": 1.9, "fairy tale": 1.9, "play": 2.3, "TV series": 1.8, "short story": 2.4, "manga": 2.3, "musical": 2.0})
T("m_set", "genre", 1.4, total={"heist movie": 1.7, "zombie movie": 1.5, "disaster movie": 1.8, "Christmas movie": 1.4, "road movie": 2.4, "sports movie": 1.7, "martial arts movie": 1.9, "war movie": 1.5, "western": 1.6, "superhero movie": 1.3, "horror movie": 1.3, "romantic comedy": 1.4, "musical movie": 1.6, "spy movie": 1.8, "coming-of-age movie": 2.2, "slasher movie": 1.9, "monster movie": 1.9, "space movie": 1.6, "courtroom drama": 2.4, "mockumentary": 3.0})
T("m_set", "female", 2.3)
T("m_set", "studio", 1.3, total={"Pixar": 1.3, "Walt Disney Pictures": 1.3, "Warner Bros.": 1.8, "Universal Pictures": 1.9, "Paramount Pictures": 1.9, "Columbia Pictures": 2.3, "20th Century Studios": 2.2, "DreamWorks Animation": 1.6, "Studio Ghibli": 1.8, "Marvel Studios": 1.3, "A24": 3.0, "Netflix": 1.6, "Blumhouse Productions": 2.8, "Lucasfilm": 1.8, "Illumination": 1.7, "Metro-Goldwyn-Mayer": 2.4})
T("m_tv", "net", 1.4, total={"Netflix": 1.4, "HBO": 1.6, "BBC One": 2.0, "NBC": 2.0, "ABC": 2.0, "CBS": 2.1, "Fox": 2.0, "Disney+": 1.6, "Hulu": 2.2, "Amazon Prime Video": 1.9, "Cartoon Network": 1.7, "Nickelodeon": 1.7, "Sveriges Television": 1.7, "Disney Channel": 1.8, "The CW": 2.4, "Comedy Central": 2.2, "AMC": 2.5})
T("m_tv", "seasons", 1.7, total={"5": 1.7, "8": 2.1, "10": 2.4})
T("m_char", "vg", 1.5)
T("m_char", "tv", 1.8)
T("m_char", "film", 1.6)
T("m_char", "anim", 1.4)
T("mu_kpop", "a", 2.6)
T("mu_band", "from", 2.1, total={"London": 2.1, "Los Angeles": 2.2, "New York City": 2.2, "Manchester": 2.4, "Liverpool": 2.2, "Stockholm": 2.5, "Gothenburg": 2.7, "Seattle": 2.6, "Berlin": 2.7, "Seoul": 2.7, "Tokyo": 2.8, "Chicago": 2.7, "Sydney": 2.8, "Melbourne": 2.8, "Toronto": 2.8, "Dublin": 2.7, "Glasgow": 2.8, "Paris": 2.8, "Detroit": 2.9, "Nashville": 3.0})
T("mu_band", "dec", 2.4, total={"1960": 2.4, "1970": 2.4, "1980": 2.5, "1990": 2.6, "2000": 2.9, "2010": 3.6})
T("g_vg", "mode", 1.5, total={"a multiplayer game": 1.3, "a single-player game": 1.6})
T("g_vg", "genre", 1.6, total={"a role-playing game": 1.6, "a platformer": 1.7, "a first-person shooter": 1.5, "a real-time strategy game": 2.1, "a survival game": 1.7, "a battle royale game": 1.8, "a sandbox game": 1.8, "a fighting game": 1.7, "a racing game": 1.6, "a puzzle game": 1.7, "a horror game": 1.8, "a rhythm game": 2.0, "a roguelike": 2.4, "a visual novel": 2.8, "a stealth game": 2.0, "a tower defense game": 2.3})
T("g_board", "a", 1.5)
T("g_card", "a", 1.6)
T("s_foot", "league", 1.6, total={"the Premier League": 1.6, "La Liga": 1.9, "Ligue 1": 2.5, "Allsvenskan": 2.0, "Major League Soccer": 2.4, "the Eredivisie": 2.6, "the Scottish Premiership": 2.7, "the Süper Lig": 3.0})
T("s_foot", "pos", 1.5, total={"goalkeeper": 1.8, "defender": 1.7, "midfielder": 1.6, "striker": 1.4})
T("s_pro", "lg", 1.8, total={"the NBA": 1.8, "the NHL": 2.0, "MLB": 2.2, "the NFL": 1.9})
T("s_job", "occ", 2.0, total={"a Formula 1 driver": 1.8, "a boxer": 1.7, "a golfer": 2.0, "a swimmer": 2.2, "a professional wrestler": 1.9, "a chess player": 2.2, "an alpine skier": 2.4, "a cyclist": 2.3, "a sprinter": 2.2, "a figure skater": 2.8, "a gymnast": 2.4, "a cricketer": 3.7, "a rugby player": 2.9, "a mixed martial artist": 2.4, "a snowboarder": 2.8, "a cross-country skier": 2.4, "a handball player": 2.4, "a darts player": 3.4})
T("s_stad", "cap", 2.0, total={"30,000": 2.0, "50,000": 2.3, "70,000": 2.6, "90,000": 3.0})
T("ge_country", "lang", 2.0, total={"English": 2.1, "French": 2.3, "Spanish": 2.2, "Arabic": 2.4, "Portuguese": 2.4, "German": 2.5, "Russian": 2.5, "Dutch": 2.7})
T("ge_country", "euro", 1.6)
T("ge_country", "monarchy", 2.3)
T("ge_country", "island", 2.2)
T("ge_city", "pop", 1.6, total={"500,000": 1.6, "1 million": 1.9, "3 million": 2.4})
T("ge_city", "cap", 1.3)
T("ge_river", "l", 2.2, total={"500": 2.2, "1,000": 2.5, "2,000": 2.9})
T("ge_nat", "a", 2.8)
T("ge_wf", "a", 3.0)
T("ge_in", "in", 2.0, adds={"London": 0, "Paris": 0, "New York City": 0, "Rome": 0.2, "Berlin": 0.4, "Stockholm": 0.4, "Moscow": 0.3, "Istanbul": 0.4, "Barcelona": 0.4, "Tokyo": 0.5, "Vienna": 0.5, "Chicago": 0.4, "Madrid": 0.5, "Amsterdam": 0.5})
T("f_dish", "has", 1.4, adds={"cheese": 0, "rice": 0.1, "potato": 0.1, "chicken": 0.1, "egg": 0.3, "tomato": 0.3, "pork": 0.5, "beef": 0.5, "fish": 0.6, "chocolate": 0.4})
T("f_type", "c", 1.2, total={"a type of pasta": 1.2, "a type of cheese": 1.2, "a type of bread": 1.5, "a type of cake": 1.3, "a type of soup": 1.5, "a type of sandwich": 1.5, "a type of sausage": 1.8, "a type of pastry": 1.8, "a type of cookie": 1.4, "a cocktail": 1.9, "a type of candy": 1.4, "a type of pie": 1.7, "a type of dumpling": 2.0, "a type of noodle": 1.9, "a type of sushi": 1.8, "a type of curry": 2.0, "a type of salad": 1.6, "a type of pizza": 1.5})
T("f_brand", "own", 2.2, total={"Nestlé": 2.4, "Unilever": 2.8, "Procter & Gamble": 3.0, "Mars, Incorporated": 2.2, "PepsiCo": 2.3, "The Coca-Cola Company": 1.6, "Mondelez International": 2.9, "The Walt Disney Company": 1.9, "Microsoft": 2.1, "Google": 2.2, "Meta Platforms": 2.4, "Sony": 2.3, "Amazon": 2.2, "Volkswagen Group": 2.5, "LVMH": 3.1, "Toyota": 2.4, "Samsung": 2.4, "Nike": 2.6})
T("n_tax", "iucn", 2.0)
T("sc_car", "make", 1.5, total={"Toyota": 1.5, "Ford Motor Company": 1.5, "Volkswagen": 1.6, "BMW": 1.6, "Mercedes-Benz": 1.6, "Volvo Cars": 1.7, "Honda": 1.7, "Nissan": 1.8, "Chevrolet": 1.7, "Audi": 1.7, "Peugeot": 1.9, "Renault": 1.9, "Fiat": 1.9, "Skoda": 2.0, "Tesla": 1.8, "Saab Automobile": 2.1, "Porsche": 1.9, "Ferrari": 1.8, "Volkswagen Group": 1.7})
T("sc_air", "a", 1.6)
T("sc_dis", "a", 1.7)
T("h_person", "nobel", 2.2)
T("h_job", "occ", 2.0, total={"a YouTuber": 1.5, "a comedian": 1.7, "a chef": 1.8, "an astronaut": 2.2, "an architect": 2.8, "a fashion designer": 2.5, "a painter": 1.9, "a philosopher": 2.0, "an inventor": 2.0, "an explorer": 2.3, "a magician": 2.6, "a photographer": 2.9, "a film producer": 2.8, "a TV presenter": 2.4, "a screenwriter": 3.0, "a novelist": 1.8, "a physicist": 2.0, "a US senator": 2.6, "a Prime Minister": 2.3})
T("h_myth", "a", 1.5)
T("x_tv", "a", 2.0)
T("x_mag", "a", 2.0)
T("x_bank", "a", 2.2)


NOSV_KEYS = {"from", "born", "setin", "hq", "made", "in", "lang", "euro", "monarchy", "island", "pop", "h", "l", "cap", "seasons", "iucn", "grp", "person", "make"}
NOSV_SPECS = {"ge_country", "ge_mount", "ge_river", "ge_nat", "ge_wf", "n_breed", "n_cat", "n_fung", "n_tax", "sc_tech", "sc_dis", "h_myth", "g_card", "g_board", "sc_app"}

P_SV = "?i wdt:P27 wd:Q34 ."


def swcls(q):
    return "?i wdt:P31/wdt:P279* wd:%s ." % q


def swocc(label):
    return "?i wdt:P31 wd:Q5 . ?i wdt:P106 wd:%s . %s" % (Q("@" + label), P_SV)


def swfam(key, tpl, base, frag="", params=None):
    return fam(key, tpl, frag, params or [("", "x", 0)], base)


def swspec(cat, key, pat, noun, plural, fams, min_sl=3, minn=100, w=1.0):
    spec(cat, key, None, min_sl, noun, plural, fams, minn=minn, w=w, pat=pat, sv=False)


SW_CLUBS = ["AIK", "Djurgårdens IF", "IFK Göteborg", "Malmö FF", "Hammarby Fotboll", "IFK Norrköping", "Helsingborgs IF", "Arsenal F.C.", "Manchester United F.C.", "Juventus F.C.", "AC Milan", "FC Barcelona", "Ajax", "Chelsea F.C.", "Liverpool F.C.", "Celtic F.C.", "Paris Saint-Germain F.C."]
SW_TOK = {"Juventus F.C.": "Q1422", "Ajax": "Q81888", "Paris Saint-Germain F.C.": "Q483020"}
SW_CLUB_ADD = {"AIK": 0, "Djurgårdens IF": 0.1, "IFK Göteborg": 0.1, "Malmö FF": 0, "Hammarby Fotboll": 0.2, "IFK Norrköping": 0.3, "Helsingborgs IF": 0.3, "Arsenal F.C.": 0.2, "Manchester United F.C.": 0.1, "Juventus F.C.": 0.4, "AC Milan": 0.3, "FC Barcelona": 0.3, "Ajax": 0.4, "Chelsea F.C.": 0.1, "Liverpool F.C.": 0.1, "Celtic F.C.": 0.5, "Paris Saint-Germain F.C.": 0.4}
SW_SPORT = [("tennis player", "a tennis player", 0.2), ("golfer", "a golfer", 0.3), ("swimmer", "a swimmer", 0.5), ("cross-country skier", "a cross-country skier", 0.3), ("alpine skier", "an alpine skier", 0.5), ("handball player", "a handball player", 0.4), ("biathlete", "a biathlete", 0.8), ("speed skater", "a speed skater", 0.9), ("cyclist", "a cyclist", 0.6), ("track and field athlete", "an athletics athlete", 0.6), ("boxer", "a boxer", 0.6), ("basketball player", "a basketball player", 0.6), ("bandy player", "a bandy player", 1.0), ("floorball player", "a floorball player", 0.9), ("table tennis player", "a table tennis player", 0.9), ("curler", "a curler", 1.0), ("ski jumper", "a ski jumper", 1.0), ("sprinter", "a sprinter", 0.6)]

swspec("geography", "sw_city", "?i wdt:P31 wd:Q12813115 .", "city", "Cities", [
    swfam("a", ["Name a city in Sweden.", "Name a Swedish city or town."], 1.9),
    swfam("letter", "Name a Swedish city or town that starts with the letter {v}.", 2.0, "FILTER(STRSTARTS(UCASE(?l), \"{v}\"))", [(c, c, a) for c, a in [("S", 0.3), ("K", 0.2), ("H", 0.3), ("L", 0.3), ("V", 0.3), ("B", 0.4), ("A", 0.4), ("M", 0.4), ("N", 0.4), ("T", 0.4), ("G", 0.5), ("J", 0.5), ("O", 0.5), ("E", 0.6), ("F", 0.6), ("U", 0.6)]]),
])
swspec("geography", "sw_lake", swcls("Q23397") + " ?i wdt:P17 wd:Q34 .", "lake", "Lakes", [swfam("a", ["Name a lake in Sweden.", "Name a Swedish lake."], 2.6)])
swspec("geography", "sw_isl", swcls("Q23442") + " ?i wdt:P17 wd:Q34 .", "island", "Islands", [swfam("a", ["Name an island in Sweden.", "Name a Swedish island."], 2.7)])
swspec("geography", "sw_build", swcls("Q811979") + " ?i wdt:P17 wd:Q34 .", "building", "Buildings", [swfam("a", ["Name a famous building or landmark in Sweden.", "Name a landmark in Sweden."], 2.5)], w=1.0)
swspec("geography", "sw_church", swcls("Q16970") + " ?i wdt:P17 wd:Q34 .", "church", "Churches", [swfam("a", ["Name a church in Sweden.", "Name a Swedish church."], 3.0)], w=0.8)
swspec("geography", "sw_museum", swcls("Q33506") + " ?i wdt:P17 wd:Q34 .", "museum", "Museums", [swfam("a", ["Name a museum in Sweden.", "Name a Swedish museum."], 2.7)], w=0.8)
swspec("sport", "sw_foot", swocc("Q937857"), "footballer", "Footballers", [
    swfam("a", ["Name a Swedish footballer.", "Name a footballer from Sweden."], 2.1, "", [("", "x", 0)]),
    swfam("club", "Name a Swedish footballer who has played for {v}.", 2.1, "?i wdt:P54 wd:{v} .", [(c, SW_TOK.get(c, "@" + c), SW_CLUB_ADD[c]) for c in SW_CLUBS]),
], min_sl=4)
swspec("sport", "sw_hockey", swocc("Q11774891"), "ice hockey player", "Ice hockey players", [
    swfam("a", ["Name a Swedish ice hockey player.", "Name a hockey player from Sweden."], 2.3),
    swfam("nhl", "Name a Swedish hockey player who has played in the NHL.", 2.5, "?i wdt:P54 ?t . ?t wdt:P118 wd:Q1215892 ."),
])
swspec("sport", "sw_ath", "?i wdt:P31 wd:Q5 . " + P_SV + " ?i wdt:P641 ?sp .", "athlete", "Athletes", [
    swfam("a", ["Name a Swedish athlete.", "Name an athlete from Sweden."], 2.1),
    swfam("olym", "Name a Swedish athlete who has competed at the {v}.", 2.6, "?i wdt:P1344 wd:{v} .", [(d, "@" + t, a) for d, t, a in [("2016 Olympics", "2016 Summer Olympics", 0), ("2012 Olympics", "2012 Summer Olympics", 0.1), ("2008 Olympics", "2008 Summer Olympics", 0.2), ("2018 Winter Olympics", "2018 Winter Olympics", 0.2), ("2014 Winter Olympics", "2014 Winter Olympics", 0.2), ("2022 Winter Olympics", "2022 Winter Olympics", 0.1)]]),
], min_sl=4)
swspec("sport", "sw_sport", "?i wdt:P31 wd:Q5 . " + P_SV, "athlete", "Athletes", [
    swfam("occ", ["Name Swedish {v}.", "Name {v} from Sweden."], 1.9, "?i wdt:P106 wd:{v} .", [(d, "@" + t, a) for t, d, a in SW_SPORT]),
], min_sl=3, w=1.2)
swspec("sport", "sw_club", swcls("Q476028") + " ?i wdt:P17 wd:Q34 .", "football club", "Football clubs", [swfam("a", ["Name a Swedish football club.", "Name a football club in Sweden."], 2.4)], min_sl=2, w=1.0)
swspec("movies", "sw_actor", swocc("Q33999"), "actor", "Actors", [
    swfam("a", ["Name a Swedish actor.", "Name an actor from Sweden."], 2.0),
    swfam("f", ["Name a Swedish actress."], 2.1, "?i wdt:P21 wd:Q6581072 ."),
    swfam("dec", "Name a Swedish actor born in the {v}s.", 2.4, "?i wdt:P569 ?b . FILTER(YEAR(?b) >= {v} && YEAR(?b) < {v}+10)", [(str(y), str(y), a) for y, a in [(1960, 0.2), (1970, 0), (1980, 0), (1990, 0.1), (1950, 0.4), (1940, 0.6)]]),
])
swspec("movies", "sw_dir", swocc("Q2526255") + " { SELECT ?i (COUNT(DISTINCT ?w) AS ?nw) WHERE { ?w wdt:P57 ?i } GROUP BY ?i HAVING (COUNT(DISTINCT ?w) >= 3) }", "film director", "Film directors", [swfam("a", ["Name a Swedish film director.", "Name a film director from Sweden."], 2.7)], w=0.9)
swspec("movies", "sw_film", swcls("Q11424") + " ?i wdt:P495 wd:Q34 .", "movie", "Movies", [
    swfam("a", ["Name a Swedish movie.", "Name a film from Sweden."], 2.3),
    swfam("dec", "Name a Swedish movie from the {v}s.", 2.7, "?i wdt:P577 ?d . FILTER(YEAR(?d) >= {v} && YEAR(?d) < {v}+10)", [(str(y), str(y), a) for y, a in [(2010, 0), (2000, 0.1), (1990, 0.2), (1980, 0.3), (1970, 0.4), (1960, 0.5), (1950, 0.6), (1940, 0.7), (1930, 0.8)]]),
], min_sl=2)
swspec("movies", "sw_tv", swcls("Q5398426") + " ?i wdt:P495 wd:Q34 .", "TV show", "TV shows", [swfam("a", ["Name a Swedish TV show.", "Name a TV series from Sweden."], 2.6)], min_sl=2, minn=100, w=0.8)
swspec("music", "sw_band", swcls("Q215380") + " ?i wdt:P495 wd:Q34 .", "band", "Bands", [
    swfam("a", ["Name a Swedish band.", "Name a band from Sweden."], 2.1),
    swfam("g", "Name a Swedish {v}.", 2.5, "?i wdt:P136/wdt:P279* wd:{v} .", [(d, t if t.startswith("Q") else "@" + t, a) for d, t, a in [("pop group", "pop music", 0), ("rock band", "rock music", 0), ("metal band", "Q38848", 0.1), ("hip hop group", "Q11401", 0.5), ("electronic music group", "electronic music", 0.5), ("indie band", "indie rock", 0.5)]]),
    swfam("dec", "Name a Swedish band that formed in the {v}s.", 2.4, "?i wdt:P571 ?d . FILTER(YEAR(?d) >= {v} && YEAR(?d) < {v}+10)", [(str(y), str(y), a) for y, a in [(1990, 0), (2000, 0), (1980, 0.1), (2010, 0.2), (1970, 0.3)]]),
], min_sl=3)
swspec("music", "sw_sing", swocc("Q177220"), "singer", "Singers", [
    swfam("a", ["Name a Swedish singer.", "Name a singer from Sweden."], 2.1),
    swfam("f", ["Name a Swedish female singer."], 2.3, "?i wdt:P21 wd:Q6581072 ."),
    swfam("m", ["Name a Swedish male singer."], 2.3, "?i wdt:P21 wd:Q6581052 ."),
])
swspec("music", "sw_mus", swocc("Q639669"), "musician", "Musicians", [swfam("a", ["Name a Swedish musician."], 2.5)], w=0.9)
swspec("history", "sw_writer", swocc("Q36180"), "writer", "Writers", [swfam("a", ["Name a Swedish author.", "Name a Swedish writer."], 2.6)])
swspec("history", "sw_pol", swocc("Q82955"), "politician", "Politicians", [swfam("a", ["Name a Swedish politician."], 2.7)], w=0.8)
swspec("history", "sw_paint", swocc("Q1028181"), "painter", "Painters", [swfam("a", ["Name a Swedish painter.", "Name a Swedish artist."], 3.0)], w=0.7)
swspec("history", "sw_all", "?i wdt:P31 wd:Q5 . " + P_SV, "person", "People", [
    swfam("born", "Name a famous person born in {v}.", 2.6, "?i wdt:P19/wdt:P131* wd:{v} .", [(c, "@" + c, a) for c, a in [("Stockholm", 0), ("Gothenburg", 0.1), ("Malmö", 0.2), ("Uppsala", 0.4), ("Västerås", 0.6), ("Örebro", 0.6), ("Linköping", 0.6), ("Helsingborg", 0.6), ("Norrköping", 0.6), ("Lund", 0.5)]]),
], min_sl=8, w=0.8)
swspec("science", "sw_comp", swcls("Q4830453") + " ?i wdt:P17 wd:Q34 .", "company", "Companies", [
    swfam("a", ["Name a Swedish company.", "Name a company from Sweden."], 2.3),
    swfam("dec", "Name a Swedish company founded in the {v}s.", 3.0, "?i wdt:P571 ?d . FILTER(YEAR(?d) >= {v} && YEAR(?d) < {v}+10)", [(str(y), str(y), a) for y, a in [(1990, 0), (2000, 0), (1980, 0.1), (1970, 0.1), (1960, 0.2), (1950, 0.2), (1900, 0.3), (1910, 0.3), (1920, 0.3), (1930, 0.3), (1940, 0.3), (2010, 0.1)]]),
], min_sl=3)
swspec("food", "sw_brand", swcls("Q431289") + " ?i wdt:P17 wd:Q34 .", "brand", "Brands", [swfam("a", ["Name a Swedish brand."], 2.3)], min_sl=2, minn=100, w=0.8)
swspec("games", "sw_game", swcls("Q7889") + " ?i wdt:P495 wd:Q34 .", "video game", "Video games", [swfam("a", ["Name a video game made in Sweden.", "Name a Swedish video game."], 2.6)], min_sl=2, w=0.8)
swspec("history", "sw_book", swcls("Q7725634") + " ?i wdt:P495 wd:Q34 .", "book", "Books", [swfam("a", ["Name a Swedish book.", "Name a book by a Swedish author."], 3.0)], min_sl=2, w=0.7)

T("sw_city", "a", 1.4)
T("sw_lake", "a", 2.2)
T("sw_isl", "a", 2.6)
T("sw_build", "a", 2.4)
T("sw_museum", "a", 2.6)
T("sw_foot", "a", 1.6)
T("sw_hockey", "a", 2.5)
T("sw_hockey", "nhl", 2.8)
T("sw_ath", "a", 1.9)
T("sw_club", "a", 1.9)
T("sw_actor", "a", 1.8)
T("sw_actor", "f", 1.9)
T("sw_sing", "a", 1.9)

MISSING = []


def all_labels():
    L = set()
    for s in OUT:
        c = s["cls"]
        if c and not c.startswith("RAW:") and c != "HUMAN":
            L.add(c[4:] if c.startswith("OCC:") else c)
        for f in s["fams"]:
            for p in f["params"]:
                if p[1].startswith("@"):
                    L.add(p[1][1:])
    for m in __import__("re").findall(r"wd:(Q[0-9]+)", "") :
        pass
    return L


def firstonly(frag):
    m = __import__("re").search(r"wdt:(P571|P577|P580) \?d \. FILTER\(YEAR\(\?d\) (>=|=) \{v\}", frag)
    if not m or "NOT EXISTS" in frag:
        return frag
    return frag + " FILTER NOT EXISTS { ?i wdt:%s ?d0 . FILTER(YEAR(?d0) < {v}) }" % m.group(1)


def build():
    left = core.resolve_many(all_labels())
    for x in left:
        MISSING.append((x, "label not found"))
    out = []
    for s in OUT:
        try:
            pat = s["pat"] or pat_of(s["cls"])
        except Exception as e:
            MISSING.append((s["key"], str(e)))
            continue
        facets = []
        for f in s["fams"]:
            facets.append({
                "key": f["key"], "kind": "custom", "prop": None, "tpl": f["tpl"], "base": f["base"], "min_n": 0, "top": len(f["params"]),
                "ok": None, "rx": None, "frag": firstonly(f["frag"]), "params": f["params"], "w_": "", "fw": f["w"],
                "sv": s["sv"] and s["key"] not in NOSV_SPECS and f["key"] not in NOSV_KEYS,
            })
        out.append({"cat": s["cat"], "key": s["key"], "pat": pat, "min_sl": s["min_sl"], "facets": facets, "label": s["label"], "noun": s["s"], "title": False, "w": s["w"], "s": s["s"], "P": s["P"], "minn": s["minn"], "krill": True, "sv": True})
    return out
