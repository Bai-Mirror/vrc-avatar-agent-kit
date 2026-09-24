> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/02_环境准备与人工介入/B850_Linux环境/进程与等待.md)

> ← [This machine (Linux) Linux environment](../b850-linux-environment.md)

# Killing, Finding, and Waiting for Processes

The problem this page solves: **three pitfalls repeatedly hit when managing Unity/Blender/script processes with bash on this machine**, plus Unity's GTK window-reshape crash.
Concurrency and clearing the field when memory is short → [Memory budget and concurrency](memory-budget-and-concurrency.md).

**Do not use `pkill -f <string>` in the same bash command** (twice on 2026-09-18 and a third time on 09-20 it killed my own shell, exit code 144): `-f` matches the entire command line, and this command itself contains that string. Instead use `pgrep -f <string>` to list PIDs, exclude `$$`, and `kill` them one by one; for Unity use `pgrep -x Unity`. Likewise, **`until ! pgrep -f <string>` for waiting on a process to end also matches the wait loop itself** and never finishes (waited 10 minutes for nothing on 2026-09-18): besides `pgrep -f <string> | grep -v $$`, the more robust way is to run the awaited command itself with `run_in_background`, which notifies automatically on completion.

> **How the third time happened (09-20)**: the rule was remembered; what failed was the **trigger moment** — I was modifying a script that ran too long and casually wrote a single compound command “`pkill -f scriptname` ; patch ; rerun”, attention on the patch, not realizing this command line itself contained the script name.
> **Checkable question**: does my command contain `pkill -f`? If so, does the string after `-f` also appear elsewhere in this command?

> **`pgrep` patterns are ERE; `\|` is not “or” (2026-09-20)**: when writing `pgrep -a -f "Unity.*工程B\|Unity/Editor"`,
> `\|` in ERE is a **literal vertical bar**, so the whole thing is matched as one string → returns empty → I concluded “Unity is not running”.
> Consequence: I deleted `Temp/UnityLockfile` and started a second editor, **two Unity instances running on the same project at the same time** (risk of corrupting Library).
> **How to write it**: for multiple patterns use `pgrep -f 'A|B'` (unescaped), or simply `pgrep -x Unity` by process name only.
> **More important is the criterion**: before starting Unity, `pgrep -x Unity` + `ps -o pid,lstart,args`; **seeing a lockfile means someone is using it — do not delete it** —
> the existence of the lockfile is itself evidence of “an existing instance”; deleting it dismantles Unity's mutual-exclusion protection.

> **`read -t N < /dev/zero` does not wait (2026-09-20)**: `/dev/zero` always has data immediately, so `read` returns at once;
> written as a polling loop it just spins — my “wait for Unity to exit” loop ran 12 iterations instantly and falsely reported “still running”.
> Foreground `sleep` is forbidden in this environment; **to wait, run the awaited command with `run_in_background`**, which notifies automatically on completion;
> if you must wait inside a script, use `python3 -c "import time;time.sleep(1)"`.


**GLib-GIO-CRITICAL `g_dbus_proxy_call_sync_internal` is harmless noise**; Unity on Linux reports it every few minutes; do not treat it as a fault clue.


## Unity crash signature #2: GTK window-reshape deadlock (2026-09-21 00:53)

**Phenomenon**: Unity exits on its own **while nobody is operating it**, leaving `mono_crash.mem.<pid>.1.blob` in the project directory.
The end of `~/.config/unity3d/Editor.log` is a gdb stack + `Exiting early due to double fault.`

**Shape of the stack (recognize this)**:
```
ContainerWindow_CUSTOM_set_Internal_Position_Injected   ← C# side sets window position
  → ContainerWindow::SetRect → SetGtkWindowSizeAndPositionSync
  → PumpGtkMainloop → gtk_main_do_event → OnConfigure
  → GUIView::ReshapeIfNeeded → ThreadedWindow::Reshape
  → GfxDeviceClient::WindowReshape → Semaphore::WaitForSignal   ← main thread stuck waiting for the render thread
```
**Keep it separate from the other recorded crash**: that one lands in `libnvidia-glcore` and happens when **repeatedly entering/exiting Play**;
this one lands in **GTK window reshape**, unrelated to Play; the trigger is the window size/position being changed (the desktop environment moved the window,
the X session changed, or the editor restoring its layout). In the same round the journal also showed
`Missing X server or $DISPLAY … The platform failed to initialize.`, indicating something really was happening on the X side at the time.

**True cause (confirmed 2026-09-21 01:00, not a random event)**: this machine's graphical session is **xrdp** (`Xorg :10 -config xrdp/xorg.conf`, WM is `kwin_x11`).
`~/.xorgxrdp.10.log` shows **`screen resized to 2560x1600` → later `resized to 3840x2160`** (the RDP client changed resolution/reconnected).
Unity stores the main window rectangle in `RestoredMainWindowSizeX/Y/W/H` in `~/.local/share/unity3d/prefs`,
and at the time it stored **0,115,2560×1485 — the width exactly equal to the old screen width**, i.e. “filling the old screen”.
At startup this rectangle is synced to kwin, and under xrdp the negotiation does not converge → the main thread gets stuck in `WaitForGtkEvent` waiting for the render thread → double fault.
**So it reproduces reliably**: after crashing once, every reopen crashes at the same place; it is not a matter of luck.

**Fix (measured, worked the first time)**: back up, then edit `~/.local/share/unity3d/prefs`:
change `RestoredMainWindowSizeX/Y/W/H` to values clearly away from the edges (e.g. 120,120,1800×1100), `IsMainWindowMaximized=0`;
while at it, also move `MCPForUnity.Editor.Windows.*x/y` away from the origin. Reopen after editing → `MCP_READY after 5s`.

> **Criterion**: is `RestoredMainWindowSizeW` **exactly equal to some historical screen width**? If so, it is filling a screen that no longer exists.
> Also: authentication/login windows are also popped up with positions set from C# (the top of the stack is `ContainerWindow_CUSTOM_set_Internal_Position_Injected`);
> **do not pop such windows right after RDP changes resolution or reconnects**.

**Handling**:
1. **Look at git first**: this kind of crash does not corrupt assets. If `git status <工程>` is clean, the disk matches the commit and nothing was lost.
2. Clear `mono_crash*.blob` (10 MB each) and `Temp/UnityLockfile`, delete `~/.unity-mcp/unity-mcp-status-*.json`;
   **save a copy of the crash log first** before clearing `Editor.log`, otherwise the next startup overwrites it and the stack is lost.
3. Reopen with `-force-vulkan` (the established convention on this machine).
4. **Before reopening you must confirm with `pgrep -x Unity` that no instance is alive**; see the previous item on this page.

> **Checkable question**: did Unity crash “while I was operating it” or “on its own”? If on its own, first look for the stack shape at the end of `Editor.log`;
> do not assume it is the same cause as last time.
