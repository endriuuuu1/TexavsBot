import io
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import discord

# ── Ticker alias map ──────────────────────────────────────────────────────────
# Maps friendly names and short aliases → canonical Yahoo Finance ticker
# Both directions work: "apple" → "AAPL", "aapl" → "AAPL"
ALIAS_MAP: dict[str, str] = {
    # ── Crypto (top 10) ───────────────────────────────────────────────────────
    "bitcoin":   "BTC-USD", "btc":      "BTC-USD",
    "ethereum":  "ETH-USD", "eth":      "ETH-USD",
    "tether":    "USDT-USD","usdt":     "USDT-USD",
    "solana":    "SOL-USD", "sol":      "SOL-USD",
    "bnb":       "BNB-USD",
    "xrp":       "XRP-USD",
    "usdc":      "USDC-USD",
    "dogecoin":  "DOGE-USD","doge":     "DOGE-USD",
    "cardano":   "ADA-USD", "ada":      "ADA-USD",
    "tron":      "TRX-USD", "trx":      "TRX-USD",

    # ── Tech / Familiar Stocks (top 20) ───────────────────────────────────────
    "apple":     "AAPL",    "aapl":     "AAPL",
    "microsoft": "MSFT",    "msft":     "MSFT",
    "nvidia":    "NVDA",    "nvda":     "NVDA",
    "google":    "GOOGL",   "googl":    "GOOGL",   "alphabet": "GOOGL",
    "amazon":    "AMZN",    "amzn":     "AMZN",
    "meta":      "META",
    "tesla":     "TSLA",    "tsla":     "TSLA",
    "netflix":   "NFLX",    "nflx":     "NFLX",
    "amd":       "AMD",
    "intel":     "INTC",    "intc":     "INTC",
    "micron":    "MU",      "mu":       "MU",
    "qualcomm":  "QCOM",    "qcom":     "QCOM",
    "samsung":   "005930.KS",
    "tsmc":      "TSM",     "tsm":      "TSM",
    "paypal":    "PYPL",    "pypl":     "PYPL",
    "spotify":   "SPOT",    "spot":     "SPOT",
    "uber":      "UBER",
    "airbnb":    "ABNB",    "abnb":     "ABNB",
    "coinbase":  "COIN",    "coin":     "COIN",
    "sandisk":   "SNDK",    "sndk":     "SNDK",
}

# Period config
# Maps user-facing flag → yfinance (period, interval) tuple
# Interval is chosen to give a clean number of data points for each period
PERIOD_MAP: dict[str, tuple[str, str]] = {
    "1d":  ("1d",  "5m"),
    "1m":  ("1mo", "1d"),
    "1y":  ("1y",  "1wk"),
    "5y":  ("5y",  "1wk"),
}
DEFAULT_PERIOD = "1d"

# Discord dark background color (used as chart background)
DISCORD_BG = "#2b2d31"


def resolve_ticker(user_input: str) -> str:
    """
    Resolve a user-supplied string to a canonical Yahoo Finance ticker.
    Checks alias map first (case-insensitive), then falls back to
    uppercasing the raw input so unknown tickers like 'ASML' still work.
    """
    return ALIAS_MAP.get(user_input.lower().strip(), user_input.upper().strip())


def _friendly_name(ticker: str, info: dict) -> str:
    # Return a human-readable name for the embed title.
    return info.get("shortName") or info.get("longName") or ticker


def _fmt_large(value) -> str:
    # Format large numbers (market cap, volume) into readable strings.
    if value is None:
        return "—"
    value = float(value)
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.2f}"


def _fmt_price(value) -> str:
    if value is None:
        return "—"
    return f"${float(value):,.2f}"


