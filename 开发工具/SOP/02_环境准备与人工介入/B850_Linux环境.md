> ← [02 · 环境准备与人工介入](../02_环境准备与人工介入.md)

# 本机(Linux)（Ubuntu）本机环境

这页解决的问题：**在 本机(Linux) 上开 Unity / Blender、派 DSH / agy 时，东西在哪、命令怎么写、Linux 特有的坑是什么**。
2026-09-17 从 旧Windows机（Windows）迁来；SOP 里残留的 Windows 写法以本页为准。

## 路径

具体位置全由仓库根 `kit.env` 配置（样例 `kit.env.example`，环境变量优先），下表只写变量名与目录约定。

| 内容 | 位置 |
|---|---|
| 工作区（进行中的工程、开发工具） | `$VRC_WS/`（即 `<工作区>`；放 NVMe 等快盘，Unity 导入吃 IO） |
| 客户素材包 | `<客户素材目录>/COMM-<订单号>_<客户名>_素材/`（若只有一份，自己安排冷备） |
| 权威存档 / 交付总包 | `$ARCHIVE_ROOT/{个人存档,交付文件}/`（本机盘或网络盘都行，脚本与文档只认这个变量） |
| 素材库（可选） | `$VRC_ASSET_ROOT/<商品名>-<商品号>/`（每商品一目录；目录名可能是 NFD，按商品号通配） |
| VCC 设置与社区源（ALCOM / vrc-get 共用） | `~/.local/share/VRChatCreatorCompanion/` |
| 凭据（DeepSeek / Codex 等） | 放在 DSH / Codex 各自的凭据位置，权限 600，**别进仓库** |

迁机时各工程根目录剥掉 `Library/ Logs/ Temp/ obj/ .vs/ *.csproj *.sln`，首开会重建。

## 程序与启动

| 程序 | 位置 / 命令 | 备注 |
|---|---|---|
| Unity 2022.3.22f1 | `AVATARAUDIT_SUPPRESS_DIALOGS=1 DISPLAY=$DISPLAY_FALLBACK $UNITY_EDITOR_ROOT/2022.3.22f1/Editor/Unity -projectPath "<工程>"`（平时走 `unity_run.sh`） | 依赖本机编译的 `/usr/local/lib/libxml2.so.2`，**别删**；带 Windows(Mono)/Android/iOS 构建模块 |
| Unity Hub CLI | 加 `--ozone-platform=headless` 并去掉 `DISPLAY` | 否则被 GTK 全局菜单模块弄崩（已设 `UBUNTU_MENUPROXY=0`） |
| Blender 5.2.0 LTS | `blender`（PATH 里） | MCP 插件 `bl_ext.user_default.mcp` 自启，监听 **9876**；偏好里必须开「在线访问」 |
| Blender 无头 + MCP | `blender --background --command blender_mcp` | **别加 `--factory-startup`**（会跳过用户扩展，报 `Unrecognized command`）；用完要关，否则占着 9876，GUI 版的 MCP 起不来 |
| ALCOM / vrc-get | `alcom`、`vrc-get`（PATH 里） | 建工程见 [建工程与首轮编译](建工程与首轮编译.md) |
| DSH（改模用） | `dsh-vrc`（0.1.2-rc.1，`$DSH_BIN`，家目录 `$DSH_HOME`，缺省 `~/.dsh`） | 派工一律走 `开发工具/通用工具/dsh_task.js`；**别用别处装的 `dsh`**（版本与家目录都可能不同） |
| agy | `agy`（1.2.4，先登录）、`$AGY_TASK`（agy-task.py） | 可用模型名以 `agy models` 为准，版本升级会下线旧名 |
| 7-Zip | `/usr/bin/7z` | 迁机前内存只有 14 GB（现为 30 GB，并发上限见 [内存预算与并发](B850_Linux环境/内存预算与并发.md)）：LZMA2 每线程约 500 MB，线程数别超过 `-mmt=6` |

## MCP 接线

