from handlers.ai_handler import ask_ai, clear_history
from handlers.stock_handler import fetch_and_render, resolve_ticker, PERIOD_MAP, DEFAULT_PERIOD
from handlers.lol_handler import roll_arena, roll_champs, roll_roles, roll_mix, ROLE_LABELS
from handlers.language_handler import TextAnalyzer
from handlers.pip_handler import (
    build_package_list_embed,
    install_package,
    uninstall_package,
    is_numpy_package,
    random_numpy_reply,
)
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import discord
import json
import random
import os

# env variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot instance setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents, help_command=None)
HELP_COMMANDS = {
    "help": {
        "usage": "$help [command]",
        "description": "Shows all bot commands, or details for specified command.",
        "details": "Use when you forget a command or want to see the flags for one specific command.",
        "flags": {
            "$help": "Shows the short overview for every command.",
            "$help <command>": "Shows detailed help for one command. (don't use $ before the command)",
        },
        "examples": ["$help", "$help stock", "$help pip"],
        "aliases": [],
        "admin": False,
    },
    "ping": {
        "usage": "$ping",
        "description": "Checks if the bot is online",
        "details": "A check command. If the bot replies, it is online and processing commands.",
        "examples": ["$ping"],
        "aliases": [],
        "admin": False,
    },
    "chat": {
        "usage": "$chat <message> / $ჩატ <message>",
        "description": "AI chatbot feature. talks to the AI model using your message and channel context.",
        "details": (
            "Get a reply from and AI agent. It understands context and is a friend"
            "Georgian, English, English-Georgian transliteration is also supported."
        ),
        "examples": ["$chat რა ხდება?", "$ჩატ explain this code", "$chat ra xdeba ak?"],
        "aliases": ["ჩატ"],
        "admin": False,
    },
    "reset": {
        "usage": "$reset",
        "description": "Clears this channel's AI conversation/context history.",
        "details": (
            "Admin-only command. It clears the stored AI chat history for the current channel only."
        ),
        "examples": ["$reset"],
        "aliases": [],
        "admin": True,
    },
    "stock": {
        "usage": "$stock <ticker|stock-name> [1d|1m|1y|5y]",
        "description": "fetch a stock or crypto chart and render it with basic info.",
        "details": (
            "Fetches market data, renders a chart, and sends an embed. Common names like "
            "`apple` or `bitcoin` work, and raw tickers objects like `NVDA` or `SNDK` work too."
        ),
        "flags": {
            "1d": "One-day chart. (default period)",
            "1m": "One-month chart.",
            "1y": "One-year chart.",
            "5y": "Five-year chart.",
        },
        "examples": ["$stock apple", "$stock bitcoin 1m", "$stock NVDA 1y", "$stock SNDK 1y"],
        "aliases": [],
        "admin": False,
    },
    "pip": {
        "usage": "$pip install|uninstall|list|freeze|unfreeze",
        "description": "Python Package manager commands, plus admin-only - freeze/unfreeze.",
        "details": (
            "A fake server package manager. Installs are simulated, package infos are fetched from PyPI, "
            "and the installed package list is saved locally."
        ),
        "flags": {
            "install <package>": "Fetches PyPI info,Simulates install process, and adds it to the list.",
            "uninstall <package>": "Simulates uninstall process and removes it from the list.",
            "list": "Lists the installed packages.",
            "freeze @user": "Admin-only. Times out the mentioned user for 1 hour.",
            "unfreeze @user": "Admin-only. Removes the timeout for the mentioned user.",
        },
        "examples": ["$pip install requests", "$pip list", "$pip freeze @user"],
        "aliases": [],
        "admin": False,
    },
    "arenaroll": {
        "usage": "$arenaroll v2|v3",
        "description": "Rolls random League of Legends champions for Arena mode.",
        "details": "Randomly picks champions for Arena with specified game mode.",
        "flags": {
            "v2": "Rolls 2 champions for 2v2 Arena.",
            "v3": "Rolls 3 champions for 3v3 Arena.",
        },
        "examples": ["$arenaroll v2", "$arenaroll v3"],
        "aliases": [],
        "admin": False,
    },
    "flexroll": {
        "usage": "$flexroll -champs|-roles|-mix [@p1 @p2 @p3 @p4 @p5]",
        "description": "Rolls random champions for each role, assigns random roles (1 each), or both.",
        "details": (
            "Flex queue helper. For role-based rolls it uses exactly 5 manual mentions, or exactly "
            "5 non-bot users from your current voice channel."
        ),
        "flags": {
            "-champs": "Rolls ONE different champion for EACH role.",
            "-roles": "Assigns 5 players to top, jungle, mid, bot, and support randomly.",
            "-mix": "Assigns roles and champs for each assigned role.",
            "@mentions": "Optional manual player list for `-roles` and `-mix`; must be exactly 5 users.",
        },
        "examples": [
            "$flexroll -champs",
            "$flexroll -roles",
            "$flexroll -mix @p1 @p2 @p3 @p4 @p5",
        ],
        "aliases": [],
        "admin": False,
    },
}
analyzer = TextAnalyzer()

