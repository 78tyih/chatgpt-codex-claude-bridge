<div align="center">

# 🌉 ChatGPT × Codex × Claude Bridge

**让网页版 ChatGPT 隔空指挥你电脑上的 Codex 和 Claude Code 干活。**

*ChatGPT 负责想，你的电脑负责动手。*

</div>

---

## 这是什么？

平时这三个 AI 各自关在自己的盒子里：

| AI | 强项 | 短板 |
|---|---|---|
| **ChatGPT**（网页版） | 规划、调研、拆需求 | 在云端，碰不到你的电脑、跑不了你的代码 |
| **Claude Code**（本地） | 真改文件、真跑命令、执行落地 | 规划不如 ChatGPT |
| **Codex**（本地） | 真改文件、真跑命令、代码审查 | 规划不如 ChatGPT |

以前你得当**人肉中转**：在 ChatGPT 里问完方案，复制出来，再粘到终端里让本地 AI 执行。

**这个项目把中转环节自动化了**——ChatGPT 自己就能把活派到你电脑上，结果自动跑完回传到对话里。你全程只在 ChatGPT 里打字。

## 数据怎么流的

```
   你在 ChatGPT 里说一句话
        │
        ▼
   ChatGPT（云端 · 负责"想"）
        │  通过一条加密隧道（Cloudflare Tunnel）
        ▼
   你电脑上的一个小服务（这个 MCP 桥）
        │  分派任务
        ├──────────────┐
        ▼              ▼
  Claude Code        Codex
  （负责"执行"）     （负责"审查"）
        │              │
        └──────┬───────┘
               ▼
   真的改了你电脑上的文件 / 跑了命令
               │
               ▼
   结果原路返回，显示在 ChatGPT 对话里
```

**三个角色像一个小团队：** ChatGPT = 项目经理（想方案、派活）｜Claude Code = 干活的工程师｜Codex = 审查的同事。

## 它能干嘛（实例）

你在 ChatGPT 里打一句"帮我写个三步计划，再让 Codex 审一遍"，然后：

1. ChatGPT 把"写计划"派给本地 **Claude Code** → 真的在你硬盘上生成了文件；
2. 再把"审查"派给本地 **Codex** → Codex 真的读了文件、写下审查意见；
3. 结果回到 ChatGPT 对话里给你看。

全程你只在 ChatGPT 里打字，电脑那头自动完成。
</content>

---

## ⚠️ 安全警告（务必读完再用）

这座桥的两个执行工具运行时带了 **`--dangerously-bypass-approvals-and-sandbox`**（Codex）和 **`--dangerously-skip-permissions`**（Claude Code）。这意味着：

> **谁能连到这个端点，谁就能在你的电脑上跑任意命令、改任意文件。**

所以必须做到：

- 🔒 **绝不**把端点裸奔在公网。至少用 `BRIDGE_PATH_SECRET`（不可猜的密钥 URL），有条件再叠 `BRIDGE_TOKEN`。
- 🚫 **绝不**把你正在跑的服务地址分享给别人——那等于把你电脑的钥匙发出去。要分享请让对方**克隆本仓库、在自己电脑上各搭各的**。
- 📁 用 `BRIDGE_WORK_ROOT` 把可读写范围锁在一个目录里，别直接放任整个 `$HOME`。
- 🔐 `.env` 里有密钥，已被 `.gitignore` 排除——**永远不要提交它**。

这是个人效率工具，不是给多人用的生产服务。请自担风险。

## 工作原理（关键招数）

