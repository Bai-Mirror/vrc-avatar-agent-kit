> 🌐 English translation · [中文原文](../../../../开发工具/SOP/02_环境准备与人工介入/B850_Linux环境.md)

> ← [02 · Environment preparation and manual intervention](../02-environment-and-manual-intervention.md)

# This Machine (Linux) (Ubuntu) Local Environment

The problem this page solves: **when opening Unity / Blender and dispatching DSH / agy on this machine (Linux), where things are, how to write commands, and what the Linux-specific pitfalls are**.
Migrated on 2026-09-17 from the old Windows machine (Windows); for Windows-style instructions remaining in the SOP, this page prevails.

## Paths

All concrete locations are configured in `kit.env` at the repository root (sample `kit.env.example`; environment variables take precedence). The table below only gives variable names and directory conventions.

| Content | Location |
|---|---|
| Workspace (in-progress projects, dev tools) | `$VRC_WS/` (i.e. `<工作区>`; put it on a fast disk such as NVMe, Unity import is IO-heavy) |
| Client asset packages | `<客户素材目录>/COMM-<订单号>_<客户名>_素材/` (if it is the only copy, arrange a cold backup yourself) |
| Authoritative archive / delivery bundles | `$ARCHIVE_ROOT/{个人存档,交付文件}/` (local disk or network share both work; scripts and docs only refer to this variable) |
| Asset library (optional) | `$VRC_ASSET_ROOT/<商品名>-<商品号>/` (one directory per product; directory names may be NFD, glob by product ID) |
| VCC settings and community sources (shared by ALCOM / vrc-get) | `~/.local/share/VRChatCreatorCompanion/` |
| Credentials (DeepSeek / Codex, etc.) | Keep them in DSH's / Codex's own credential locations, mode 600, **never in the repository** |

During machine migration each project root was stripped of `Library/ Logs/ Temp/ obj/ .vs/ *.csproj *.sln`; they are rebuilt on first open.

## Programs and launching

| Program | Location / command | Notes |
|---|---|---|
| Unity 2022.3.22f1 | `AVATARAUDIT_SUPPRESS_DIALOGS=1 DISPLAY=$DISPLAY_FALLBACK $UNITY_EDITOR_ROOT/2022.3.22f1/Editor/Unity -projectPath "<工程>"` (normally via `unity_run.sh`) | Depends on the locally compiled `/usr/local/lib/libxml2.so.2`, **do not delete it**; includes Windows(Mono)/Android/iOS build modules |
| Unity Hub CLI | Add `--ozone-platform=headless` and remove `DISPLAY` | Otherwise it crashes due to the GTK global menu module (`UBUNTU_MENUPROXY=0` is already set) |
| Blender 5.2.0 LTS | `blender` (on PATH) | MCP add-on `bl_ext.user_default.mcp` auto-starts, listening on **9876**; “online access” must be enabled in preferences |
| Blender headless + MCP | `blender --background --command blender_mcp` | **Do not add `--factory-startup`** (it skips user extensions, reporting `Unrecognized command`); close it when done, otherwise it holds 9876 and the GUI version's MCP cannot start |
| ALCOM / vrc-get | `alcom`, `vrc-get` (on PATH) | For creating projects see [Project setup and first compile](project-setup-and-first-compile.md) |
| DSH (for model editing) | `dsh-vrc` (0.1.2-rc.1, `$DSH_BIN`, home directory `$DSH_HOME`, default `~/.dsh`) | Always dispatch via `开发工具/通用工具/dsh_task.js`; **do not use a `dsh` installed elsewhere** (its version and home directory may differ) |
| agy | `agy` (1.2.4, log in first), `$AGY_TASK` (agy-task.py) | Available model names per `agy models`; version upgrades retire old names |
| 7-Zip | `/usr/bin/7z` | Before the machine migration memory was only 14 GB (now 30 GB; concurrency limits in [Memory budget and concurrency](b850-linux-environment/memory-budget-and-concurrency.md)): LZMA2 takes about 500 MB per thread; do not exceed `-mmt=6` threads |

