from dotenv import load_dotenv
from handlers.ai_handler import ask_ai, clear_history
from handlers.stock_handler import fetch_and_render, resolve_ticker, PERIOD_MAP, DEFAULT_PERIOD
from handlers.lol_handler import roll_arena, roll_champs, roll_roles, roll_mix, ROLE_LABELS
from handlers.language_handler import TextAnalyzer
from discord.ext import commands
import requests
import discord
import random
import os

# env variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MY_GUILD = discord.Object(id=os.getenv('MY_GUILD_ID'))

# Bot instance setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)
analyzer = TextAnalyzer()

# conversation variables:
PASSIVE_CONTEXT_LIMIT = 10


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
    """
        Attempt to resolve exactly 5 non-bot members from the author's voice channel.
        Returns:
          - list[str] of display names if exactly 5 found
          - 'not_in_voice' if the author isn't in any voice channel
          - 'wrong_count:<n>:<names>' if the channel exists but has != 5 human members
        """
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        return "not_in_voice"

    members = [m for m in ctx.author.voice.channel.members if not m.bot]

    if len(members) == 5:
        return [m.display_name for m in members]

    names = ", ".join(m.display_name for m in members)
    return f"wrong_count:{len(members)}:{names}"


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    print(f'Bot Ready!')


# check bot state by pinging (online/offline)
@bot.command()
async def ping(ctx):
    ping_random_reply_list: list[str] = ["ჰოუ", "რაა", "რაია",
                                         "რაო", "ხო რაარი", "რახდება",
                                         "ჰოოოო", "რაგინდაააა რააა"]
    reply = random.choice(ping_random_reply_list)
    await ctx.reply(f'{reply}?', mention_author=False) #, mention_author=False


@bot.command()
async def ჩატ(ctx):
    content = ctx.message.content.strip()
    argument = content[len('$ჩატ'):].strip()

    if not argument:
        await ctx.reply("რა გინდა ძმა? რა ვერ დალაგდი? ა ესე დაწერე -> $ჩატ \"<მესიჯი>\"",mention_author=False)
        return

    async with ctx.channel.typing():
        passive_context = await get_passive_context(ctx.channel, ctx.message.id)
        reply = await ask_ai(
            channel_id=ctx.channel.id,
            username=ctx.author.display_name,
            user_message=analyze(argument),
            passive_context=passive_context if passive_context else None)

    await ctx.reply(reply, mention_author=False)
    return


@bot.command()
@commands.has_permissions(administrator=True)
async def reset(ctx):
    clear_history(ctx.channel.id)
    await ctx.send("ამ ჩანელის ჩატ-ჰისთორი/კონტექსტი წაიშალა.")
    return


@bot.command()
async def stock(ctx, ticker: str = None, period: str = DEFAULT_PERIOD):
    """
    Fetch a stock or crypto snapshot and post a chart + stats embed.
    Usage: $stock <ticker|name> [1d|1m|1y|5y]
    Examples: $stock apple 1y  |  $stock bitcoin  |  $stock NVDA 1m
    """
    stock_not_found_list = ['ეგეთი მონაცემები ვერსად ვერ ვნახე', 'ეგ რაარი? არსად არაა',
                      'ვინა, სადა?', 'ვიის?', 'არ მაქ მაგის მონაცემები',]
    stock_random_reply = random.choice(stock_not_found_list)
    if ticker is None:
        await ctx.reply("გამოყენება: `$stock <ticker or name> [1d|1m|1y|5y]`\nმაგალითად: `$stock apple 1y` | `$stock bitcoin` | `$stock NVDA 1m`\n1d ოფშენი, default flag-ია", mention_author=False)
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


# League of Legends Command
@bot.command()
async def arenaroll(ctx, flag: str = None):
    # Roll random champions for Arena mode.
    # Usage: $arenaroll v2 | $arenaroll v3

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
    # Roll for ranked flex.
    # Usage:
    #   $flexroll -champs
    #   $flexroll -roles
    #   $flexroll -mix
    #   $flexroll -roles @p1 @p2 @p3 @p4 @p5   (manual override)
    #   $flexroll -mix   @p1 @p2 @p3 @p4 @p5

    # No Flag
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

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, err):
    # ERROR variables:
    missing_permission_reply_list = ['მაგას შენ ვერიზამ', 'მაგაზე ელიტას მიმართე',
                          'კიდე რაგინდა?', 'ძაან ხოარ გაიჯვი?',
                          'ადმინი არ ხარ', 'არ გაქ უფლება', 'ადმინ... უთხარი რა ამას რამე'
                          'მენეჯერს მიმართე', 'менеджери садаа?']
    missing_permission_reply = random.choice(missing_permission_reply_list)
    confused_reply_list = ['რია?', 'ვინა?', 'სადა?', 'ჰა?',
                           'ეგ არვიცი ძმა', 'როგორ?', 'არ მაქ ეგ',
                           'ეგეთი command არმაქ', 'ეგეთი command არვიცი',
                           'არვიცი ეგ რაარი', 'ეგ რაარი?', 'აბა მერავიცი']
    confused_reply = random.choice(confused_reply_list)


    if isinstance(err, commands.CommandNotFound):
        await ctx.send(confused_reply, mention_author=False)

    # If no argument provided with a command
    if isinstance(err, commands.MissingRequiredArgument):
        await ctx.send(f"Please provide an argument")

    # If the user is missing admin privileges
    if isinstance(err, commands.MissingPermissions):
        await ctx.send(missing_permission_reply, mention_author=False)

if __name__ == '__main__':
    bot.run(TOKEN)