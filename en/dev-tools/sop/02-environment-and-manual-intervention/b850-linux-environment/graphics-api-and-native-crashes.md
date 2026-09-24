> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/02_环境准备与人工介入/B850_Linux环境/图形API与原生崩溃.md)

# Graphics API and Native Crashes (this machine (Linux))

> ← [This machine (Linux) environment](../b850-linux-environment.md). Trigger: choosing `-force-vulkan` or `-force-glcore` when opening Unity; or Unity crashed and the log has `Exiting early due to double fault`.

**① Under OpenGL some lilToon / LilBug passes exceed the 32 texture-parameter limit.**
Over the limit: `ltspass_cutout` 33, `lilToonRefraction` 33, `LilBugShader/Refraction` 56, `LilBugShader/ltspass_opaque` 52.
Symptoms: these materials look wrong in the editor viewport and in acceptance renders; the console gets hundreds of `State comes from an incompatible keyword space` per second
(49,000 in 3 minutes, log 197 MB). **The upload package is built for the Windows target and is unaffected; but when using editor renders for visual review, the look of these materials cannot be trusted.**

Alternative: `-force-vulkan` — measured on 2026-09-18 in the graphical session to start: log `Physical Device ... "NVIDIA GeForce RTX 5060 Ti"`, and after loading the scene 0 `incompatible keyword space` lines.
**Default OpenGL runs on the AMD integrated GPU** (xrdp's X server only attaches the iGPU, and GLX cannot switch to NVIDIA); Vulkan does not select the card through the X server, so it can use the discrete GPU.
lilToonSetting.json gets rewritten: this is lilToon's designed behavior after detecting a graphics API change and does not affect uploads (`_长程任务_20260918/派工/B_结论.md`).
**⚠ Under OpenGL opaque lilToon does not draw at all in the editor (measured 09-22, not as mild as “materials look wrong”)**:
after Project B switched to `-force-glcore`, the user's screenshot showed “the base avatar became transparent and disappeared”. Rendering alone with a temporary camera, with forced synchronous compilation, twice in a row: skin `Body_base` (lilToon) 0 pixels, nails 0,
face only the transparent layers and lenses at 10 pixels, `lilToonOutline` ribbon in magenta; the transparent-outline clothing was normal (cardigan 1490). Renderers enabled, not hidden, materials unchanged — purely an editor display problem.
**When describing it to the user, do not call it “grayish”** (I said that and was corrected by the user): say “the skin, face and nails are invisible in the editor; the uploaded model is unaffected”.
**The first reading when measuring rendering is not trustworthy**: the same code measured skin at 1600 pixels the first time and stably 0 afterwards — measure at least twice with async compilation off (`ShaderUtil.allowAsyncCompilation=false`) before concluding.

**OpenGL mode does not save memory and also floods the log (measured 09-22)**:
- On this machine OpenGL = iGPU (xrdp's X only attaches the iGPU); the iGPU's own VRAM is only 512 MB (488 used), and it borrowed another **2.87 GB** from system memory (`/sys/class/drm/card2/device/mem_info_gtt_used`);
  the 16 GB discrete GPU is basically idle. So OpenGL shifts graphics memory pressure onto system memory; it does not save anything.
- The Scene view reports one `incompatible keyword space` for every frame drawn: the previous OpenGL session's `Editor-prev.log` grew to **18.6 GB**. When you don't need to see the scene, switch to the Game tab or close the Scene view.
- To make OpenGL use the discrete GPU too, the candidate is PRIME offload (`__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia`) — **not yet tested** (glxinfo is not installed on this machine);
  the root fix is to run the desktop itself on the discrete GPU (a local display session, or a remote solution streaming a discrete-GPU desktop), which is system configuration and the user's decision.

**⚠ User decision 09-22: from now on all projects use `-force-vulkan`.** The “choose API by task” below is kept as background: under Vulkan, builds/entering Play may still crash natively, so save before building; if it crashes, delete `Temp/UnityLockfile` and reopen; switching back to OpenGL requires asking the user first.

**(Superseded by the 09-22 decision, background only) Choose API by task (measured 09-22)**: use Vulkan for viewing/render reviews (under OpenGL some lilToon materials exceed the texture limit and their look cannot be trusted);
**use `-force-glcore` for builds and measurements (ParamCost90/Final90, NDMF/VRCFury preprocessing)** — under Vulkan such builds intermittently crash natively (see next item),
while under OpenGL two full chains ran through in 2.5 minutes (one round under Vulkan takes about 14 minutes). Switching API requires restarting Unity; read `scene.isDirty` first.

**Intermittent native crashes during builds/entering Play under Vulkan: the root cause is swapchain recreation, not “which attempt”** (log `Got a SIGSEGV` → `Exiting early due to double fault`).
09-19 Project D and 09-21 Project B recorded it as “the third time entering Play / third build round”, overturned on 09-22: it crashed on **the first round after a restart**. The gdb dump (the `External Debugger Dump` section of the crash report)
shows the crashing thread `UnityGfxDeviceW`: `VKWindow::Reshape → GfxDeviceVK::AdjustPrimarySwapChain → UpdatePrimarySwapChain → … → libnvidia-glcore`,
with identical offsets both times. That is: the window resizes (VRCFury/NDMF pop progress bars during builds) → Vulkan on the discrete GPU recreates the swapchain onto the xrdp iGPU X window → driver crash; no Xid in the kernel, plenty of VRAM.
**Practice (after the decision)**: always Vulkan; save scene changes before building/measuring; the task brief says “if it crashes, stop and report the log tail”, and Claude deletes `Temp/UnityLockfile` and reopens (environment recovery, declared as fallback).
**Checkable question**: which thread crashed in the crash report, and is the top of the stack `VKWindow::Reshape`? — stop trying to fit a pattern by attempt count.

## Editor crashed but the process is still alive: do not delete the lock, do not start another Unity on the same project (09-23 L6-0)
- **Phenomenon**: at 01:56, when memory dropped to 1 GB, the interactive editor crashed natively (infinite recursion `DebugProxy::CallOverridenDebugHandler` ↔ `Scripting::LogException`), the process got stuck at “Launching bug reporter” (`cp /tmp/status_<pid>` lacked permission), and **the process was still alive**: RSS 7.4 GB, CPU 50%, MCP unable to connect.
- **What DSH did at the time (wrong)**: deleted `Temp/UnityLockfile` and, with a fake HOME, started `-batchmode` opening **the same project** to finish gathering evidence. Two Unity instances on one project compete to write `Library/` and may corrupt it; this time, by luck, it only incidentally changed `ProjectSettings/lilToonSetting.json` (reverted).
- **Rule**: when MCP cannot connect, first `ps -o stat,etime,%cpu,rss -p <pid>` and `tail Editor.log`; if the end of the log is a crash stack/bug reporter, judge it “crashed but not exited” — **DSH stops and reports `UNITY-CRASHED`, does not delete the lock, does not start another instance**; Claude ends that process (a session it started itself can be ended directly; ask first if the user is using it), confirms the process is gone, then deletes the lock, then restarts or switches to batch.
- **Checkable question**: is the pid corresponding to the lock file still alive? If so, deletion is not allowed.
