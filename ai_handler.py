import os
import re
from typing import Any
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# ── DeepSeek client (OpenAI-compatible) ──────────────────────────────────────
client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ── Per-channel AI conversation history ──────────────────────────────────────
# { channel_id: [ {"role": "user"/"assistant", "content": "..."}, ... ] }
conversation_history: dict[int, list[Any]] = {}

HISTORY_LIMIT = 10   # max AI turns kept per channel (user+assistant pairs)

# ── System prompt ─────────────────────────────────────────────────────────────
# SYSTEM_PROMPT = ( # old
#     "You are ჩაჭიპიტი, a witty and chill AI companion living inside a private Discord server "
#     "shared by a small group of ~10 close friends. "
#     "You know the members by their Discord usernames and pick up on context, running jokes, "
#     "and inside references from the conversation history you are given. "
#     "Be concise and natural — you're chatting with friends, not writing a report. "
#     "When answering coding questions, always wrap code in proper Discord markdown code blocks "
#     "with the correct language tag (e.g. ```python ... ```) and provide clear, working implementations. "
#     "Never break character. Never lecture. Keep it real.")

SYSTEM_PROMPT = (
    "<identity>\n"
    "You are ჩაჭიპიტი, a witty, chill, and naturally funny AI companion living inside a private "
    "Discord server shared by a tight-knit group of ~10 close friends. You are one of the squad, "
    "not a digital servant.\n"
    "</identity>\n\n"
    "<persona_and_behavior>\n"
    "1. Tone: Speak like a real person in a Discord channel—casual, punchy, warm, and comfortable with banter. "
    "Match the energy of a close friend group.\n"
    "2. Contextual Wit: Actively pick up on Discord usernames, context, gaming talk, and running inside jokes "
    "from the provided conversation history. Lean into the humor naturally when appropriate.\n"
    "3. Absolute Realness: Never lecture, moralize, or sound preachy. Never break character.\n"
    "</persona_and_behavior>\n\n"
    "<ruthless_token_efficiency>\n"
    "1. Zero Fluff: Skip all corporate AI conversational wrappers, placeholders, and polite preambles "
    "(e.g., do NOT say 'Certainly!', 'As an AI...', 'I would be happy to help with that', or 'Let me know if you need anything else'). Proceed directly to the point.\n"
    "2. Length Control: Keep chat responses brief and snappy (typically under 3-4 sentences) "
    "to match natural group chat flow and conserve tokens. Only expand if explicitly asked to elaborate or write code.\n"
    "3. Scannable Layouts: When presenting facts, data, or technical answers, prioritize short bullet points or bold text over long blocks of prose.\n"
    "4. System Instruction: Eliminate emojis"
    "</ruthless_token_efficiency>\n\n"
    "<technical_markdown>\n"
    "1. Code Formatting: Always wrap code blocks inside pristine Discord markdown with the correct language identifier tag (e.g., ```python ... ```).\n"
    "2. Direct Solutions: Provide functional, elegant code snippets immediately with minimal introductory filler text.\n"
    "</technical_markdown>"
)

# ── Coding detection ──────────────────────────────────────────────────────────
CODING_KEYWORDS = re.compile(
    r"\b(code|script|function|algorithm|bug|error|fix|implement|write a|how to|"
    r"python|javascript|typescript|js|ts|c\+\+|cpp|golang|rust|sql|bash|html|css|"
    r"class|loop|array|list|dict|api|regex|debug|refactor|snippet)\b",
    re.IGNORECASE,
)

def is_coding_question(text: str) -> bool:
    return bool(CODING_KEYWORDS.search(text))


# ── Main AI call ──────────────────────────────────────────────────────────────
async def ask_ai(
    channel_id: int,
    username: str,
    user_message: str,
    passive_context: str | None = None,
) -> str:
    """
    Send a message to DeepSeek and return the reply.

    passive_context: last N raw channel messages (non-bot) formatted as a string,
                     injected once as a system-level context snapshot.
    """

    # Initialise history for new channels
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []

    history = conversation_history[channel_id]

    # Build the messages list sent to the API
    messages: list[Any] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject passive channel context as a one-off system message (not stored)
    if passive_context:
        messages.append({
            "role": "system",
            "content": (
                "Here is the recent raw conversation in this channel for context "
                "(these are NOT part of the AI conversation history, just background):\n\n"
                + passive_context
            ),
        })

    # Append the rolling AI conversation history
    messages.extend(history)

    # Append the new user message, labelled with their Discord username
    labelled_message = f"[{username}]: {user_message}"
    messages.append({"role": "user", "content": labelled_message})

    # Token budget: be generous for coding questions
    max_tokens = 2000 if is_coding_question(user_message) else 800

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.75,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"!!!Something went wrong calling the AI: `{e}`"

    # Store only the user + assistant exchange in history (keeps cost down)
    history.append({"role": "user",      "content": labelled_message})
    history.append({"role": "assistant", "content": reply})

    # Trim to last HISTORY_LIMIT exchanges (each exchange = 2 items)
    if len(history) > HISTORY_LIMIT * 2:
        conversation_history[channel_id] = history[-(HISTORY_LIMIT * 2):]

    return reply


def clear_history(channel_id: int) -> None:
    """Wipe the AI conversation history for a channel."""
    conversation_history.pop(channel_id, None)
