"""Text-to-speech using macOS say command with browser SpeechSynthesis fallback."""
from __future__ import annotations

import asyncio
import hashlib
import platform
from pathlib import Path

from app.config import settings

AUDIO_DIR = settings.data_dir / "audio"


async def text_to_speech(text: str, voice: str | None = None) -> Path | None:
    """Generate audio file using macOS say command.

    Returns path to the audio file, or None if TTS is not available
    (non-macOS). In that case, the frontend uses browser SpeechSynthesis.
    """
    if platform.system() != "Darwin":
        return None

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    voice = voice or settings.tts_voice

    # Cache by content + voice hash
    text_hash = hashlib.md5(f"{voice}:{text}".encode()).hexdigest()
    output_path = AUDIO_DIR / f"{text_hash}.aiff"

    if output_path.exists():
        return output_path

    cmd = ["say", "-v", voice, "-o", str(output_path), text]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    if proc.returncode != 0 or not output_path.exists():
        return None

    return output_path
