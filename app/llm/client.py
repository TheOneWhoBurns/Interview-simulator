from __future__ import annotations

import asyncio
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


async def _run_claude_once(
    cmd: list[str],
    timeout: int,
) -> str:
    """Run a single claude CLI invocation (no retries)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"claude CLI timed out after {timeout}s")

    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {stderr.decode().strip()}")

    raw = stdout.decode().strip()
    data = json.loads(raw)
    return data.get("result", raw)


def _build_cmd(
    prompt: str,
    *,
    system: str = "",
    model: str | None = None,
    allowed_tools: list[str] | None = None,
) -> list[str]:
    model = model or settings.default_model
    cmd: list[str] = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--dangerously-skip-permissions",
    ]
    if system:
        cmd.extend(["--system-prompt", system])
    if allowed_tools:
        cmd.extend(["--allowedTools", ",".join(allowed_tools)])
    return cmd


async def call_claude(
    prompt: str,
    *,
    system: str = "",
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    timeout: int = 120,
) -> str:
    """Call the claude CLI and return the response text."""
    cmd = _build_cmd(prompt, system=system, model=model, allowed_tools=allowed_tools)

    for attempt in range(MAX_RETRIES + 1):
        try:
            return await _run_claude_once(cmd, timeout)
        except (RuntimeError, TimeoutError) as exc:
            logger.error("claude CLI error (attempt %d): %s", attempt, exc)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1)
                continue
            raise

    raise RuntimeError("Exhausted retries calling claude CLI")


async def call_claude_json(
    prompt: str,
    *,
    system: str = "",
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    timeout: int = 120,
) -> dict:
    """Call claude CLI and parse the response as JSON.

    Retries at this level only (no nested retries from call_claude).
    """
    original_prompt = prompt
    cmd = _build_cmd(prompt, system=system, model=model, allowed_tools=allowed_tools)

    for attempt in range(MAX_RETRIES + 1):
        try:
            text = await _run_claude_once(cmd, timeout)
        except (RuntimeError, TimeoutError) as exc:
            logger.error("claude CLI error (attempt %d): %s", attempt, exc)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1)
                continue
            raise

        try:
            return _extract_json(text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "JSON parse failed (attempt %d): %s — raw: %.200s",
                attempt, exc, text,
            )
            if attempt < MAX_RETRIES:
                retry_prompt = (
                    f"{original_prompt}\n\nIMPORTANT: Your previous response was not valid JSON. "
                    "Return ONLY a JSON object, no markdown fences or extra text."
                )
                cmd = _build_cmd(retry_prompt, system=system, model=model, allowed_tools=allowed_tools)
                continue
            raise

    raise RuntimeError("Exhausted retries parsing JSON from claude CLI")


def _extract_json(text: str) -> dict:
    """Extract a JSON object from text that might contain markdown fences."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object, got {type(result).__name__}")
    return result