# conversation variables:
PASSIVE_CONTEXT_LIMIT = 10
AI_LIMIT_MAX_REQUESTS = 7
AI_LIMIT_WINDOW = timedelta(hours=2)
AI_LIMIT_FILE = Path(__file__).resolve().parent / "data" / "ai_usage_limits.json"
megonkalo_trigger_list: list[str] = ['megonka', 'megonkalo', 'gonka', 'gonkalo','megonkaloze','megonkaze','megonkalos',
                          'მეგონკა', 'მეგონკალო', 'გონკა', 'გონკალო', 'მეგონკალოზე', 'მეგონკაზე', 'მეგონკალოს']
megonkalo_random_reply_list: list[str] = ["94", "94ით მოფრინავს", "ჩვენი ძმა მეგონკა", "გიო wowი არ ვიყომაროთ?",
                               "ეგ ვისი ძმაკაცია?", "დაურეკეთ მეგონკას ჩვენ ძმას", "94ჯერ ვითამაშე wow დღეს", "ბანჯოლას ძმაკაცი ვინახსენა?"]
ping_random_reply_list: list[str] = ["ჰოუ", "რაა", "რაია",
                                    "რაო", "ხო რაარი", "რახდება",
                                     "ჰოოოო", "რაგინდაააა რააა"]
stock_not_found_list: list[str] = ['ეგეთი მონაცემები ვერსად ვერ ვნახე', 'ეგ რაარი? არსად არაა',
                      'ვინა, სადა?', 'ვიის?', 'არ მაქ მაგის მონაცემები']
missing_permission_reply_list: list[str] = ['მაგას შენ ვერიზამ', 'მაგაზე ელიტას მიმართე',
                          'კიდე რაგინდა?', 'ძაან ხოარ გაიჯვი?',
                          'ადმინი არ ხარ', 'არ გაქ უფლება', 'ადმინ... უთხარი რა ამას რამე'
                          'მენეჯერს მიმართე', 'менеджери садаа?']

