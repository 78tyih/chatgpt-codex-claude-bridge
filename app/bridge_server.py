"""ChatGPT(规划) → Codex(审查) / Claude Code(执行) 的 MCP 执行端 server。

ChatGPT 负责规划(Prompt/PRD/方案),通过 MCP 派活:
  run_codex        交给本地 Codex(偏审查)
  run_claude_code  交给本地 Claude Code(偏执行)

一套代码两用:
  python -m app.bridge_server            # stdio,给 Codex / Claude Code
  python -m app.bridge_server --http     # streamable-http,给 ChatGPT 隧道
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# 真身二进制:shell 里的 codex/claude 都是带 approval 音效的函数包装,非交互 shell 调不动。
CODEX_BIN = os.environ.get("CODEX_BIN", str(Path.home() / ".local/bin/codex"))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/opt/homebrew/bin/claude")
# 工作根:文件工具不允许越出此目录,防止规划端误读/误写无关路径。
WORK_ROOT = Path(os.environ.get("BRIDGE_WORK_ROOT", str(Path.home()))).resolve()
DEFAULT_TIMEOUT = int(os.environ.get("CODEX_TIMEOUT", "600"))

# Bearer Token 鉴权:设了 BRIDGE_TOKEN 就强制校验 Authorization 头,挡住陌生人。
# 留空则裸奔(仅限本地/受信网络调试)。http 模式下强烈建议设。
BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "").strip()

# 隧道域名每次重启会变。设了 BRIDGE_ALLOWED_HOSTS(逗号分隔)就用白名单;
# 没设则关掉 DNS rebinding 防护——此时访问控制靠随机隧道地址 + 后续鉴权。
_hosts = os.environ.get("BRIDGE_ALLOWED_HOSTS", "").strip()
if _hosts:
    _sec = TransportSecuritySettings(allowed_hosts=_hosts.split(","))
else:
    _sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# 密钥路径(capability URL):ChatGPT Plus 开发者模式只支持"无验证/OAuth",
# 不能发自定义头,故用不可猜的 URL 路径当凭据。设了 BRIDGE_PATH_SECRET 就把
# 端点从 /mcp 改成 /mcp/<secret>,陌生人访问 /mcp 得 404。
_path_secret = os.environ.get("BRIDGE_PATH_SECRET", "").strip()
_http_path = f"/mcp/{_path_secret}" if _path_secret else "/mcp"

mcp = FastMCP(
    "chatgpt-codex-bridge",
    transport_security=_sec,
    streamable_http_path=_http_path,
)


def _safe_path(rel: str) -> Path:
    """把相对路径锁进 WORK_ROOT,越界则报错。"""
    p = (WORK_ROOT / rel).resolve()
    if WORK_ROOT not in p.parents and p != WORK_ROOT:
        raise ValueError(f"path escapes work root: {rel}")
    return p


@mcp.tool()
def run_codex(task: str, cwd: str = ".", timeout: int = DEFAULT_TIMEOUT) -> str:
    """把执行类任务交给本地 Codex 跑(写代码/改文件/跑命令),返回最终结果文本。

    task: 给 Codex 的完整指令。cwd: 相对 WORK_ROOT 的工作目录。
    """
    try:
        workdir = _safe_path(cwd)
    except ValueError as e:
        return f"[bridge error] {e}"
    if not workdir.is_dir():
        return f"[bridge error] cwd not a directory: {workdir}"

    out_file = Path(tempfile.mktemp(suffix=".txt"))
    cmd = [
        CODEX_BIN, "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "-C", str(workdir),
        "-o", str(out_file),
        task,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return f"[bridge error] codex timed out after {timeout}s"
    except FileNotFoundError:
        return f"[bridge error] codex binary not found: {CODEX_BIN}"

    result = out_file.read_text().strip() if out_file.exists() else ""
    out_file.unlink(missing_ok=True)
    if result:
        return result
    # 没拿到 last-message:多半是额度/认证问题,把 stderr 关键行回传给规划端。
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
    return f"[codex no output, exit={proc.returncode}]\n" + "\n".join(tail)


@mcp.tool()
def run_claude_code(task: str, cwd: str = ".", timeout: int = DEFAULT_TIMEOUT) -> str:
    """把执行类任务交给本地 Claude Code 跑(写代码/改文件/跑命令),返回结果文本。

    与 run_codex 互补:Claude Code 偏执行落地。task: 完整指令;cwd: 相对 WORK_ROOT 的工作目录。
    """
    try:
        workdir = _safe_path(cwd)
    except ValueError as e:
        return f"[bridge error] {e}"
    if not workdir.is_dir():
        return f"[bridge error] cwd not a directory: {workdir}"

    cmd = [
        CLAUDE_BIN, "-p", task,
        "--dangerously-skip-permissions",
        "--output-format", "text",
        "--add-dir", str(workdir),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(workdir),
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return f"[bridge error] claude code timed out after {timeout}s"
    except FileNotFoundError:
        return f"[bridge error] claude binary not found: {CLAUDE_BIN}"

    result = (proc.stdout or "").strip()
    if result:
        return result
    tail = (proc.stderr or "").strip().splitlines()[-5:]
    return f"[claude code no output, exit={proc.returncode}]\n" + "\n".join(tail)


@mcp.tool()
def read_file(path: str, max_bytes: int = 100_000) -> str:
    """读 WORK_ROOT 内的文件内容,供规划端了解现状。"""
    try:
        p = _safe_path(path)
        data = p.read_text(errors="replace")[:max_bytes]
        return data if data else "[empty file]"
    except Exception as e:  # noqa: BLE001 — 错误优先继续跑
        return f"[bridge error] read failed: {e}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """写文件到 WORK_ROOT 内(覆盖)。规划端一般应让 run_codex 改文件,此工具用于小改。"""
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"[ok] wrote {len(content)} chars to {p}"
    except Exception as e:  # noqa: BLE001
        return f"[bridge error] write failed: {e}"


@mcp.tool()
def list_dir(path: str = ".") -> str:
    """列出 WORK_ROOT 内某目录的条目,供规划端探索结构。"""
    try:
        p = _safe_path(path)
        if not p.is_dir():
            return f"[bridge error] not a directory: {p}"
        items = sorted(
            f"{c.name}/" if c.is_dir() else c.name
            for c in p.iterdir()
        )
        return "\n".join(items) if items else "[empty dir]"
    except Exception as e:  # noqa: BLE001
        return f"[bridge error] list failed: {e}"


class _BearerAuth:
    """纯 ASGI 中间件:校验 Authorization: Bearer <token>。
    用纯 ASGI 而非 BaseHTTPMiddleware,避免破坏 MCP 的 SSE 流式响应。"""

    def __init__(self, app, token: str):
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        if headers.get(b"authorization") != self.expected:
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"unauthorized"})
            return
        await self.app(scope, receive, send)


def main() -> None:
    if "--http" in sys.argv:
        import uvicorn
        app = mcp.streamable_http_app()
        if BRIDGE_TOKEN:
            app = _BearerAuth(app, BRIDGE_TOKEN)
            print("[bridge] Bearer token auth ENABLED", file=sys.stderr)
        else:
            print("[bridge] WARNING: no BRIDGE_TOKEN — endpoint is UNAUTHENTICATED",
                  file=sys.stderr)
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