## MCP wiring

Workspace `.mcp.json`: **UnityMCP** (uvx `mcpforunityserver==10.1.2`, stdio), **agy** (`agy_mcp_server.js`), **Blender** (blender-mcp 1.0.2).
The DSH side has the same three, written in `$DSH_HOME/cordis.patch.yml`.

- **Unity MCP only starts the 6400 bridge under the graphical interface**; it does not start in batch mode. `MCPForUnity.UseHttpTransport=0` is already written to `~/.local/share/unity3d/prefs`, so it connects automatically on cold start.
- **Unity rewrites client configurations on every startup**: Codex / VS Code get `--offline` added for unityMCP, and `~/.claude.json` gets a project-level UnityMCP added for the project directory.
  Claude Desktop writes back its old in-memory configuration while running; to change its configuration you must first **fully quit** the app.

## Linux editor-specific pitfalls

> → [Memory budget and concurrency](b850-linux-environment/memory-budget-and-concurrency.md) — Unity/Blender/DSH started by Claude share one cgroup, and one OOM kills them all (09-22); with available <8 GB start no new work, DSH ≤4, no batch imports while two editors are open.

**⓪ Starting Unity and crash recovery always go through `unity_run.sh` / `unity_recover.sh`** (memory limits, serialized batch, no second instance on the same project) → [Memory budget and concurrency](b850-linux-environment/memory-budget-and-concurrency.md).
**① Always `-force-vulkan` (user decision 09-22; ask before switching back to OpenGL)** → [Graphics API and native crashes](b850-linux-environment/graphics-api-and-native-crashes.md):
OpenGL goes through the iGPU, and opaque lilToon materials do not draw at all (the base avatar is transparent). Cost: under Vulkan builds intermittently crash natively (swapchain recreation crashing in the NVIDIA driver) — **save before building; if it crashes, delete `Temp/UnityLockfile` and reopen**.
> → [Compile offline before editor scripts](b850-linux-environment/compile-offline-before-editor-scripts.md) — a failed compile pops an `Enter Safe Mode?` modal that freezes the editor and requires a human to click; after editing `Assets/Editor/*.cs`, first run `开发工具/通用工具/unity_csc.sh <工程根>` (reuses the project's own `.rsp`; hand-rolled `-r` certainly hits CS0433/CS0518).

**Play changes project settings; check `git diff ProjectSettings/` before committing** (two erroneous commits on 2026-09-18): entering Play, AAO/SDK set `legacyClampBlendShapeWeights` to 1, and back to 0 after exiting; Unity also flips `m_Automatic` of the iOS graphics API. These are side effects, not changes — after the session, restore with `git checkout <基线提交> -- <工程>/ProjectSettings/ProjectSettings.asset`, or list only the paths to commit when committing.
**② There is no VRChat client on this machine: Build & Test is unavailable.** Upload works; for real testing, upload privately and check in the client.

**③ Quit Unity by executing the menu `File/Exit` via MCP**; a “Could not connect to Unity” return means it has already quit, which is normal. Do not `kill`: it leaves `Temp/UnityLockfile` and a 10 MB `mono_crash.*.blob`, and **the next time the same project is opened it silently exits immediately** (the log only has `Server::Kill`) — after confirming no Unity process exists, just delete the lock file.
  ⚠ **In auto mode this is rejected by the permission classifier** (09-22: both `File/Exit` and `EditorApplication.Exit` were rejected). When you need to switch projects, do not force a workaround: open another Unity instance (check `free -g` first; an idle instance is about 5 GB), route MCP with `set_active_instance <工程名>@<哈希>` (hash in `~/.unity-mcp/unity-mcp-status-*.json`), and make the first line of the DSH task brief “set_active_instance first”; leave idle instances for the user to close.
> `File/Exit` after exiting Play may pop a “save scene?” modal (2026-09-19 Project D: saved at 01:49, then entering/exiting Play made it dirty again); the dialog is on the user's desktop, all MCP calls time out, CPU 0%. **Before `File/Exit`, read `scene.isDirty` with `execute_code`**: if dirty and not changes you intended → ask the user first (save / don't save), do not just quit; when stuck, use `DISPLAY=$DISPLAY_FALLBACK xwd -root` + `ffmpeg` to png to see the screen. 09-19 Project C made the same mistake again (File/Exit without reading isDirty first): this machine has no xdotool, so the dialog could not be clicked, and the only option was to ask the user and kill by PID.

