"""Anthropic API wrapper for Smelt."""

import os
import re

import anthropic


def complete(
    system: str,
    user: str,
    model: str = "claude-sonnet-4-5",
    max_tokens: int = 8192,
) -> str:
    """Send a prompt to the Anthropic API and return the text response.

    Args:
        system: System prompt text.
        user: User message text.
        model: Anthropic model ID.
        max_tokens: Maximum tokens in the response.

    Returns:
        Response text with markdown code fences stripped.

    Raises:
        anthropic.APIError: On API failure.
        ValueError: If ANTHROPIC_API_KEY is not set.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = message.content[0].text
    return _strip_code_fences(text)


def _strip_code_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences from LLM output."""
    text = text.strip()
    # Match optional language tag: ```python or ```
    pattern = r"^```[a-zA-Z]*\n(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text
