from discord.ext.commands import MissingRequiredArgument, errors
from dotenv import load_dotenv
from ai_handler import ask_ai, clear_history
from language import TextAnalyzer
from discord.ext import commands
import discord
import os
import random

# env variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot instance setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)
#MY_GUILD = discord.Object(id=788188909343342602)
analyzer = TextAnalyzer()

# conversation variables:
PASSIVE_CONTEXT_LIMIT = 10
ping_random_reply_list: list[str] = ["ჰოუ", "რაა", "რაია", "რაო", "ხო რაარი", "რახდება", "ჰოოოო", "რაგინდაააა რააა"]

class MyFlags(commands.FlagConverter):
    reason: str = "No reason provided"
    silent: bool = False


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
    await ctx.reply(f'{random.choice(ping_random_reply_list)}?') #, mention_author=False

@bot.command()
async def ჩატ(ctx):
    content = ctx.message.content.strip()
    argument = content[len('$ჩატ'):].strip()

    if not argument:
        await ctx.send("რა გინდა ძმა? რა ვერ დალაგდი? ა ესე დაწერე -> $ჩატ \"<მესიჯი>\"")
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
async def reset(ctx):
    clear_history(ctx.channel.id)
    await ctx.send("Conversation history cleared for this channel")
    return

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, err):
    if isinstance(err, commands.MissingRequiredArgument):
        await ctx.send(f"Please provide argument")

if __name__ == '__main__':
    bot.run(TOKEN)