async def fetch_and_render(
    ticker: str,
    period_flag: str,
) -> tuple[discord.File, discord.Embed] | tuple[None, None]:
    """
    Fetch price history and metadata for `ticker`, draw a chart, and
    return (discord.File, discord.Embed) ready to send.
    Returns (None, None) if the ticker is invalid or data is unavailable.
    """
    period, interval = PERIOD_MAP.get(period_flag, PERIOD_MAP[DEFAULT_PERIOD])

    # Fetch data
    asset = yf.Ticker(ticker)

    hist = asset.history(period=period, interval=interval)
    if hist.empty:
        return None, None

    try:
        info = asset.info or {}
    except Exception:
        info = {}

    # Compute period change
    price_start = float(hist["Close"].iloc[0])
    price_end   = float(hist["Close"].iloc[-1])
    change_abs  = price_end - price_start
    change_pct  = (change_abs / price_start) * 100 if price_start else 0
    is_up       = change_abs >= 0

    line_color = "#3ba55d" if is_up else "#ed4245"   # Discord green / red
    sign       = "+" if is_up else ""

    # Draw chart
    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor(DISCORD_BG)
    ax.set_facecolor(DISCORD_BG)

    closes = hist["Close"]
    x      = range(len(closes))

    ax.plot(closes.values, color=line_color, linewidth=1.8, zorder=3)
    ax.fill_between(x, closes.values, alpha=0.12, color=line_color, zorder=2)

    # Subtle horizontal grid only
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis="y", color="#3f3f3f", linewidth=0.6, zorder=1)
    ax.grid(axis="x", visible=False)

    # Axis styling
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors="#9a9a9a", labelsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.2f}"))

    # X-axis: show a handful of date labels
    n        = len(hist)
    step     = max(n // 5, 1)
    x_ticks  = list(range(0, n, step))
    x_labels = [str(hist.index[i])[:10] for i in x_ticks]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, rotation=20, ha="right")

    friendly = _friendly_name(ticker, info)
    ax.set_title(
        f"{friendly}  ({ticker})  —  {period_flag.upper()}",
        color="#ffffff", fontsize=11, pad=10, loc="left"
    )

    plt.tight_layout(pad=1.2)

    # Render to in-memory bytes
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=DISCORD_BG)
    plt.close(fig)
    buf.seek(0)

    chart_file = discord.File(fp=buf, filename="chart.png")

    # Build embed
    embed = discord.Embed(color=0x3ba55d if is_up else 0xed4245)

    embed.add_field(
        name="Price",
        value=f"**{_fmt_price(price_end)}**\n{sign}{change_abs:.2f} ({sign}{change_pct:.2f}%) over {period_flag.upper()}",
        inline=False
    )
    embed.add_field(name="Open",     value=_fmt_price(hist["Open"].iloc[0]),         inline=True)
    embed.add_field(name="High",     value=_fmt_price(hist["High"].max()),            inline=True)
    embed.add_field(name="Low",      value=_fmt_price(hist["Low"].min()),             inline=True)
    embed.add_field(name="Mkt Cap",  value=_fmt_large(info.get("marketCap")),         inline=True)
    embed.add_field(name="52W High", value=_fmt_price(info.get("fiftyTwoWeekHigh")),  inline=True)
    embed.add_field(name="52W Low",  value=_fmt_price(info.get("fiftyTwoWeekLow")),   inline=True)

    # P/E only meaningful for stocks, shows — for crypto
    embed.add_field(name="P/E Ratio", value=str(round(info["trailingPE"], 2)) if info.get("trailingPE") else "—", inline=True)

    # Volume label differs: stocks → Avg Volume, crypto → 24h Volume
    vol_key   = "volume24Hr" if ticker.endswith("-USD") else "averageVolume"
    vol_label = "24h Volume" if ticker.endswith("-USD") else "Avg Volume"
    embed.add_field(name=vol_label, value=_fmt_large(info.get(vol_key)), inline=True)

    embed.set_image(url="attachment://chart.png")
    embed.set_footer(text="Data via Yahoo Finance · Not financial advice")

    return chart_file, embed