# Custom Help Class with a description for each command
class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="Bot Commands",
            description="Use `$help <command>` for more details.",
            color=0x5865F2,
        )

        for command_name, metadata in HELP_COMMANDS.items():
            command = self.context.bot.get_command(command_name)
            if command is None and command_name != "help":
                continue

            label = f"${command_name}"
            if metadata["admin"]:
                label += " (admin)"

            aliases = metadata["aliases"]
            alias_text = f"\nAliases: {', '.join(f'${alias}' for alias in aliases)}" if aliases else ""
            embed.add_field(
                name=label,
                value=f"{metadata['description']}\nUsage: `{metadata['usage']}`{alias_text}",
                inline=False,
            )

        await self.context.reply(embed=embed, mention_author=False)

    async def send_command_help(self, command):
        metadata = HELP_COMMANDS.get(command.name)
        if metadata is None:
            await self.context.reply("მაგ command-ზე help არ მაქვს.", mention_author=False)
            return

        title = f"Help: ${command.name}"
        if metadata["admin"]:
            title += " (admin)"

        embed = discord.Embed(
            title=title,
            description=metadata.get("details", metadata["description"]),
            color=0x57F287,
        )
        embed.add_field(name="Usage", value=f"`{metadata['usage']}`", inline=False)

        flags = metadata.get("flags")
        if flags:
            flag_lines = [f"`{name}` - {description}" for name, description in flags.items()]
            embed.add_field(
                name="Flags / Options",
                value="\n".join(flag_lines),
                inline=False,
            )

        examples = metadata.get("examples")
        if examples:
            embed.add_field(
                name="Examples",
                value="\n".join(f"`{example}`" for example in examples),
                inline=False,
            )

        aliases = metadata["aliases"]
        if aliases:
            embed.add_field(
                name="Aliases",
                value=", ".join(f"`${alias}`" for alias in aliases),
                inline=False,
            )

        await self.context.reply(embed=embed, mention_author=False)

    async def send_cog_help(self, cog):
        await self.send_bot_help({})

    async def send_group_help(self, group):
        await self.send_command_help(group)

    def command_not_found(self, string):
        return f"`{string}` ეგ command ვერ ვნახე ან `$`-ის გარეშე დაწერე"

    async def send_error_message(self, error):
        await self.context.reply(error, mention_author=False)


bot.help_command = CustomHelpCommand()

# analyze text content and return transliteration if conditions met
def analyze(arg) -> str | None:

    if analyzer.is_other_language(arg):
        return analyzer.to_georgian(arg)
    elif analyzer.is_georgian(arg) or analyzer.is_english(arg):
        return arg

    return None

async def get_passive_context(channel, triggering_message_id: int) -> str:
    lines = []
    async for msg in channel.history(limit=PASSIVE_CONTEXT_LIMIT + 5, before=discord.Object(id=triggering_message_id)):
        if msg.author.bot:
            continue
        lines.append(f"{msg.author.display_name}: {analyze(msg.content)}")
        if len(lines) >= PASSIVE_CONTEXT_LIMIT:
            break
    lines.reverse() # chronological order
    return "\n".join(lines)

def _get_voice_players(ctx) -> list[str] | str:
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        return "not_in_voice"

    members = [m for m in ctx.author.voice.channel.members if not m.bot]

    if len(members) == 5:
        return [m.display_name for m in members]

    names = ", ".join(m.display_name for m in members)
    return f"wrong_count:{len(members)}:{names}"


def _load_ai_usage_limits() -> dict[str, dict[str, object]]:
    if not AI_LIMIT_FILE.exists():
        return {}

    try:
        with AI_LIMIT_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    return {
        user_id: entry
        for user_id, entry in data.items()
        if isinstance(user_id, str) and isinstance(entry, dict)
    }


def _save_ai_usage_limits(limits: dict[str, dict[str, object]]) -> None:
    AI_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AI_LIMIT_FILE.open("w", encoding="utf-8") as file:
        json.dump(limits, file, ensure_ascii=False, indent=2, sort_keys=True)


