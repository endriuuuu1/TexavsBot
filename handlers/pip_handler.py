import asyncio
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

import discord
import requests


PYPI_URL = "https://pypi.org/pypi/{package}/json"
STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "pip_packages.json"
PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

NUMPY_REPLIES = [
    "აი რათგინდა?",
    "ეგ რო ჩავიწერო, აფეთქდება სერვერი ძმა",
    "მათემატიკის სწავლა გინდა?",
    "გვაფეთქებ?",
    "სანდრო სადაა?",
    "პიპ ინსტალლ ნუმპყ",
    "pip install numpy",
    "სანდრომ იცის ეგ მაგრად, მაგას კითხე",
    "ეგ პროსტა package არაა, ცხოვრების სტილია.",
]


@dataclass
class PipResponse:
    content: str
    embed: discord.Embed | None = None


def is_numpy_package(package_name: str) -> bool:
    return _normalize_name(package_name) == "numpy"


def random_numpy_reply() -> str:
    return random.choice(NUMPY_REPLIES)


async def install_package(package_name: str) -> PipResponse:
    normalized = _normalize_name(package_name)
    if not _is_valid_package_name(normalized):
        return PipResponse("ნორმალურად დაწერე package name.")

    metadata = await _fetch_pypi_metadata(normalized)
    if metadata is None:
        return PipResponse(
            f"```powershell\n"
            f"> pip install {normalized}\n"
            f"ERROR: Could not find a version that satisfies the requirement {normalized}\n"
            f"ERROR: No matching distribution found for {normalized}\n"
            f"```"
        )

    packages = _load_packages()
    canonical_name = metadata["name"]
    key = _normalize_name(canonical_name)
    packages[key] = metadata
    _save_packages(packages)

    transcript = _build_install_transcript(metadata)
    embed = _build_package_embed(metadata, title="Package installed")
    return PipResponse(transcript, embed)


def uninstall_package(package_name: str) -> PipResponse:
    normalized = _normalize_name(package_name)
    if not _is_valid_package_name(normalized):
        return PipResponse("ნორმალურად დაწერე package name")

    packages = _load_packages()
    metadata = packages.pop(normalized, None)

    if metadata is None:
        return PipResponse(
            f"```powershell\n"
            f"> pip uninstall {normalized}\n"
            f"WARNING: Skipping `{normalized}` as it is not installed.\n"
            f"```"
        )

    _save_packages(packages)
    return PipResponse(_build_uninstall_transcript(metadata))


def build_package_list_embed() -> discord.Embed:
    packages = _load_packages()
    embed = discord.Embed(
        title="pip list",
        color=0x57F287 if packages else 0xED4245,
    )

    if not packages:
        embed.description = "```powershell\nPackage    Version\n---------- -------\n(empty)    0.0.0\n```"
        embed.set_footer(text="virtual environment is clean")
        return embed

    sorted_packages = sorted(packages.values(), key=lambda item: item["name"].lower())
    longest_name = max(len(item["name"]) for item in sorted_packages)
    rows = ["Package".ljust(longest_name) + "  Version"]
    rows.append("-" * longest_name + "  " + "-" * 7)
    rows.extend(
        item["name"].ljust(longest_name) + "  " + item["version"]
        for item in sorted_packages
    )

    embed.description = "```powershell\n" + "\n".join(rows) + "\n```"
    for item in sorted_packages[:10]:
        summary = item.get("summary") or "No summary provided."
        embed.add_field(
            name=f"{item['name']} {item['version']}",
            value=summary[:220],
            inline=False,
        )

    if len(sorted_packages) > 10:
        embed.set_footer(text=f"And {len(sorted_packages) - 10} more packages installed")
    else:
        embed.set_footer(text=f"{len(sorted_packages)} package(s) installed")

    return embed


def _normalize_name(package_name: str) -> str:
    return re.sub(r"[-_.]+", "-", package_name.strip().lower())


def _is_valid_package_name(package_name: str) -> bool:
    return bool(package_name and PACKAGE_NAME_RE.fullmatch(package_name))


def _load_packages() -> dict[str, dict[str, str]]:
    if not STATE_FILE.exists():
        return {}

    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    return {
        key: value
        for key, value in data.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def _save_packages(packages: dict[str, dict[str, str]]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(packages, file, ensure_ascii=False, indent=2, sort_keys=True)


async def _fetch_pypi_metadata(package_name: str) -> dict[str, str] | None:
    def fetch() -> dict[str, str] | None:
        try:
            response = requests.get(PYPI_URL.format(package=package_name), timeout=8)
        except requests.RequestException:
            return None

        if response.status_code != 200:
            return None

        data = response.json()
        info = data.get("info", {})
        name = info.get("name") or package_name
        version = info.get("version") or "0.0.0"
        summary = info.get("summary") or "No summary provided."
        homepage = info.get("home_page") or info.get("package_url") or ""

        return {
            "name": str(name),
            "version": str(version),
            "summary": str(summary),
            "homepage": str(homepage),
        }

    return await asyncio.to_thread(fetch)


def _build_install_transcript(metadata: dict[str, str]) -> str:
    name = metadata["name"]
    version = metadata["version"]
    wheel_name = name.replace("-", "_")
    download_speed = random.choice(["4.2 MB/s", "8.7 MB/s", "11.3 MB/s", "22.9 MB/s"])
    download_size = random.randint(84, 950)

    return (
        f"```powershell\n"
        f"> pip install {name}\n"
        f"Collecting {name}\n"
        f"  Downloading {wheel_name}-{version}-py3-none-any.whl ({download_size} kB)\n"
        f"     ---------------------------------------- {download_size}/{download_size} kB {download_speed}\n"
        f"Installing collected packages: {name}\n"
        f"Successfully installed {name}-{version}\n"
        f"```"
    )


def _build_uninstall_transcript(metadata: dict[str, str]) -> str:
    name = metadata["name"]
    version = metadata["version"]
    return (
        f"```powershell\n"
        f"> pip uninstall {name}\n"
        f"Found existing installation: {name} {version}\n"
        f"Uninstalling {name}-{version}:\n"
        f"  Successfully uninstalled {name}-{version}\n"
        f"```"
    )


def _build_package_embed(metadata: dict[str, str], title: str) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=metadata.get("summary") or "No summary provided.",
        color=0x5865F2,
    )
    embed.add_field(name="Name", value=metadata["name"], inline=True)
    embed.add_field(name="Version", value=metadata["version"], inline=True)

    homepage = metadata.get("homepage")
    if homepage:
        embed.add_field(name="PyPI", value=homepage, inline=False)

    embed.set_footer(text="Server install only. only Local packages were changed.")
    return embed
