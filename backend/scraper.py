import asyncio
import json
import os
import re
from typing import Any, Callable

import httpx
from anthropic import Anthropic
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_html, scrape_me
from recipe_scrapers._exceptions import (
    ElementNotFoundInHtml,
    FieldNotProvidedByWebsiteException,
    NoSchemaFoundInWildMode,
    StaticValueException,
    WebsiteNotImplementedError,
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 4096
CLAUDE_INPUT_CHAR_LIMIT = 20000

CLAUDE_PROMPT = """Extract the recipe from the page text below and return ONLY a single JSON object. No prose, no markdown fences.

Schema:
{
  "title": string,
  "servings": integer,
  "prep_min": integer,
  "cook_min": integer,
  "cuisine": string,
  "tags": [string],
  "ingredients": [
    {"quantity": number, "unit": string, "name": string, "preparation": string}
  ],
  "steps": [
    {"step_number": integer, "instruction": string}
  ]
}

If a field is unknown, use an empty string, empty list, or 0. Do not invent data.

PAGE TEXT:
"""

# Exceptions from recipe-scrapers that mean "this path didn't work, try the next one".
_SCRAPER_RECOVERABLE = (
    WebsiteNotImplementedError,
    NoSchemaFoundInWildMode,
    ElementNotFoundInHtml,
    FieldNotProvidedByWebsiteException,
    StaticValueException,
)


async def scrape_url(url: str) -> dict:
    """Fetch a URL and return a normalised recipe dict.

    Tier 1: recipe-scrapers official scrape_me path.
    Tier 2: browser-style fetch + recipe-scrapers generic schema.org fallback.
    Tier 3: Claude on page text + embedded JSON, for SPAs and obscure layouts.
    Raises ValueError if neither path yields a recipe.
    """
    scraped = await _try_scrape_me(url)
    if scraped is not None:
        return {**scraped, "source": "recipe-scrapers"}

    html = await _fetch(url)

    scraped = _try_recipe_scrapers_html(html, url)
    if scraped is not None:
        return {**scraped, "source": "recipe-scrapers"}

    soup = BeautifulSoup(html, "html.parser")
    text = _page_text_for_claude(soup)
    try:
        raw = _claude_extract(text)
    except ClaudeExtractError as e:
        raise ValueError(f"Claude fallback failed: {e}") from e
    normalised = normalise_claude(raw, url)
    if not normalised["ingredients"] and not normalised["steps"]:
        raise ValueError("No recipe ingredients or instructions found")
    return {**normalised, "source": "claude"}


async def _fetch(url: str) -> str:
    async with httpx.AsyncClient(
        headers=BROWSER_HEADERS,
        follow_redirects=True,
        timeout=15.0,
        http2=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def _try_scrape_me(url: str) -> dict | None:
    """Run recipe-scrapers' official URL workflow without blocking the event loop."""
    try:
        scraper = await asyncio.to_thread(scrape_me, url)
    except _SCRAPER_RECOVERABLE:
        return None
    except Exception:
        return None
    return _normalise_scraper(scraper, url)


def _try_recipe_scrapers_html(html: str, url: str) -> dict | None:
    """Run recipe-scrapers against already-fetched HTML."""
    try:
        scraper = scrape_html(html=html, org_url=url, supported_only=False)
    except _SCRAPER_RECOVERABLE:
        return None
    except Exception:
        return None
    return _normalise_scraper(scraper, url)


def _normalise_scraper(scraper: Any, url: str) -> dict | None:
    """Return a normalized recipe dict from a recipe-scrapers scraper object."""
    title = _clean_text(_safe(scraper.title, ""))
    ingredients_raw = _string_list(_safe(scraper.ingredients, []))
    steps_raw = _string_list(_safe(scraper.instructions_list, []))

    # Avoid saving a title-only metadata hit as a recipe. Claude can try richer page text.
    if not ingredients_raw and not steps_raw:
        return None

    return {
        "title": title or "Untitled",
        "source_url": url,
        "servings": _parse_yield(_safe(scraper.yields, "")),
        "prep_min": _int_or_zero(_safe(scraper.prep_time, 0)),
        "cook_min": _resolve_cook_time(scraper),
        "cuisine": _clean_text(_safe(scraper.cuisine, "")),
        "tags": _collect_tags(scraper),
        "ingredients": [_parse_ingredient_string(s) for s in ingredients_raw],
        "steps": [
            {"step_number": i, "instruction": line}
            for i, line in enumerate(steps_raw, start=1)
        ],
    }


def _safe(fn: Callable, default: Any) -> Any:
    """Call a recipe-scrapers method and swallow its per-field exceptions."""
    try:
        return fn()
    except _SCRAPER_RECOVERABLE:
        return default
    except Exception:
        return default


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _string_list(value: Any) -> list[str]:
    """Normalize scraper list-ish fields while dropping empty items."""
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        values = [value]
    return [cleaned for item in values if (cleaned := _clean_text(item))]


def _int_or_zero(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        return int(match.group(0)) if match else 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _resolve_cook_time(scraper) -> int:
    """Prefer explicit cook_time; fall back to total_time if cook is missing but prep is known."""
    cook = _int_or_zero(_safe(scraper.cook_time, 0))
    if cook:
        return cook
    total = _int_or_zero(_safe(scraper.total_time, 0))
    prep = _int_or_zero(_safe(scraper.prep_time, 0))
    if total and prep and total > prep:
        return total - prep
    return total


def _collect_tags(scraper) -> list[str]:
    raw: list[Any] = []
    for field in (scraper.category, scraper.keywords):
        value = _safe(field, None)
        if value:
            raw.append(value)

    tags: list[str] = []
    for value in raw:
        if isinstance(value, list):
            for v in value:
                tags.extend(_split_tag_string(str(v)))
        else:
            tags.extend(_split_tag_string(str(value)))

    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        key = t.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(t)
    return out


def _split_tag_string(value: str) -> list[str]:
    return [t.strip() for t in value.split(",") if t.strip()]


def _parse_yield(value: Any) -> int:
    """Yield can be int, "4", "4 servings", or ["4", "4 servings"]."""
    if value is None:
        return 0
    if isinstance(value, list):
        value = value[0] if value else 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        return int(match.group(0)) if match else 0
    return 0


# ────────────────────────────────────────────────────────────────
# Claude fallback
# ────────────────────────────────────────────────────────────────


def _visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _page_text_for_claude(soup: BeautifulSoup) -> str:
    """Build the payload sent to Claude: visible text + embedded SPA JSON blobs.

    Next.js/Nuxt/Gatsby sites often render empty chrome while the real data sits in
    <script type="application/json"> (e.g. __NEXT_DATA__). Harvest those before
    _visible_text nukes all <script> tags.
    """
    json_blobs: list[str] = []
    for script in soup.find_all("script", {"type": "application/json"}):
        body = script.string or script.get_text() or ""
        body = body.strip()
        if len(body) > 200:
            sid = script.get("id") or "inline"
            json_blobs.append(f"--- embedded JSON ({sid}) ---\n{body}")

    visible = _visible_text(soup)

    parts = [f"--- visible page text ---\n{visible}"]
    parts.extend(json_blobs)
    return "\n\n".join(parts)[:CLAUDE_INPUT_CHAR_LIMIT]


class ClaudeExtractError(Exception):
    """Raised when the Claude fallback can't produce a recipe dict."""


def _claude_extract(page_text: str) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeExtractError("ANTHROPIC_API_KEY is not set")

    client = Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": CLAUDE_PROMPT + page_text}],
        )
    except Exception as e:
        raise ClaudeExtractError(f"Claude API call failed: {e}") from e

    if message.stop_reason == "max_tokens":
        raise ClaudeExtractError(
            f"Claude response was truncated at {CLAUDE_MAX_TOKENS} tokens — "
            "recipe likely too long; increase CLAUDE_MAX_TOKENS"
        )

    body = "".join(block.text for block in message.content if block.type == "text").strip()
    return parse_claude_json_body(body)


def parse_claude_json_body(body: str) -> dict:
    """Strip optional markdown fences and parse a Claude text response as JSON."""
    if not body:
        raise ClaudeExtractError("Claude returned an empty response")
    if body.startswith("```"):
        body = re.sub(r"^```(?:json)?\s*|\s*```$", "", body, flags=re.MULTILINE).strip()

    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        snippet = body[:200].replace("\n", " ")
        raise ClaudeExtractError(f"Claude did not return JSON: {e.msg} — got: {snippet!r}") from e


def normalise_claude(raw: dict, source_url: str) -> dict:
    if not isinstance(raw, dict):
        raise ClaudeExtractError("Claude JSON response was not an object")

    ingredients_in = raw.get("ingredients") or []
    ingredients = []
    for item in ingredients_in:
        if isinstance(item, dict):
            quantity = item.get("quantity") or 1.0
            ingredients.append(
                {
                    "quantity": _parse_quantity(str(quantity)),
                    "unit": _clean_text(item.get("unit", "")),
                    "name": _clean_text(item.get("name", "")),
                    "preparation": _clean_text(item.get("preparation", "")),
                }
            )
        elif isinstance(item, str):
            ingredients.append(_parse_ingredient_string(item))

    steps_in = raw.get("steps") or []
    steps = []
    for idx, item in enumerate(steps_in, start=1):
        if isinstance(item, dict):
            steps.append(
                {
                    "step_number": _int_or_zero(item.get("step_number")) or idx,
                    "instruction": _clean_text(item.get("instruction", "")),
                }
            )
        elif isinstance(item, str):
            steps.append({"step_number": idx, "instruction": _clean_text(item)})

    ingredients = [item for item in ingredients if item["name"]]
    steps = [item for item in steps if item["instruction"]]

    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return {
        "title": _clean_text(raw.get("title", "")) or "Untitled",
        "source_url": source_url,
        "servings": _int_or_zero(raw.get("servings")),
        "prep_min": _int_or_zero(raw.get("prep_min")),
        "cook_min": _int_or_zero(raw.get("cook_min")),
        "cuisine": _clean_text(raw.get("cuisine", "")),
        "tags": [_clean_text(t) for t in tags if _clean_text(t)],
        "ingredients": ingredients,
        "steps": steps,
    }


# ────────────────────────────────────────────────────────────────
# Ingredient string → {quantity, unit, name, preparation}
# ────────────────────────────────────────────────────────────────


_UNICODE_FRACTIONS = {
    "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3,
    "¼": 0.25, "¾": 0.75,
    "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8,
    "⅙": 1 / 6, "⅚": 5 / 6,
    "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
}
_FRAC_CHARS = "".join(_UNICODE_FRACTIONS.keys())

_QTY_PATTERN = (
    rf"(?:\d+(?:\.\d+)?(?:\s+\d+/\d+|\s*[{_FRAC_CHARS}])?"
    rf"|\d+/\d+"
    rf"|[{_FRAC_CHARS}])"
)

_UNIT_PATTERN = (
    r"(?:cups?|c\.|tbsps?|tablespoons?|tsps?|teaspoons?|"
    r"oz|ounces?|lbs?|pounds?|g|grams?|kg|kilograms?|"
    r"ml|milliliters?|l|liters?|litres?|"
    r"pints?|quarts?|gallons?|cloves?|cans?|sticks?|slices?|pieces?)"
)

_INGREDIENT_RE = re.compile(
    rf"""^\s*
        (?P<qty>{_QTY_PATTERN})?
        \s*
        (?:(?P<unit>{_UNIT_PATTERN})\.?\b)?
        \s*
        (?P<rest>.+?)\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _parse_ingredient_string(raw: str) -> dict:
    """Split "2 cups flour, sifted" → {quantity, unit, name, preparation}. Fallback: whole string as name."""
    text = " ".join(raw.split())
    if not text:
        return {"quantity": 1.0, "unit": "", "name": "", "preparation": ""}

    match = _INGREDIENT_RE.match(text)
    if not match or (not match.group("qty") and not match.group("unit")):
        return {"quantity": 1.0, "unit": "", "name": text, "preparation": ""}

    qty = _parse_quantity(match.group("qty"))
    unit = (match.group("unit") or "").lower()
    rest = (match.group("rest") or "").lstrip(".,;: ")

    name, preparation = _split_name_prep(rest)

    return {
        "quantity": qty,
        "unit": unit,
        "name": name,
        "preparation": preparation,
    }


def _split_name_prep(text: str) -> tuple[str, str]:
    """Split on the first comma that's NOT inside parentheses."""
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            return text[:i].strip(), text[i + 1 :].strip()
    return text.strip(), ""


def _parse_quantity(raw: str | None) -> float:
    if not raw:
        return 1.0
    raw = raw.strip()

    for char, value in _UNICODE_FRACTIONS.items():
        if char in raw:
            whole_part = raw.replace(char, "").strip()
            whole = float(whole_part) if whole_part else 0.0
            return whole + value

    if " " in raw:
        whole, frac = raw.split(None, 1)
        try:
            return float(whole) + _parse_quantity(frac)
        except ValueError:
            return 1.0
    if "/" in raw:
        num, denom = raw.split("/", 1)
        try:
            return float(num) / float(denom)
        except (ValueError, ZeroDivisionError):
            return 1.0
    try:
        return float(raw)
    except ValueError:
        return 1.0