工作区 `.mcp.json`：**UnityMCP**（uvx `mcpforunityserver==10.1.2`，stdio）、**agy**（`agy_mcp_server.js`）、**Blender**（blender-mcp 1.0.2）。
DSH 侧同样三路，写在 `$DSH_HOME/cordis.patch.yml`。

- **Unity MCP 只在图形界面下起 6400 桥**，批处理模式不起。`MCPForUnity.UseHttpTransport=0` 已写进 `~/.local/share/unity3d/prefs`，冷启动自动连。
- **Unity 每次启动都会改写客户端配置**：Codex / VS Code 给 unityMCP 加 `--offline`，`~/.claude.json` 给工程目录加项目级 UnityMCP。
  Claude Desktop 在运行时会用内存里的旧配置写回；要改它的配置得先**完全退出**应用。

## Linux 编辑器特有的坑

> → [内存预算与并发](B850_Linux环境/内存预算与并发.md) —— Claude 起的 Unity/Blender/DSH 同在一个 cgroup，OOM 一次全死（09-22）；available <8 GB 不再起新活、DSH ≤4、两台编辑器开着不跑批处理导入。

**⓪ 起 Unity 与崩溃恢复一律走 `unity_run.sh` / `unity_recover.sh`**（内存上限、批处理串行、不许同工程另起）→ [内存预算与并发](B850_Linux环境/内存预算与并发.md)。
**① 一律 `-force-vulkan`（作者 09-22 拍板；改回 OpenGL 先问）** → [图形 API 与原生崩溃](B850_Linux环境/图形API与原生崩溃.md)：
OpenGL 走核显，lilToon 不透明材质整片不画（素体透明）。代价：Vulkan 下构建会间歇原生崩溃（交换链重建崩在 NVIDIA 驱动）——**构建前先存盘，崩了删 `Temp/UnityLockfile` 重开**。
> → [改编辑器脚本先离线编译](B850_Linux环境/改编辑器脚本先离线编译.md) —— 编译不过会弹 `Enter Safe Mode?` 模态框卡死编辑器、只能叫人来点；改完 `Assets/Editor/*.cs` 先跑 `开发工具/通用工具/unity_csc.sh <工程根>`（复用工程自己的 `.rsp`，手搓 `-r` 必踩 CS0433/CS0518）。

**Play 会改工程设置，提交前先看 `git diff ProjectSettings/`**（2026-09-18 两次误提交）：进 Play 时 AAO/SDK 把 `legacyClampBlendShapeWeights` 置 1、退出后回 0；Unity 还会翻 iOS 图形 API 的 `m_Automatic`。这些是副作用不是改动 —— 会话结束后 `git checkout <基线提交> -- <工程>/ProjectSettings/ProjectSettings.asset` 还原，或提交时只列要提交的路径。
**② 本机没有 VRChat 客户端：Build & Test 不可用。** 上传可用；要实测就私密上传后在客户端里看。

**③ 退出 Unity 用 MCP 执行菜单 `File/Exit`**，返回「Could not connect to Unity」是它已经退了，属正常。别 `kill`：会残留 `Temp/UnityLockfile` 和 10 MB 的 `mono_crash.*.blob`，**下次打开同一工程会静默秒退**（日志里只有 `Server::Kill`）——确认没有 Unity 进程后删掉锁文件即可。
  ⚠ **自动模式（auto mode）下这条会被权限分类器拒**（09-22：`File/Exit` 与 `EditorApplication.Exit` 都被拒）。要换工程时别硬绕：另开一个 Unity 实例（先看 `free -g`，闲置实例约 5 GB），MCP 用 `set_active_instance <工程名>@<哈希>`（哈希见 `~/.unity-mcp/unity-mcp-status-*.json`）路由，DSH 任务书第一条写明「先 set_active_instance」；闲置实例留给用户关。
> 退 Play 后再 `File/Exit`，可能弹「是否保存场景」模态框（2026-09-19 工程D：01:49 已保存、之后进出 Play 又变脏），框在用户桌面上、MCP 全部超时、CPU 0%。**`File/Exit` 前先用 `execute_code` 读 `scene.isDirty`**：脏且不是自己要的改动 → 先问用户（保存 / 不保存），别直接退；卡住时用 `DISPLAY=$DISPLAY_FALLBACK xwd -root` + `ffmpeg` 转 png 看屏。09-19 工程C又犯一次（没先读 isDirty 就 File/Exit）：本机没有 xdotool，点不了框，只能问用户后按 PID 杀。

