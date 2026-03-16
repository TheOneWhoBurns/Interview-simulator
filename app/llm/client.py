from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
DEFAULT_TIMEOUT = 300  # 5 minutes — claude CLI can be slow


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
    stream: bool = False,
) -> list[str]:
    model = model or settings.default_model
    fmt = "stream-json" if stream else "json"
    cmd: list[str] = [
        "claude", "-p", prompt,
        "--output-format", fmt,
        "--model", model,
        "--dangerously-skip-permissions",
    ]
    if stream:
        cmd.append("--verbose")
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
    timeout: int = DEFAULT_TIMEOUT,
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
    timeout: int = DEFAULT_TIMEOUT,
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


async def call_claude_json_streaming(
    prompt: str,
    *,
    system: str = "",
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> AsyncIterator[tuple[str, str]]:
    """Call claude CLI with streaming, yielding (event_type, message) tuples.

    Yields:
        ("status", "human-readable status message")
        ("thinking", "what the model is thinking about")
        ("result", "final JSON string")
        ("error", "error message")
    """
    cmd = _build_cmd(
        prompt, system=system, model=model,
        allowed_tools=allowed_tools, stream=True,
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    result_text = None
    thinking_sent = False

    try:
        while True:
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                yield ("error", f"Timed out after {timeout}s")
                return

            if not line:
                break

            line = line.decode().strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")

            if etype == "system" and event.get("subtype") == "init":
                yield ("status", "Connected to Claude...")

            elif etype == "assistant":
                msg = event.get("message", {})
                content_blocks = msg.get("content", [])
                for block in content_blocks:
                    btype = block.get("type", "")
                    if btype == "thinking" and not thinking_sent:
                        thinking = block.get("thinking", "")
                        # Send first ~120 chars of thinking as a peek
                        snippet = thinking[:120].replace("\n", " ").strip()
                        if snippet:
                            yield ("thinking", snippet + ("..." if len(thinking) > 120 else ""))
                            thinking_sent = True
                    elif btype == "tool_use":
                        tool = block.get("name", "unknown")
                        yield ("status", f"Using tool: {tool}")
                    elif btype == "text":
                        text = block.get("text", "")
                        if text and len(text) > 10:
                            snippet = text[:80].replace("\n", " ").strip()
                            yield ("status", f"Writing: {snippet}...")

            elif etype == "result":
                result_text = event.get("result", "")
                if event.get("is_error"):
                    yield ("error", result_text or "Claude CLI returned an error")
                    return

        await proc.wait()

        if proc.returncode != 0 and not result_text:
            stderr = await proc.stderr.read()
            yield ("error", f"CLI failed: {stderr.decode().strip()}")
            return

        if result_text is not None:
            try:
                parsed = _extract_json(result_text)
                yield ("result", json.dumps(parsed))
            except (json.JSONDecodeError, ValueError) as exc:
                yield ("error", f"Failed to parse response as JSON: {exc}")
        else:
            yield ("error", "No result received from Claude CLI")

    except Exception as exc:
        proc.kill()
        await proc.wait()
        yield ("error", str(exc))


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