1. **ChatGPT 开发者模式**：ChatGPT 有个"开发者模式"，允许它连接外部 MCP 工具。这是入口钥匙。
2. **本地 MCP 桥**：`app/bridge_server.py`，基于 [FastMCP](https://github.com/modelcontextprotocol)。它听懂 ChatGPT 的指令，转头去调本地的 Codex / Claude Code 真身二进制。一套代码两用——`stdio` 给本地客户端，`--http` 给隧道。
3. **加密隧道**：用 [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) 把本地 server 安全暴露成 HTTPS，云端的 ChatGPT 不用你把电脑直接挂公网就能够到。
4. **认证靠密钥 URL**：ChatGPT Plus 开发者模式的 connector 只支持"无验证 / OAuth"，发不了自定义请求头——所以 Bearer Token 它用不了。改用**密钥路径**（capability URL）：端点从 `/mcp` 改成 `/mcp/<不可猜的hex密钥>`，裸访问 `/mcp` 直接 404。

## 暴露的工具

| 工具 | 作用 |
|---|---|
| `run_codex` | 把任务交给本地 Codex 跑（执行 / 审查） |
| `run_claude_code` | 把任务交给本地 Claude Code 跑（执行落地） |
| `read_file` | 读 `BRIDGE_WORK_ROOT` 内的文件 |
| `write_file` | 写文件到 `BRIDGE_WORK_ROOT` 内 |
| `list_dir` | 列目录，供规划端探索结构 |

## 快速开始

**前提**：本机已装好 Codex CLI 和 / 或 Claude Code，能在终端跑通；有 [Cloudflare 账号](https://dash.cloudflare.com)。

```bash
# 1) 克隆 + 装依赖
git clone https://github.com/<你的用户名>/chatgpt-codex-claude-bridge.git
cd chatgpt-codex-claude-bridge
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) 配置：生成密钥，填好真身二进制路径
cp .env.example .env
python -c "import secrets;print('BRIDGE_PATH_SECRET='+secrets.token_hex(24))"   # 填进 .env
# 编辑 .env：CODEX_BIN / CLAUDE_BIN 填二进制真身的绝对路径（用 `which codex` 找，
# 但注意 shell 里的 codex/claude 常是带音效的函数包装，要找真身，如 ~/.local/bin/codex）

# 3) 起 server（HTTP 模式，给隧道用）
set -a; source .env; set +a
python -m app.bridge_server --http      # 监听 127.0.0.1:8000

# 4) 起隧道（另开一个终端）
cloudflared tunnel --protocol http2 --url http://localhost:8000
# 从输出里拿到 https://xxx.trycloudflare.com 地址

# 5) 在 ChatGPT 里加 connector
#    URL = https://xxx.trycloudflare.com/mcp/<你的 BRIDGE_PATH_SECRET>
#    Settings → Connectors → 开 Developer Mode → 添加
```

## 踩坑速查（都是真踩过的）

| 现象 | 原因 / 解法 |
|---|---|
| `run_codex` 报 `exit=-6` + dyld `libllhttp.x.dylib not loaded` | Homebrew 升级把 node 的 llhttp 依赖拽断了。`brew reinstall node` 重新链接即可。`run_claude_code` 正常但 `run_codex` 挂 → 大概率是 node 运行时坏了（Codex 依赖 node）。 |
| ChatGPT 声称"被安全检查拦截"但其实没真调 | 它没真发工具调用，自己脑补了借口。措辞**强制点名工具**（"现在必须实际调用 run_codex"）+ 要求**原样回贴返回**，堵住编借口空间。 |
| 隧道过夜失活，报 `quic: timeout` | cloudflared quick tunnel 默认走 QUIC/UDP。**必须加 `--protocol http2`**。 |
| ChatGPT 访问端点 404 | 密钥路径里若含 `_` / `-` 等特殊字符会被 URL 规范化吞掉。`BRIDGE_PATH_SECRET` **必须用纯 hex**（`secrets.token_hex`）。 |
| 调本地 codex/claude 没反应 | shell 里的 `codex` / `claude` 常是带审批音效的函数包装，非交互 shell 调不动。`.env` 里的 `CODEX_BIN` / `CLAUDE_BIN` 要指向**真身二进制**。 |
| trycloudflare 地址重启就变 | quick tunnel 是临时的。要固定地址，配 **命名隧道**（[Cloudflare Tunnel 文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)）绑你自己的域名。 |

## 环境

- Python 3.10+
- `mcp[cli]` + `uvicorn`（见 `requirements.txt`）
- Codex CLI 和 / 或 Claude Code（本机已能跑通）
- cloudflared

## License

MIT