**④ 编辑器语言**写在 EditorPrefs `Editor.kEditorLocale`（ChineseSimplified）。

**⑤ 首开验收的判据**：拿旧机器的 `*.csproj` 名单逐个对 `Library/ScriptAssemblies/*.dll`，不看日志。
2026-09-17 三个工程首开：批处理导入 5–9 分钟/个，0 个 `error CS`。

## 2026-09-18 连通性自检（复查时照这个跑）

| 项 | 做法 | 结果 |
|---|---|---|
| DSH 文本 | `dsh_task.js --task "只回复 DSH-OK"` | ✓ 3 s，deepseek-flash |
| DSH 读图 | `--model vision --images 7个圆点.png` 问数量 | ✓ 答 7，read_image 1/1 |
| agy CLI | `agy-task.py "只回复 AGY-OK"` | ✓（默认模型已改 `gemini-3.8-flash-low`） |
| agy 评审 | `agy_panel.py --fast --images`；再加自定义 `--schema` | ✓ 两种都正常 |
| DeepSeek 视觉直连 | `ds_vision.py --task --images` | ✓ |
| Unity MCP | 开图形界面 → 读 `mcpforunity://editor/state`、`manage_scene get_active` | ✓ `is_batch_mode=false` |
| Blender MCP | 无头起 → `get_objects_summary` | ✓ |

**杀进程 / 找进程 / 等进程的三个坑**（`pkill -f` 杀掉自己、`pgrep` 的 ERE `\|` 不是或、`read -t < /dev/zero` 不等待）
另开一页：[进程与等待](B850_Linux环境/进程与等待.md)。**起 Unity 前先 `pgrep -x Unity`，看到 lockfile 别删。**

> → [写脚本的六个坑](B850_Linux环境/写脚本的坑.md) —— `set -e` 下别写 `[ ] && `；`pipefail` 下命令替换里的 grep 要加 `|| true`；列 zip 成员别用 `$NF`（路径含空格）；dry-run 的 mkdir 也要受保护（判据：跑完 git status 不变）；`free` 表头本地化；只读参照与导出目标分两个参数。
> → [Blender 脚本的坑](B850_Linux环境/Blender脚本的坑.md) —— 5.2 的 `Bone` 无 `roll`、轴在父骨空间；无头 EEVEE 告警是假警报；mathutils 是 float32、BVH 单位是米、穿透用 overlap 判。

> **症状**：命令返回 144、没有任何输出，且随后的 `cd` 像没执行过（shell 换了一个）。

> **同一天还栽了等待循环那一半（09-20，代价约 1 小时）**：派完 DSH 用 `until ! pgrep -f dsh_task.js; do sleep 20; done` 等它收工 —— 这条等待命令自己的命令行就含 `dsh_task.js`，于是 `pgrep` 永远数得到它自己，DSH 其实 512 秒就跑完了，我却一直以为"还在跑"，中间还发了两次"仍在运行"的判断。
> **可查问句**：我这条等待命令要等的那个串，是不是也出现在这条等待命令自己里？
> **正确写法**：等 DSH／长命令一律靠 `run_in_background`（完成即通知）；真要轮询就等**产物**不等进程（`until [ -f 出参文件 ]; do sleep 10; done`），或者 `pgrep -x`／按 PID 等。

> 被 kill 的 Unity 会在 `~/.unity-mcp/` 留下 `unity-mcp-status-<哈希>.json`；之后别的工程进 Play（域重载、心跳暂断）时，MCP 会把请求路由到这个死实例（报「instance not found, available: <旧工程>」）。**kill 过 Unity 就删掉对应的状态文件**（`ls -t ~/.unity-mcp/` 看，哈希与当前工程不符、时间是被 kill 那刻的就是）。2026-09-19 工程B会话连撞两次。
