# 依赖清单

Python 包见 [`requirements.txt`](requirements.txt)；本机路径类配置见 [`kit.env.example`](kit.env.example)（复制为 `kit.env` 后填写）。
下面是外部程序。**必需**的缺了主流程跑不起来；**可选**的缺了只影响所列功能。

## 必需

| 程序 | 版本 | 用途 | 不装时 |
|---|---|---|---|
| Unity Editor | **2022.3.22f1**（VRChat 现行要求） | 工程编辑、批处理构建、NDMF 预处理；`unity_run.sh` / `unity_csc.sh` / 审查自测的 mono/mcs 都从它来 | 无法打开或构建任何工程 |
| VRChat Avatars SDK | **3.10.4**（`com.vrchat.avatars` / `com.vrchat.base`） | 头像构建与上传 | 同上 |
| Modular Avatar / NDMF | **1.18.1** / **1.14.3** | 非破坏式装配 | 装配、菜单相关工具与 SOP 不适用 |
| Avatar Optimizer (AAO) | **1.9.16** | 优化 | 优化相关工具（FitAAO 等）不可用 |
| lilToon | **2.3.4** | 着色器 | 配色/材质相关工具不可用 |
| Python | ≥ 3.10 | `开发工具/通用工具/` 下的大部分脚本 | 绝大多数工具不可用 |
| Node.js | ≥ 18；**≥ 22.15** 才能读 DSH 会话（用到 `zlib.zstdDecompressSync`） | 钩子（`.claude/hooks/*.js`）、`dsh_task.js`、`agy_mcp_server.js` | 钩子与派工脚本不可用 |
| git | 任意近版 | 工作区版本管理、`ws_git.py`、`log_step.py --commit`、pre-commit 闸口 | 施工记录提交与闸口不可用 |
| pgrep（procps） | — | 查活的 Unity / DSH 进程，防同工程双开与误删锁 | `unity_run.sh`、`unity_recover.sh`、`baseline_recheck.sh` 不可用 |
| flock（util-linux） | — | 批处理 Unity 全机串行锁 | `unity_run.sh --batch` 不可用 |

其余 VPM 包（Avatars 3.0 Manager、GoGoLoco、Gesture Manager、VRCFury、Light Limit Changer 等）的版本与冻结理由见 [`开发工具/_工具链基准.md`](开发工具/_工具链基准.md)，接新单时照抄那一页。

## 可选

| 程序 | 用途 | 不装时 |
|---|---|---|
| Blender 5.2 ＋ Blender MCP 扩展（`blender-mcp` 命令） | 改模、形态键测量（`bl_*.py` 在 Blender 内置 Python 里跑）、Claude 经 MCP 操作 Blender | 改模与形态键类工具不可用，`.mcp.example.json` 里的 Blender 项需删掉 |
| uv / uvx | 起 UnityMCP 服务器（`uvx --from mcpforunityserver==10.1.2 mcp-for-unity`） | Claude 不能经 MCP 驱动 Unity 编辑器，只能走批处理 |
| systemd（`systemd-run --user`） | 给 Unity 进程设 MemoryMax，超限只杀 Unity | `unity_run.sh` 自动退回无内存上限的直接启动 |
| zstd | 手工解 DSH 会话日志（`session.jsonl.zstd`）排障 | 只影响手工排障；脚本本身用 Node 内置 zstd |
| 7z（p7zip） | 解厂商素材包、加密压缩包 | 素材包需手工解压 |
| ComfyUI | `comfy_redraw.py` 对定妆照做二次创作改绘 | 二次创作改绘不可用 |
| CJK 字体（如 Noto Sans CJK） | 标注图写中文（`cjk_font.py`） | 带中文标注的出图会报错 |

## 可选编排层（多代理执行与第三方证伪）

完整保留、全部可选。不装时由 Claude Code 主会话自己执行，SOP 中「派 DSH / 派 Codex / 送 agy 证伪」的步骤改为手动或跳过。

| 程序 | 用途 | 不装时 |
|---|---|---|
| DSH（DeepSeek 执行代理，`@deepseek-ai/dsh`） | `dsh_task.js` 把执行活派给 DeepSeek 模型，自动记施工记录并提交 | `dsh_task.js --engine dsh` 不可用；`dsh_balance.py` / `dsh_usage.js` 无意义 |
| Codex CLI | `dsh_task.js --engine codex`（或 auto 在高峰时段）改派 Codex | 只能走 DSH 或手动执行 |
| agy（Google Antigravity，含 `agy-task.py`） | `agy_panel.py` 多模型交叉评审、`agy_mcp_server.js` 的 `agy_review` / `agy_ask` 工具 | 第三方证伪关口需改用其它评审方式；`.mcp.example.json` 里的 agy 项需删掉 |