def _format_cooldown(remaining: timedelta) -> str:
    total_seconds = max(int(remaining.total_seconds()), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = (remainder + 59) // 60

    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{max(minutes, 1)}m"


def _consume_ai_request(user_id: int) -> tuple[bool, str | None]:
    limits = _load_ai_usage_limits()
    now = datetime.now(timezone.utc)
    key = str(user_id)
    entry = limits.get(key)

    if entry is not None:
        try:
            window_start = datetime.fromisoformat(str(entry["window_start"]))
            count_value = entry.get("count", 0)
            count = int(count_value) if isinstance(count_value, (int, str)) else 0
        except (KeyError, TypeError, ValueError):
            window_start = now
            count = 0
    else:
        window_start = now
        count = 0

    if now - window_start >= AI_LIMIT_WINDOW:
        window_start = now
        count = 0

    if count >= AI_LIMIT_MAX_REQUESTS:
        cooldown = _format_cooldown(AI_LIMIT_WINDOW - (now - window_start))
        return False, cooldown

    limits[key] = {
        "window_start": window_start.isoformat(),
        "count": count + 1,
    }
    _save_ai_usage_limits(limits)
    return True, None


def _get_welcome_channel(guild: discord.Guild) -> discord.TextChannel | None:
    bot_member = guild.me
    if bot_member is None:
        return None

    system_channel = guild.system_channel
    if system_channel and system_channel.permissions_for(bot_member).send_messages:
        return system_channel

    for channel in guild.text_channels:
        if channel.permissions_for(bot_member).send_messages:
            return channel

    return None


# check bot state by pinging (online/offline)
@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    print(f'Bot Ready!')


@bot.event
async def on_guild_join(guild):
    channel = _get_welcome_channel(guild)
    if channel is None:
        return

    await channel.send(
        "@everyone სალამი სასტავ, მე ვარ ჩაჭიპიტი.\n"
        "ჩემი prefix არის `$`.\n"
        "ჯერ `$help`, რო ნახოთ რა command-ები მაქ.",
        allowed_mentions=discord.AllowedMentions(everyone=True),
    )


@bot.command()
async def ping(ctx):
    reply = random.choice(ping_random_reply_list)
    await ctx.reply(f'{reply}?', mention_author=False) #, mention_author=False

#this used to be $ჩატ command
@bot.command(aliases=['ჩატ'])
async def chat(ctx):
    content = ctx.message.content.strip()

    if content.startswith('$ჩატ'):
        argument = content[len('$ჩატ'):].strip()
    else:
        argument = content[len('$chat'):].strip()

    if not argument:
        await ctx.reply("რა გინდა ძმა? რა ვერ დალაგდი? აი ესე უნდა -> `$chat ან $ჩატ <მესიჯი>`",mention_author=False)
        return

    is_allowed, cooldown = _consume_ai_request(ctx.author.id)
    if not is_allowed:
        await ctx.reply(
            f"თუ არ გინდა რო ავფეთქდე, ცადე {cooldown}-ში.",
            mention_author=False,
        )
        return

    async with ctx.channel.typing():
        passive_context = await get_passive_context(ctx.channel, ctx.message.id)
        reply = await ask_ai(
            channel_id=ctx.channel.id,
            username=ctx.author.display_name,
            user_message=analyze(argument),
            passive_context=passive_context if passive_context else None)

    await ctx.reply(reply, mention_author=False)


@bot.command()
@commands.has_permissions(administrator=True)
async def reset(ctx):
    clear_history(ctx.channel.id)
    await ctx.send("ამ ჩანელის ჩატ-ჰისთორი/კონტექსტი წაიშალა.")
    return

@bot.command()
async def stock(ctx, ticker: str = None, period: str = DEFAULT_PERIOD):
    # Fetch a stock or crypto snapshot and post a chart + stats embed.
    # Usage: $stock <ticker|name> [1d|1m|1y|5y]
    # Examples: $stock apple 1y  |  $stock bitcoin  |  $stock NVDA 1m

    stock_random_reply = random.choice(stock_not_found_list)
    if ticker is None:
        await ctx.reply("გამოყენება: `$stock <ticker or name> [1d|1m|1y|5y]`\nმაგალითად: `$stock apple 1y` | `$stock bitcoin` | `$stock NVDA 1m | $stock SNDK 1y`\n1d ოფშენი, default flag-ია", mention_author=False)
        return

    period = period.lower()
    if period not in PERIOD_MAP:
        await ctx.reply(f"არასწორი ოფშენია`{period}`. აქედან აარჩიე: `1d` `1m` `1y` `5y`", mention_author=False)
        return

    resolved = resolve_ticker(ticker)

    async with ctx.channel.typing():
        chart_file, embed = await fetch_and_render(resolved, period)

    if chart_file is None:
        await ctx.reply(f"{stock_random_reply} `{resolved}`. ახლიდან ცადე", mention_author=False)
        return

    await ctx.reply(file=chart_file, embed=embed, mention_author=False)


@bot.command()
async def pip(ctx, action: str = None, target: str = None):
    usage = (
        "გამოყენება:\n"
        "`$pip install <package>`\n"
        "`$pip uninstall <package>`\n"
        "`$pip list`\n"
        "`$pip freeze @user`\n"
        "`$pip unfreeze @user`"
    )

    if action is None:
        await ctx.reply(usage, mention_author=False)
        return

    action = action.lower()

    if action == "install":
        if target is None:
            await ctx.reply("package name სადაა ძმა? `$pip install <package>`", mention_author=False)
            return

        if is_numpy_package(target):
            await ctx.reply(random_numpy_reply(), mention_author=False)
            return

        async with ctx.channel.typing():
            response = await install_package(target)
        await ctx.reply(response.content, embed=response.embed, mention_author=False)
        return

    if action == "uninstall":
        if target is None:
            await ctx.reply("package name სადაა ძმა? `$pip uninstall <package>`", mention_author=False)
            return

        response = uninstall_package(target)
        await ctx.reply(response.content, embed=response.embed, mention_author=False)
        return

    if action == "list":
        await ctx.reply(embed=build_package_list_embed(), mention_author=False)
        return

    if action in ("freeze", "unfreeze"):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply("მაგას ადმინი უნდა.", mention_author=False)
            return

        if not ctx.message.mentions:
            await ctx.reply(f"ჰა ვისააქ ხმა ჩასაგდები? `$pip {action} @user`", mention_author=False)
            return

        member = ctx.message.mentions[0]

        try:
            if action == "freeze":
                await member.timeout(timedelta(hours=1), reason=f"$pip freeze by {ctx.author}")
                await ctx.reply(
                    f"მიიწუწეეეეეე! {member.mention}", # freeze action
                    mention_author=False
                )
            else:
                await member.timeout(None, reason=f"$pip unfreeze by {ctx.author}")
                await ctx.reply(
                    f"ხო კაი ნუ ტირი {member.mention}", # unfreeze action
                    mention_author=False
                )
        except discord.Forbidden:
            await ctx.reply("მაგას ვერაფერს ვერ ვუზავ, permission არ მყოფნის.", mention_author=False)
        except discord.HTTPException:
            await ctx.reply("Discord-მა აურია გამიფუჭა ჭაჭიპიტი, ახლიდან ცადე.", mention_author=False)
        return

    await ctx.reply(usage, mention_author=False)


# League of Legends Command
@bot.command()
async def arenaroll(ctx, flag: str = None):

    if flag is None:
        await ctx.reply("გამოყენება: `$arenaroll v2` ან `$arenaroll v3`", mention_author=False)
        return

    flag = flag.lower()
    if flag == "v2":
        count = 2
    elif flag == "v3":
        count = 3
    else:
        await ctx.reply("ეგეთი flag არარი. `v2` ან `v3` აირჩიე.", mention_author=False)
        return

    async with ctx.channel.typing():
        picks = await roll_arena(count)

    mode = "2v2" if flag == "v2" else "3v3"
    champs = "  ·  ".join(f"**{c}**" for c in picks)
    await ctx.reply(f"🎲  **Arena Roll ({mode}):**  {champs}", mention_author=False)


@bot.command()
async def flexroll(ctx, flag: str = None, *mentions: discord.Member):
    if flag is None:
        await ctx.reply(
            "გამოყენება: `$flexroll -champs` | `$flexroll -roles` | `$flexroll -mix`\n"
            "(`-roles` და `-mix`-ისთვის ვოისში უნდა იყოთ 5 კაცი, "
            "ან ხელით/სათითაოდ უნდა მოთაგო: `$flexroll -mix @p1 @p2 @p3 @p4 @p5`)",
            mention_author=False
        )
        return

    flag = flag.lower()
    if flag not in ("-champs", "-roles", "-mix"):
        await ctx.reply("ამეებიდან აირჩიე რომელიმე: `-champs`, `-roles`, ან `-mix`", mention_author=False)
        return

    # -champs: champion picks only, no player detection
    if flag == "-champs":
        async with ctx.channel.typing():
            champs = await roll_champs()
        embed = discord.Embed(title="🎲  Flex Roll — Champions", color=0xC89B3C)
        for role, champ in champs.items():
            embed.add_field(name=ROLE_LABELS[role], value=f"**{champ}**", inline=False)
        await ctx.reply(embed=embed, mention_author=False)
        return

    # -roles / -mix: need exactly 5 players
    # Manual mentions take full priority over voice detection
    if mentions:
        if len(mentions) != 5:
            await ctx.reply(
                f"5 ძმაა 5 კაცი უნდა იყოს, შენ კიდე {len(mentions)} მონიშნე.",
                mention_author=False
            )
            return
        players = [m.display_name for m in mentions]
    else:
        voice_result = _get_voice_players(ctx)

        if voice_result == "not_in_voice":
            await ctx.reply(
                "ვოისში არ ხარ შესული. შედი 4 კაცთან ერთად, "
                f"ან ხელით მონიშნე ესე: `$flexroll {flag} @p1 @p2 @p3 @p4 @p5`",
                mention_author=False
            )
            return

        if isinstance(voice_result, str) and voice_result.startswith("wrong_count"):
            _, count, names = voice_result.split(":", 2)
            await ctx.reply(
                f"ვოისში **{count}** კაცია: {names}\n"
                f"5 კაცია საჭირო — ხელით მონიშნე: `$flexroll {flag} @p1 @p2 @p3 @p4 @p5`",
                mention_author=False
            )
            return

        players = voice_result  # exactly 5 confirmed from voice

    # Build and send result embed
    async with ctx.channel.typing():
        if flag == "-roles":
            assignment = roll_roles(players)
            embed = discord.Embed(title="🎲  Flex Roll — Roles", color=0x5865F2)
            for role, player in assignment.items():
                embed.add_field(name=ROLE_LABELS[role], value=f"**{player}**", inline=False)
            await ctx.reply(embed=embed, mention_author=False)

        elif flag == "-mix":
            assignment = await roll_mix(players)
            embed = discord.Embed(title="🎲  Flex Roll — Mix", color=0x57F287)
            for role, (player, champ) in assignment.items():
                embed.add_field(
                    name=ROLE_LABELS[role],
                    value=f"**{player}** → {champ}",
                    inline=False
                )
            await ctx.reply(embed=embed, mention_author=False)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    if any(word in content for word in megonkalo_trigger_list):
        await message.reply(random.choice(megonkalo_random_reply_list), mention_author=False)

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, err):
    # ERROR variables:

    missing_permission_reply = random.choice(missing_permission_reply_list)

    if isinstance(err, commands.CommandNotFound):
        await ctx.send("ეგ command არმაქ")

    # If no argument provided with a command
    if isinstance(err, commands.MissingRequiredArgument):
        await ctx.send(f"Please provide an argument")

    # If the user is missing admin privileges
    if isinstance(err, commands.MissingPermissions):
        await ctx.send(missing_permission_reply, mention_author=False)

if __name__ == '__main__':
    bot.run(TOKEN)