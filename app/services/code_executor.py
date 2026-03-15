"""Sandboxed code execution for interview coding questions."""
from __future__ import annotations

import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

BLOCKED_IMPORTS = {
    "os", "subprocess", "socket", "shutil", "ctypes", "signal",
    "multiprocessing", "threading", "http", "urllib", "requests",
    "pathlib", "io", "sys", "importlib",
}

IMPORT_GUARD = """
import builtins as _builtins

# Block dangerous imports
_original_import = _builtins.__import__
_BLOCKED = {blocked}
def _safe_import(name, *args, **kwargs):
    top = name.split(".")[0]
    if top in _BLOCKED:
        raise ImportError(f"Import of '{{top}}' is not allowed in this sandbox")
    return _original_import(name, *args, **kwargs)
_builtins.__import__ = _safe_import

# Block dangerous builtins
_builtins.open = None
_builtins.exec = None
_builtins.eval = None
_builtins.compile = None
_builtins.__import__ = _safe_import
_builtins.breakpoint = None
_builtins.exit = None
_builtins.quit = None
"""

RESOURCE_LIMITS = """
import resource
for _res, _val in [
    (resource.RLIMIT_CPU, ({cpu}, {cpu})),
    (resource.RLIMIT_FSIZE, (1048576, 1048576)),
    (resource.RLIMIT_AS, ({mem}, {mem})),
]:
    try:
        resource.setrlimit(_res, _val)
    except (ValueError, OSError):
        pass
try:
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
except (ValueError, AttributeError, OSError):
    pass
"""


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool


async def execute_code(code: str, stdin: str = "") -> ExecutionResult:
    """Execute Python code in a sandboxed subprocess."""
    tmpdir = tempfile.mkdtemp(prefix="interview_exec_")
    script_path = Path(tmpdir) / "solution.py"

    guard = IMPORT_GUARD.format(blocked=BLOCKED_IMPORTS)
    limits = RESOURCE_LIMITS.format(
        mem=settings.code_memory_mb * 1024 * 1024,
        cpu=settings.code_timeout,
    )
    full_code = guard + "\n" + limits + "\n" + code
    script_path.write_text(full_code)

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", str(script_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmpdir,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin.encode() if stdin else None),
                timeout=settings.code_timeout,
            )
            return ExecutionResult(
                stdout=stdout.decode(errors="replace").strip(),
                stderr=stderr.decode(errors="replace").strip(),
                return_code=proc.returncode or 0,
                timed_out=False,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ExecutionResult(
                stdout="",
                stderr="Execution timed out",
                return_code=-1,
                timed_out=True,
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


async def run_test_case(
    code: str, test_input: str, expected_output: str
) -> dict:
    """Run code with a test case and check if output matches."""
    result = await execute_code(code, stdin=test_input)

    actual = result.stdout.strip()
    expected = expected_output.strip()
    passed = actual == expected

    return {
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
    }
