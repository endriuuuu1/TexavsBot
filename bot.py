from dotenv import load_dotenv
from handlers.ai_handler import ask_ai, clear_history
from handlers.stock_handler import fetch_and_render, resolve_ticker, PERIOD_MAP, DEFAULT_PERIOD
from handlers.language_handler import TextAnalyzer
from discord.ext import commands
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


# check bot state by pinging (online/offline)
@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    print(f'Bot Ready!')

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