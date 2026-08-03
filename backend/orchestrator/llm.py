import json, os, subprocess
from config import CLAUDE_BIN, DISPATCH_MODEL, POLISH_MODEL

def call_claude(prompt: str, system_prompt: str | None = None,
                model: str = DISPATCH_MODEL, timeout: float = 60) -> str:
    full = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    cmd = [CLAUDE_BIN, "-p", full, "--output-format", "json",
           "--dangerously-skip-permissions", "--model", model]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude failed (rc={result.returncode}): "
            f"stderr={result.stderr.strip()!r} stdout={result.stdout.strip()!r}"
        )
    return json.loads(result.stdout)["result"].strip()
