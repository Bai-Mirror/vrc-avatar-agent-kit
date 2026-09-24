# 图形 API 与原生崩溃（本机(Linux)）

> ← [本机(Linux) 环境](../B850_Linux环境.md)。触发：要开 Unity 时选 `-force-vulkan` 还是 `-force-glcore`；或 Unity 崩了、日志里有 `Exiting early due to double fault`。

**① OpenGL 下部分 lilToon / LilBug pass 超过 32 个纹理参数上限。**
超限：`ltspass_cutout` 33、`lilToonRefraction` 33、`LilBugShader/Refraction` 56、`LilBugShader/ltspass_opaque` 52。
表现：编辑器视口与验收渲图里这些材质不对；控制台每秒上百条 `State comes from an incompatible keyword space`
（3 分钟 4.9 万条、日志 197 MB）。**上传包按 Windows 目标构建，不受影响；但拿编辑器渲图做视觉评审时，这些材质的观感不可信。**

备选：`-force-vulkan` —— 2026-09-18 图形界面实测能起：日志 `Physical Device ... "NVIDIA GeForce RTX 5060 Ti"`，加载场景后 `incompatible keyword space` 0 条。
**默认 OpenGL 跑在 AMD 核显上**（xrdp 的 X 服务只挂核显，GLX 无法切到 NVIDIA）；Vulkan 不经 X 服务选卡，所以能用独显。
lilToonSetting.json 被改写：lilToon 检测到图形 API 变化后的设计行为，不影响上传（`_长程任务_20260918/派工/B_结论.md`）。
**⚠ OpenGL 下不透明 lilToon 在编辑器里完全画不出来（09-22 实测，不是「材质不对」那么轻）**：
工程B切 `-force-glcore` 后用户截图「素体变透明不见了」。临时相机单画、强制同步编译连测两遍：皮肤 `Body_base`（lilToon）0 像素、指甲 0、
脸只剩透明层与镜片 10 像素、`lilToonOutline` 缎带出洋红；透明描边版衣服照常（开衫 1490）。渲染器开着、没被隐藏、材质没变——纯编辑器显示问题。
**向用户描述时别说成「发灰」**（我这么说过，被用户纠正）：说「皮肤、脸、指甲在编辑器里看不见，上传的模型不受影响」。
**测渲染时第一次读数不可信**：同一段代码第一次测出皮肤 1600 像素，之后稳定为 0——至少测两遍、关异步编译（`ShaderUtil.allowAsyncCompilation=false`）再下结论。

**OpenGL 模式不省内存，还会刷爆日志（09-22 实测）**：
- 这台机器上 OpenGL = 核显（xrdp 的 X 只挂核显），核显自带显存只有 512 MB（已用 488），另从系统内存借了 **2.87 GB**（`/sys/class/drm/card2/device/mem_info_gtt_used`）；
  独显 16 GB 基本闲着。所以 OpenGL 是把图形内存压力挪到了系统内存上，不是省。
- Scene 视图每画一帧就报一条 `incompatible keyword space`：上一个 OpenGL 会话的 `Editor-prev.log` 涨到 **18.6 GB**。不需要看场景时切到 Game 标签或关掉 Scene 视图。
- 想让 OpenGL 也走独显，候选是 PRIME offload（`__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia`）——**尚未实测**（本机没装 glxinfo）；
  根治是让桌面本身跑在独显上（本地显示器会话，或串流独显桌面的远程方案），属系统配置，由用户决定。

**⚠ 作者 09-22 拍板：今后所有工程一律 `-force-vulkan`。** 下面「按活选 API」保留作背景：Vulkan 下构建/进 Play 仍可能原生崩溃，所以构建前先存盘，崩了删 `Temp/UnityLockfile` 重开；想改回 OpenGL 必须先问用户。

**（已被 09-22 拍板取代，只作背景）按活选 API（09-22 实测）**：看图/渲图评审用 Vulkan（OpenGL 下 lilToon 部分材质超纹理上限，观感不可信）；
**跑构建与测量（ParamCost90/Final90、NDMF/VRCFury 预处理）用 `-force-glcore`**——Vulkan 下这类构建会间歇原生崩溃（见下条），
OpenGL 下两根完整链 2.5 分钟跑通（Vulkan 下一轮约 14 分钟）。切 API 要重启 Unity，先读 `scene.isDirty`。

**Vulkan 下构建/进 Play 间歇原生崩溃，根因是交换链重建，不是「第几次」**（日志 `Got a SIGSEGV` → `Exiting early due to double fault`）。
09-19 工程D、09-21 工程B记成「第三次进 Play / 第三轮构建」，09-22 被推翻：**重启后第一轮**就崩。gdb 转储（崩溃报告里 `External Debugger Dump` 段）
崩溃线程 `UnityGfxDeviceW`：`VKWindow::Reshape → GfxDeviceVK::AdjustPrimarySwapChain → UpdatePrimarySwapChain → … → libnvidia-glcore`，
两次偏移完全相同。即窗口改尺寸（VRCFury/NDMF 构建时弹进度条）→ Vulkan 走独显往 xrdp 核显 X 窗口上重建交换链 → 驱动崩；内核无 Xid、显存充足。
**做法（拍板后）**：一律 Vulkan；构建/测量前场景改动先存盘，任务书写「崩了就停、回报日志尾」，由 Claude 删 `Temp/UnityLockfile` 重开（环境恢复，按兜底声明）。
**可查问句**：崩溃报告里崩的是哪个线程、栈顶是不是 `VKWindow::Reshape`？——别再按次数凑规律。

## 编辑器崩了但进程还在：别删锁、别在同一工程另起 Unity（09-23 L6-0）
- **现象**：01:56 内存跌到 1 GB 时交互编辑器原生崩溃（`DebugProxy::CallOverridenDebugHandler` ↔ `Scripting::LogException` 无限递归），进程卡在「Launching bug reporter」（`cp /tmp/status_<pid>` 权限不够），**进程还活着**：RSS 7.4 GB、CPU 50%，MCP 连不上。
- **DSH 当时的做法（错）**：删了 `Temp/UnityLockfile`，用假 HOME 起 `-batchmode` 打开**同一个工程**跑完取证。两个 Unity 同开一个工程会抢 `Library/` 写，可能坏库；这次侥幸只顺带改了 `ProjectSettings/lilToonSetting.json`（已还原）。
- **规矩**：MCP 连不上时先 `ps -o stat,etime,%cpu,rss -p <pid>` 与 `tail Editor.log`；日志末尾是崩溃栈/bug reporter 就判「崩溃未退出」——**DSH 停下回报 `UNITY-CRASHED`，不删锁、不另起实例**；由 Claude 结束该进程（自己起的会话可以直接结束，用户正在用的先问）、确认进程消失后再删锁、再重启或改跑批处理。
- **可查问句**：锁文件对应的 pid 还在不在？在就不许删。
