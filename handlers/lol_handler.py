import aiohttp
import random

# Data Dragon
# Public Riot CDN — no API key required
VERSION_URL  = "https://ddragon.leagueoflegends.com/api/versions.json"
CHAMP_URL    = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"

# In-memory cache so we only fetch once per bot session
_champion_cache: list[str] | None = None          # full champion name list
_role_cache: dict[str, list[str]] | None = None   # role → [champion names]

# Role map
# Curated primary lane assignments for every champion.
# Data Dragon tags are class-based (Fighter/Mage/etc), not lane-based,
# so this is hand-tuned to reflect actual Summoner's Rift lane meta.
# Update a champion's entry if the meta shifts their primary lane.
ROLE_MAP: dict[str, list[str]] = {
    # TOP
    "Aatrox":      ["top"],
    "Ambessa":     ["top"],
    "Camille":     ["top"],
    "Cho'Gath":    ["top"],
    "Darius":      ["top"],
    "Dr. Mundo":   ["top"],
    "Fiora":       ["top"],
    "Gangplank":   ["top"],
    "Garen":       ["top"],
    "Gnar":        ["top"],
    "Gragas":      ["top",    "jungle"],
    "Gwen":        ["top"],
    "Illaoi":      ["top"],
    "Irelia":      ["top",    "mid"],
    "Jax":         ["top",    "jungle"],
    "Jayce":       ["top",    "mid"],
    "K'Sante":     ["top"],
    "Kennen":      ["top"],
    "Kled":        ["top"],
    "Malphite":    ["top",    "support"],
    "Mordekaiser": ["top"],
    "Nasus":       ["top"],
    "Olaf":        ["top",    "jungle"],
    "Ornn":        ["top"],
    "Pantheon":    ["top",    "support"],
    "Poppy":       ["top",    "support"],
    "Quinn":       ["top"],
    "Renekton":    ["top"],
    "Riven":       ["top"],
    "Rumble":      ["top"],
    "Sett":        ["top"],
    "Shen":        ["top",    "support"],
    "Singed":      ["top"],
    "Sion":        ["top"],
    "Teemo":       ["top",    "support"],
    "Trundle":     ["top",    "jungle"],
    "Tryndamere":  ["top"],
    "Urgot":       ["top"],
    "Vayne":       ["top",    "bot"],
    "Vladimir":    ["top",    "mid"],
    "Volibear":    ["top",    "jungle"],
    "Wukong":      ["top",    "jungle"],
    "Yorick":      ["top"],

    # JUNGLE
    "Amumu":           ["jungle", "support"],
    "Bel'Veth":        ["jungle"],
    "Briar":           ["jungle"],
    "Diana":           ["jungle", "mid"],
    "Ekko":            ["jungle", "mid"],
    "Elise":           ["jungle"],
    "Evelynn":         ["jungle"],
    "Fiddlesticks":    ["jungle", "support"],
    "Graves":          ["jungle"],
    "Hecarim":         ["jungle"],
    "Ivern":           ["jungle", "support"],
    "Jarvan IV":       ["jungle", "top"],
    "Kayn":            ["jungle"],
    "Kha'Zix":         ["jungle"],
    "Kindred":         ["jungle"],
    "Lee Sin":         ["jungle"],
    "Lillia":          ["jungle", "mid"],
    "Maokai":          ["jungle", "support"],
    "Master Yi":       ["jungle"],
    "Nidalee":         ["jungle"],
    "Nocturne":        ["jungle"],
    "Nunu & Willump":  ["jungle", "support"],
    "Rammus":          ["jungle"],
    "Rek'Sai":         ["jungle"],
    "Rengar":          ["jungle"],
    "Sejuani":         ["jungle", "support"],
    "Shaco":           ["jungle", "support"],
    "Shyvana":         ["jungle"],
    "Skarner":         ["jungle"],
    "Taliyah":         ["jungle", "mid"],
    "Udyr":            ["jungle", "top"],
    "Vi":              ["jungle"],
    "Viego":           ["jungle"],
    "Warwick":         ["jungle", "top"],
    "Xin Zhao":        ["jungle"],
    "Zac":             ["jungle", "support"],

    # MID
    "Ahri":         ["mid"],
    "Akali":        ["mid"],
    "Akshan":       ["mid"],
    "Anivia":       ["mid"],
    "Annie":        ["mid",     "support"],
    "Aurelion Sol": ["mid"],
    "Azir":         ["mid"],
    "Cassiopeia":   ["mid"],
    "Corki":        ["mid",     "bot"],
    "Fizz":         ["mid"],
    "Galio":        ["mid",     "support"],
    "Heimerdinger": ["mid",     "support"],
    "Hwei":         ["mid",     "support"],
    "Kassadin":     ["mid"],
    "Katarina":     ["mid"],
    "LeBlanc":      ["mid"],
    "Lissandra":    ["mid"],
    "Lux":          ["mid",     "support"],
    "Malzahar":     ["mid"],
    "Morgana":      ["mid",     "support"],
    "Naafiri":      ["mid"],
    "Orianna":      ["mid"],
    "Qiyana":       ["mid"],
    "Ryze":         ["mid"],
    "Swain":        ["mid",     "support"],
    "Sylas":        ["mid",     "jungle"],
    "Syndra":       ["mid"],
    "Talon":        ["mid",     "jungle"],
    "Twisted Fate": ["mid"],
    "Veigar":       ["mid",     "support"],
    "Vel'Koz":      ["mid",     "support"],
    "Vex":          ["mid"],
    "Viktor":       ["mid"],
    "Xerath":       ["mid",     "support"],
    "Yasuo":        ["mid",     "bot"],
    "Yone":         ["mid",     "top"],
    "Zed":          ["mid"],
    "Ziggs":        ["mid",     "bot"],
    "Zoe":          ["mid"],

    # BOT (ADC)
    "Aphelios":    ["bot"],
    "Ashe":        ["bot",     "support"],
    "Caitlyn":     ["bot"],
    "Draven":      ["bot"],
    "Ezreal":      ["bot"],
    "Jhin":        ["bot"],
    "Jinx":        ["bot"],
    "Kai'Sa":      ["bot"],
    "Kalista":     ["bot"],
    "Kog'Maw":     ["bot"],
    "Lucian":      ["bot",     "mid"],
    "Miss Fortune": ["bot",    "support"],
    "Nilah":       ["bot"],
    "Samira":      ["bot"],
    "Senna":       ["bot",     "support"],
    "Sivir":       ["bot"],
    "Smolder":     ["bot"],
    "Tristana":    ["bot",     "mid"],
    "Twitch":      ["bot",     "jungle"],
    "Varus":       ["bot",     "support"],
    "Xayah":       ["bot"],
    "Zeri":        ["bot"],

    # SUPPORT
    "Alistar":      ["support"],
    "Bard":         ["support"],
    "Blitzcrank":   ["support"],
    "Brand":        ["support",  "mid"],
    "Braum":        ["support"],
    "Janna":        ["support"],
    "Karma":        ["support",  "mid"],
    "Leona":        ["support"],
    "Lulu":         ["support"],
    "Milio":        ["support"],
    "Nami":         ["support"],
    "Nautilus":     ["support"],
    "Neeko":        ["support",  "mid"],
    "Pyke":         ["support"],
    "Rakan":        ["support"],
    "Rell":         ["support"],
    "Renata Glasc": ["support"],
    "Seraphine":    ["support",  "mid",  "bot"],
    "Sona":         ["support"],
    "Soraka":       ["support"],
    "Tahm Kench":   ["support",  "top"],
    "Taric":        ["support"],
    "Thresh":       ["support"],
    "Yuumi":        ["support"],
    "Zilean":       ["support",  "mid"],
    "Zyra":         ["support",  "mid"],
}

