import discord
import os
import random
from dotenv import load_dotenv
from ai_handler import ask_ai, clear_history

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ── Discord client setup ──────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# How many recent raw channel messages to scoop up as passive context
PASSIVE_CONTEXT_LIMIT = 10

# conversation variables
ping_random_reply_list: list[str] = ["ჰოუ", "რაა", "რაია", "რაო", "ხო რაარი", "რახდება"]

# ── Helper: gather passive channel context ────────────────────────────────────
async def get_passive_context(channel, triggering_message_id: int) -> str:
    """
    Fetch the last PASSIVE_CONTEXT_LIMIT messages before the triggering command,
    ignoring bot messages and the command itself.
    Returns a formatted string like:
        Username: message content
        Username: message content
    """
    lines = []
    async for msg in channel.history(limit=PASSIVE_CONTEXT_LIMIT + 5, before=discord.Object(id=triggering_message_id)):
        if msg.author.bot:
            continue
        lines.append(f"{msg.author.display_name}: {msg.content}")
        if len(lines) >= PASSIVE_CONTEXT_LIMIT:
            break
    lines.reverse()  # chronological order
    return "\n".join(lines)


# ── Events ────────────────────────────────────────────────────────────────────
@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("Bot is ready.")


@client.event
async def on_message(message: discord.Message):
    # Never respond to ourselves or other bots
    if message.author.bot:
        return

    content = message.content.strip()

    # ── $ჩატ ──────────────────────────────────────────────────────────────────
    # Usage: $ჩატ <your message>
    if content.startswith("$ჩატ"):
        user_input = content[len("$ჩატ"):].strip()

        if not user_input:
            await message.reply("რა გინდა ძმა? რა ვერ დალაგდი? ა ესე დაწერე -> $ჩატ \"<მესიჯი>\"")
            return

        # Show typing indicator while we wait for the AI
        async with message.channel.typing():
            passive_ctx = await get_passive_context(message.channel, message.id)
            reply = await ask_ai(
                channel_id=message.channel.id,
                username=message.author.display_name,
                user_message=user_input,
                passive_context=passive_ctx if passive_ctx else None,
            ) # ai_handler method

        await message.reply(reply)
        return

    # ── $reset ────────────────────────────────────────────────────────────────
    # Clears the AI conversation history for this channel
    if content == "$reset":
        clear_history(message.channel.id) # ai_handler method
        await message.reply("Conversation history cleared for this channel.")
        return

    # ── $hello ────────────────────────────────────────────────────────────────
    # Simple ping to confirm the bot is alive
    if content == "$hello":
        await message.reply(f"{random.choice(ping_random_reply_list)}?")
        return

    # ── $help ─────────────────────────────────────────────────────────────────
    if content == "$help":
        help_text = (
            "**🤖 ჩაჭიპიტის კომანდების სია**\n\n"
            "`$ჩატ <მესიჯი>` — AI მოდელთან საუბარი. კონტექსტიც ესმის ასე თუ ისე.\n"
            "`$reset` — AI-ს მეხსიერების გასუფთავება ამ კონკრეტული ჩენელისთვის (!!! არ გამოიყენოთ უაზროდ !!!).\n"
            "`$hello` — ჩეკი ონლაინია ბოტი თუ არა.\n"
            "`$help` — ეს მესიჯი.\n\n"
            #"*Coding questions get longer, syntax-highlighted responses automatically.*"
        )
        await message.reply(help_text)
        return


if __name__ == "__main__":
    client.run(TOKEN)
