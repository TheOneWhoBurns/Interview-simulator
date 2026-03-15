from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.routes import interview, progress, research
from app.services.code_executor import execute_code
from app.services.tts import text_to_speech

app = FastAPI(title=settings.app_name)

# Routes
app.include_router(research.router)
app.include_router(interview.router)
app.include_router(progress.router)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ── Utility endpoints ───────────────────────────────────────────────────


class ExecuteRequest(BaseModel):
    code: str
    stdin: str = ""


@app.post("/api/execute")
async def run_code(req: ExecuteRequest):
    result = await execute_code(req.code, req.stdin)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "return_code": result.return_code,
        "timed_out": result.timed_out,
    }


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None


@app.post("/api/tts")
async def tts(req: TTSRequest):
    audio_path = await text_to_speech(req.text, req.voice)
    if audio_path and audio_path.exists():
        return FileResponse(audio_path, media_type="audio/aiff")
    return JSONResponse(
        {"fallback": "browser", "text": req.text},
        status_code=200,
    )


# ── Static files & SPA ──────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(static_dir / "index.html"))


# ── Startup ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    settings.ensure_dirs()


if __name__ == "__main__":
    import shutil
    import subprocess
    import sys
    import webbrowser
    import threading

    import uvicorn

    # ── Preflight checks ────────────────────────────────────────────────
    ok = True

    if not shutil.which("claude"):
        print("\x1b[31m[ERROR]\x1b[0m  claude CLI not found on PATH.")
        print("         Install: https://docs.anthropic.com/en/docs/claude-code")
        ok = False
    else:
        v = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True,
        )
        print(f"\x1b[32m[OK]\x1b[0m     claude CLI {v.stdout.strip()}")

    try:
        import fastapi, pydantic  # noqa: E401, F401
        print(f"\x1b[32m[OK]\x1b[0m     Python deps installed")
    except ImportError as e:
        print(f"\x1b[31m[ERROR]\x1b[0m  Missing dependency: {e.name}")
        print("         Run: pip3 install -r requirements.txt")
        ok = False

    if not ok:
        sys.exit(1)

    # ── Launch ───────────────────────────────────────────────────────────
    url = f"http://localhost:{settings.port}"
    print()
    print(f"\x1b[1m  Interview Simulator\x1b[0m")
    print(f"  \x1b[36m{url}\x1b[0m")
    print()

    # Open browser after a short delay so uvicorn is ready
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
