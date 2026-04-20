import asyncio
import base64
import os

from anthropic import Anthropic

from backend.scraper import (
    CLAUDE_MAX_TOKENS,
    CLAUDE_MODEL,
    ClaudeExtractError,
    normalise_claude,
    parse_claude_json_body,
)

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
SUPPORTED_DOC_TYPES = {"application/pdf"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

PARSER_PROMPT = """Extract the recipe from this file and return ONLY a single JSON object. No prose, no markdown fences.

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

Rules:
- quantity must be a float (0.5 not "half", 0.25 not "quarter")
- unit should be standardised: cup, tbsp, tsp, oz, g, ml, lb — or empty string
- preparation is optional; use empty string if none
- if a field is unknown, use an empty string, empty list, or 0 — do not invent data
- if multiple recipes are visible, extract only the main/largest one
"""


async def parse_upload(
    file_bytes: bytes, media_type: str, filename: str | None = None
) -> dict:
    """Send an image or PDF to Claude Vision and return a normalised recipe dict.

    Raises ValueError for invalid media type or oversized upload.
    Raises ClaudeExtractError if Claude's response is missing, truncated, or unparseable.
    Lets anthropic SDK errors propagate (FastAPI maps to 500).
    """
    if media_type not in SUPPORTED_IMAGE_TYPES and media_type not in SUPPORTED_DOC_TYPES:
        raise ValueError(f"Unsupported file type: {media_type}")

    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Upload too large: {len(file_bytes)} bytes (max {MAX_UPLOAD_BYTES})"
        )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeExtractError("ANTHROPIC_API_KEY is not set")

    data = base64.standard_b64encode(file_bytes).decode("ascii")
    block_type = "document" if media_type in SUPPORTED_DOC_TYPES else "image"
    file_block = {
        "type": block_type,
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }

    client = Anthropic(api_key=api_key)
    message = await asyncio.to_thread(
        client.messages.create,
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": [file_block, {"type": "text", "text": PARSER_PROMPT}],
            }
        ],
    )

    if message.stop_reason == "max_tokens":
        raise ClaudeExtractError(
            f"Claude response was truncated at {CLAUDE_MAX_TOKENS} tokens — "
            "recipe likely too long; increase CLAUDE_MAX_TOKENS"
        )

    body = "".join(block.text for block in message.content if block.type == "text").strip()
    raw = parse_claude_json_body(body)

    source_url = f"upload:{filename}" if filename else "upload:unknown"
    source_tag = "upload-pdf" if media_type in SUPPORTED_DOC_TYPES else "upload-image"

    return {**normalise_claude(raw, source_url), "source": source_tag}
