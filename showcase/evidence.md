# Evidence — chatgpt-codex-claude-bridge

Updated: 2026-10-05

## Observed（实查）

| 声明 | 证据 |
|---|---|
| 五个 MCP 工具（run_codex / run_claude_code / read_file / write_file / list_dir） | README「暴露的工具」表格 |
| 三角色数据流（ChatGPT 想本地执行） | README「这是什么」+「数据怎么流的」ASCII 图 |
| 四个关键招数（开发者模式 / FastMCP 桥 / Tunnel / 密钥路径） | README「工作原理（关键招数）」1–4 条 |
| 认证用 capability URL 而非 Bearer | README 原因说明：开发者模式 connector 只支持无验证/OAuth，发不了自定义请求头 |
| 六条踩坑及解法 | README「踩坑速查（都是真踩过的）」表格（exit=-6 / 脑补借口 / quic timeout / 404 / 函数包装 / quick tunnel 临时） |
| 危险旗标与四条安全规则 | README「⚠️ 安全警告」节原文 |
| LICENSE MIT | 仓库根 LICENSE |

## Inferred（推断，附复核方式）

| 声明 | 复核方式 |
|---|---|
| 「ChatGPT 真的能隔空派活」端到端可用 | README 实例自述 + app/bridge_server.py 存在；本展示包未现场重放一次完整派活，复验方式=按 QUICK START 五步跑一轮 |
| 一套代码 stdio/--http 两用 | README 自述；复验=读 bridge_server.py 的模式分支 |

## Unknown

- 命名隧道（固定域名）配置的实际效果（README 指向 Cloudflare 文档，未含本仓配置样例）