**④ Editor language** is stored in EditorPrefs `Editor.kEditorLocale` (ChineseSimplified).

**⑤ Criterion for first-open acceptance**: take the old machine's list of `*.csproj` names and check each against `Library/ScriptAssemblies/*.dll`; do not look at the log.
2026-09-17 first open of three projects: batch import 5–9 minutes each, 0 `error CS`.

## 2026-09-18 connectivity self-check (run this when re-checking)

| Item | How | Result |
|---|---|---|
| DSH text | `dsh_task.js --task "只回复 DSH-OK"` | ✓ 3 s, deepseek-flash |
| DSH image reading | `--model vision --images 7个圆点.png` asking for the count | ✓ answered 7, read_image 1/1 |
| agy CLI | `agy-task.py "只回复 AGY-OK"` | ✓ (default model changed to `gemini-3.8-flash-low`) |
| agy review | `agy_panel.py --fast --images`; then with a custom `--schema` | ✓ both work |
| DeepSeek vision direct | `ds_vision.py --task --images` | ✓ |
| Unity MCP | Open the graphical interface → read `mcpforunity://editor/state`, `manage_scene get_active` | ✓ `is_batch_mode=false` |
| Blender MCP | Start headless → `get_objects_summary` | ✓ |

**Three pitfalls of killing / finding / waiting for processes** (`pkill -f` kills itself, `\|` in `pgrep`'s ERE is not “or”, `read -t < /dev/zero` does not wait)
are on a separate page: [Processes and waiting](b850-linux-environment/processes-and-waiting.md). **Before starting Unity, `pgrep -x Unity`; if you see a lockfile, do not delete it.**

> → [Six scripting pitfalls](b850-linux-environment/scripting-pitfalls.md) — under `set -e` do not write `[ ] && `; under `pipefail`, grep inside command substitution needs `|| true`; do not list zip members with `$NF` (paths with spaces); dry-run mkdir must be guarded too (criterion: git status unchanged after running); `free` headers are localized; read-only reference and export target are two separate parameters.
> → [Blender scripting pitfalls](b850-linux-environment/blender-scripting-pitfalls.md) — in 5.2 `Bone` has no `roll` and axes are in parent-bone space; headless EEVEE warnings are false alarms; mathutils is float32, BVH units are meters, judge penetration with overlap.

> **Symptom**: the command returns 144 with no output at all, and a subsequent `cd` seems not to have run (the shell was replaced).

> **The same day also stumbled on the wait-loop half (09-20, cost about 1 hour)**: after dispatching DSH, I waited for it to finish with `until ! pgrep -f dsh_task.js; do sleep 20; done` — this wait command's own command line contained `dsh_task.js`, so `pgrep` always counted itself; DSH had actually finished in 512 seconds, but I kept believing it was "still running", and even twice judged "still running" in between.
> **Checkable question**: does the string my wait command waits for also appear in the wait command itself?
> **Correct way**: always wait for DSH / long commands via `run_in_background` (notifies on completion); if you really must poll, wait for the **output** rather than the process (`until [ -f 出参文件 ]; do sleep 10; done`), or wait with `pgrep -x` / by PID.

> A killed Unity leaves `unity-mcp-status-<hash>.json` in `~/.unity-mcp/`; afterwards, when another project enters Play (domain reload, heartbeat briefly interrupted), MCP routes requests to this dead instance (reporting “instance not found, available: <old project>”). **After killing Unity, delete the corresponding status file** (check with `ls -t ~/.unity-mcp/`: the one whose hash does not match the current project and whose time is the moment of the kill). The Project B session hit this twice in a row on 2026-09-19.