ROLES = ["top", "jungle", "mid", "bot", "support"]
ROLE_LABELS = {
    "top":     "🗡️  Top",
    "jungle":  "🌿  Jungle",
    "mid":     "⚡  Mid",
    "bot":     "🏹  Bot",
    "support": "🛡️  Support",
}


# Data fetching
async def _fetch_latest_version() -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(VERSION_URL) as resp:
            versions = await resp.json(content_type=None)
            return versions[0]


async def _fetch_champions() -> tuple[list[str], dict[str, list[str]]]:
    # Fetch champion data from Data Dragon.
    # Returns (all_champion_names, role_dict)
    # role_dict maps each role to a list of champion names playable there.
    version = await _fetch_latest_version()
    url = CHAMP_URL.format(version=version)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json(content_type=None)

    all_champs = [champ["name"] for champ in data["data"].values()]

    # Build role lists from our curated ROLE_MAP.
    # Any champion not in ROLE_MAP falls back to a role derived from their
    # Data Dragon tags so new releases are never silently missing.
    role_dict: dict[str, list[str]] = {r: [] for r in ROLES}

    tag_fallback = {
        "Fighter": "top", "Tank": "top", "Assassin": "mid",
        "Mage": "mid", "Marksman": "bot", "Support": "support",
    }

    for champ_data in data["data"].values():
        name = champ_data["name"]
        if name in ROLE_MAP:
            for role in ROLE_MAP[name]:      # iterate the list of roles
                if role in role_dict:
                    role_dict[role].append(name)
        else:
            # Fallback: use first Data Dragon tag
            tags = champ_data.get("tags", [])
            fallback_role = tag_fallback.get(tags[0], "mid") if tags else "mid"
            role_dict[fallback_role].append(name)

    return all_champs, role_dict


async def ensure_cache() -> tuple[list[str], dict[str, list[str]]]:
    # Return cached champion data, fetching from Data Dragon if needed.
    global _champion_cache, _role_cache
    if _champion_cache is None or _role_cache is None:
        _champion_cache, _role_cache = await _fetch_champions()
    return _champion_cache, _role_cache


# Roll logic
async def roll_arena(count: int) -> list[str]:
    # Pick 'count' random champions from the full pool.
    all_champs, _ = await ensure_cache()
    return random.sample(all_champs, count)


async def roll_champs() -> dict[str, str]:
    # Pick 1 champion per role (5 total, all different).
    # Returns {role: champion_name}
    _, role_dict = await ensure_cache()
    result = {}
    used: set[str] = set()

    for role in ROLES:
        pool = [c for c in role_dict[role] if c not in used]
        if not pool:
            # Extremely unlikely but safe fallback — grab from full pool
            all_champs, _ = await ensure_cache()
            pool = [c for c in all_champs if c not in used]
        pick = random.choice(pool)
        result[role] = pick
        used.add(pick)

    return result


def roll_roles(players: list[str]) -> dict[str, str]:

    # Randomly assign 5 players to the 5 roles.
    # Returns {role: player_display_name}
    shuffled = players.copy()
    random.shuffle(shuffled)
    return dict(zip(ROLES, shuffled))


async def roll_mix(players: list[str]) -> dict[str, tuple[str, str]]:
    # Assign roles to players AND pick a champion per role.
    # Returns {role: (player_display_name, champion_name)}
    role_assignments = roll_roles(players)
    champ_assignments = await roll_champs()
    return {
        role: (role_assignments[role], champ_assignments[role])
        for role in ROLES
    }
