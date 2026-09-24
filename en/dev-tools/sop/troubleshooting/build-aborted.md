> 🌐 English translation · [中文原文](../../../../开发工具/SOP/问题定位/构建被中止.md)

# Troubleshooting · Build Aborted (Preprocess Callback Failed)

VRCSDK only says "BuildFrameworkOptimizeHook reported a failure" without saying which one.
**Don't start guessing from the most conspicuous warning**; check in this order.

## ① Look at NDMF severity, not at whichever message looks scariest

NDMF has `Information` / `NonFatal` / `Error`, and **only Error aborts the build**.
Filter the log for the **`Error Reported`** line.

NonFatal warnings (e.g. AvatarPoseSystem reporting "PhysBone exceeds 256") **aren't in there at all** —
they are just reminders, not the blocker.

## ② First check for duplicated singleton-type components

**Many NDMF plugins allow only one instance; with more, they throw `InvalidOperationException` in their own pass and abort.**

The symptoms are extremely misleading:
- None of the bones/menus/parameters that plugin generates **get generated at all**
- Later AAO also complains "unknown component type XXX detected" (because nobody processed it, the component lingered into later passes)
- The exception message may be in **Japanese**, swallowed by NDMF into `Error Reported`, and not prominent in the console

> Measured: the Milfy in 300 had **two AvatarPoseSystem components attached**.

**Tool**: `通用工具/FindDupComponents.cs`

## ③ Then check the optimization components you added yourself

**A misconfigured AAO MergePhysBone reports Error and aborts directly.**

**Tool**: `通用工具/FixAaoMergePhysBone.cs` —
it validates the **parent of each target PhysBone's effective root**,
**not the parent of the object the component sits on**; judging by the latter misjudges everything as fine.

Also run `通用工具/BuildBlockerScan.cs`: scans for null references in MA MergeAnimator + idle/duplicate PhysBones.

## ④ Hard-coded GUID fails to resolve

Plugins locate their own directory in code via `AssetDatabase.GUIDToAssetPath("d63d7c3f…")`;
if the assets were **manually copied into Assets** and the folder `.meta` GUIDs were regenerated, resolution fails → `Instantiate(null)`.

> Measured: PoLKA popped a modal dialog during build and was interrupted; 15 folder `.meta` GUIDs had been regenerated,
> and of 10 hard-coded GUIDs, 9 resolved and one did not.

**Sign**: the plugin behaves abnormally but the Console **reports no missing assets**; the error point is inside the plugin's own code, so it looks like a plugin bug.
**How to check**: extract each folder `.meta` GUID from the official `.unitypackage` and compare one by one with those in the project.
**How to fix**: before changing back to the official GUIDs you **must first grep the whole project to confirm nothing references the wrong batch**, otherwise the change turns into broken links.
**Root fix**: always unpack assets via `.unitypackage` (`通用工具/unpack_unitypackage.py`); don't drag folders.

## ⑤ Modal dialogs freeze Unity's editor loop

MCP will time out on everything. **Enumerating the Unity process's visible windows can confirm whether a dialog is blocking it; don't assume MCP died.**

## ⑥ Compilation fails (not NDMF's fault)

Criterion: **whether `Library/ScriptAssemblies/Assembly-CSharp-Editor.dll` exists and how recent its timestamp is**.
**Don't count `error CS` lines in the log** — a brand-new project failing its first round and succeeding later is normal, and errors from both rounds get mixed together.

For three typical causes, see "Three pitfalls of a brand-new project's first compile" in [20 Asset inventory and import](../20-asset-inventory-and-import.md).

A fourth cause (added 2026-09-01): **`-xr!Library` during delivery packaging mistakenly deleted a plugin's internal `Library` directory** —
see [90 Delivery packaging](../90-delivery-packaging.md).

When the project has compile errors, `AnimatorState.AddStateMachineBehaviour<T>()` **silently returns null**, which shows up as several unrelated plugins throwing `NullReferenceException` in the same batch (e.g. MapleCloset, Triturbo face tracking quantization) — **clear the compile errors first, then look at the plugins**.

## MCP keeps timing out after entering Play: first check whether it's a modal dialog (2026-09-19 Project A)
- **Trigger**: after entering Play, `execute_code` repeatedly gives `Timeout receiving Unity response`, the Unity log shows `MCP-FOR-UNITY: Command TCS timed out (N consecutive)`, and CPU drops to 0.
- **Ask**: "Is there a dialog on screen waiting for someone to click?" — take a screenshot: `python3 -c "import os; from PIL import ImageGrab; ImageGrab.grab(xdisplay=os.environ.get('DISPLAY')).save('<scratchpad>/screen.png')"`, then downscale and read it.
- Instance: during a VRCFury test build the parameters exceeded the limit (342/256, still 291 after compression), which popped a single-button Warning "would have failed to upload" (`ExceptionService.cs:16` calls `DisplayDialog` unconditionally), blocking the main thread. **As long as parameters aren't cut below 256, it pops every time you enter Play.**
- **Trade-off**: this machine has no xdotool, so it can't be clicked; if the scene is already saved, just kill Unity (by PID — don't use a `pkill -f` pattern containing the path, which also matches and kills your own shell), then restore `ProjectSettings.asset`. The root fix is cutting parameters to within 256; audit sessions launch with `AVATARAUDIT_SUPPRESS_DIALOGS=1` (task BU; only intercepts single-button dialogs).
