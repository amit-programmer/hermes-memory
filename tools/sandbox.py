"""
tools/sandbox.py - Isolated Code Sandbox
Executes Python or JavaScript/Node code in a subprocess with timeouts to test code before replying.
Rule: "Code dene se pehle sandbox me test karna hi hai"
"""
import asyncio
import os
import subprocess
import sys
import tempfile
import time
from typing import Any


class CodeSandbox:
    """Safe execution sandbox for verifying code snippets before sending to user."""

    def __init__(self, default_timeout: int = 10):
        self.default_timeout = default_timeout

    async def run_python(self, code: str, timeout: int = 10) -> dict[str, Any]:
        """Execute Python code in an isolated subprocess with timeout."""
        start = time.time()
        timeout = timeout or self.default_timeout

        # Write code to a secure temporary file
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run using the active Python executable
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                duration = round(time.time() - start, 3)

                stdout_str = stdout_data.decode("utf-8", errors="replace").strip()
                stderr_str = stderr_data.decode("utf-8", errors="replace").strip()

                if proc.returncode == 0:
                    return {
                        "success": True,
                        "output": stdout_str or "(No output)",
                        "error": "",
                        "exit_code": 0,
                        "duration_sec": duration,
                    }
                else:
                    return {
                        "success": False,
                        "output": stdout_str,
                        "error": stderr_str or f"Process exited with code {proc.returncode}",
                        "exit_code": proc.returncode,
                        "duration_sec": duration,
                    }

            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                return {
                    "success": False,
                    "output": "",
                    "error": f"Execution timed out after {timeout} seconds",
                    "exit_code": -1,
                    "duration_sec": timeout,
                }

        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Sandbox launch error: {str(e)}",
                "exit_code": -1,
                "duration_sec": round(time.time() - start, 3),
            }
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    async def run_javascript(self, code: str, timeout: int = 10) -> dict[str, Any]:
        """Execute Node.js code in a subprocess if Node is installed."""
        start = time.time()
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "node",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                duration = round(time.time() - start, 3)
                return {
                    "success": proc.returncode == 0,
                    "output": stdout_data.decode("utf-8", errors="replace").strip(),
                    "error": stderr_data.decode("utf-8", errors="replace").strip(),
                    "exit_code": proc.returncode,
                    "duration_sec": duration,
                }
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                return {
                    "success": False,
                    "output": "",
                    "error": f"Timed out after {timeout} seconds",
                    "exit_code": -1,
                    "duration_sec": timeout,
                }
        except FileNotFoundError:
            return {
                "success": False,
                "output": "",
                "error": "Node.js is not installed on this system",
                "exit_code": -1,
                "duration_sec": 0,
            }
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass


# Default singleton instance
sandbox = CodeSandbox()
