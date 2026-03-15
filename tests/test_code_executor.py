"""Test the sandboxed code executor."""
import asyncio

import pytest

from app.services.code_executor import execute_code, run_test_case


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_simple_execution():
    result = _run(execute_code("print('hello')"))
    assert result.stdout == "hello"
    assert result.return_code == 0
    assert not result.timed_out


def test_syntax_error():
    result = _run(execute_code("def f("))
    assert result.return_code != 0
    assert "SyntaxError" in result.stderr


def test_blocked_import():
    result = _run(execute_code("import os"))
    assert result.return_code != 0
    assert "not allowed" in result.stderr


def test_blocked_subprocess():
    result = _run(execute_code("import subprocess"))
    assert result.return_code != 0


def test_allowed_import():
    result = _run(execute_code("import math\nprint(math.pi)"))
    assert result.return_code == 0
    assert "3.14" in result.stdout


def test_timeout():
    result = _run(execute_code("while True: pass"))
    assert result.timed_out or result.return_code != 0


def test_run_test_case_pass():
    code = "x = input()\nprint(int(x) * 2)"
    result = _run(run_test_case(code, "5", "10"))
    assert result["passed"] is True


def test_run_test_case_fail():
    code = "x = input()\nprint(int(x) + 1)"
    result = _run(run_test_case(code, "5", "10"))
    assert result["passed"] is False
    assert result["actual"] == "6"
