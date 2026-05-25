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
from datetime import timedelta
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
bot = commands.Bot(command_prefix='$', intents=intents, help_command=None)
analyzer = TextAnalyzer()

# conversation variables:
PASSIVE_CONTEXT_LIMIT = 10
megonkalo_trigger_list = ['megonka', 'megonkalo', 'gonka', 'gonkalo','megonkaloze','megonkaze','megonkalos',
                          'მეგონკა', 'მეგონკალო', 'გონკა', 'გონკალო', 'მეგონკალოზე', 'მეგონკაზე', 'მეგონკალოს']
megonkalo_random_reply_list = ["94", "94ით მოფრინავს", "ჩვენი ძმა მეგონკა", "გიო wowი არ ვიყომაროთ?",
                               "ეგ ვისი ძმაკაცია?", "დაურეკეთ მეგონკას ჩვენ ძმას", "94ჯერ ვითამაშე wow დღეს", "ბანჯოლას ძმაკაცი ვინახსენა?"]
ping_random_reply_list: list[str] = ["ჰოუ", "რაა", "რაია",
                                    "რაო", "ხო რაარი", "რახდება",
                                     "ჰოოოო", "რაგინდაააა რააა"]
stock_not_found_list = ['ეგეთი მონაცემები ვერსად ვერ ვნახე', 'ეგ რაარი? არსად არაა',
                      'ვინა, სადა?', 'ვიის?', 'არ მაქ მაგის მონაცემები']
missing_permission_reply_list = ['მაგას შენ ვერიზამ', 'მაგაზე ელიტას მიმართე',
                          'კიდე რაგინდა?', 'ძაან ხოარ გაიჯვი?',
                          'ადმინი არ ხარ', 'არ გაქ უფლება', 'ადმინ... უთხარი რა ამას რამე'
                          'მენეჯერს მიმართე', 'менеджери садаа?']

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

# check bot state by pinging (online/offline)
@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    print(f'Bot Ready!')

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
        await ctx.reply("რა გინდა ძმა? რა ვერ დალაგდი? აი ესე უნდა -> `$chat <მესიჯი>`",mention_author=False)
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