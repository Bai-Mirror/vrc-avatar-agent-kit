> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/dialog-guard.md)

# Single-Button Dialog Suppression AuditDialogGuard <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable`, etc. (originally `审查/README.md`) §14. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [Request sequence · example, acceptance and limitations](sequence-example.md) <!-- nav -->

## 14. Single-button dialog suppression `AuditDialogGuard` (task BU)

**Purpose**: when entering Play, plugins pop up modal dialogs with “only one button” (2026-09-19 Project A's VRCFury parameter-limit warning,
`Packages/com.vrcfury.vrcfury/Editor-Avatars/Service/ExceptionService.cs` parameters 342/256, only an Ok button).
The modal blocks the editor's main thread → UnityMCP times out repeatedly, audit requests can't run, and the only way out is to kill Unity.
`unity/Editor/AuditDialogGuard.cs` (`[InitializeOnLoad]`) turns such single-button dialogs into
“write one line `Debug.LogWarning("[AvatarAudit] 已屏蔽对话框：…")` + append to a log file, then return `true` directly as if the user clicked OK”.

**Activation condition**: the Harmony patch is installed only when the environment variable `AVATARAUDIT_SUPPRESS_DIALOGS=1`; if unset or set to anything else, it does nothing at all.

**Why only the three-parameter `EditorUtility.DisplayDialog(string title, string message, string ok)` is intercepted**:
this overload has only one “Ok” with no choice to make, so a machine clicking it is equivalent to letting the notice through. The four-parameter (ok/cancel) and five/six-parameter
(`DialogOptOutDecisionType`) overloads are **never intercepted** — they require the user to decide among “save / don't save / cancel”,
and choosing automatically would lose changes (e.g. the save-scene dialog when exiting Play / quitting the editor). The patch only hooks the 3-parameter MethodInfo.

**Harmony source**: at runtime it finds `HarmonyLib.Harmony` via reflection (VRCSDK's `0Harmony.dll` or the one bundled with NDMF);
if not found it only prints a warning and doesn't affect compilation; `AuditDialogGuard.cs` doesn't `using HarmonyLib`, and the asmdef adds no new references.

**Log location**: `<工程>/Library/AvatarAudit/suppressed_dialogs.log`, one line per suppression,
`时间 <TAB> 标题 <TAB> 消息前 500 字` (time <TAB> title <TAB> first 500 characters of the message; line breaks in the message are folded into spaces).

### 14.1 Unity acceptance steps for Claude

1. Start Project A with the environment variable:
   `AVATARAUDIT_SUPPRESS_DIALOGS=1 DISPLAY=$DISPLAY_FALLBACK <Unity安装根>/Editors/2022.3.22f1/Editor/Unity -projectPath "工程A"`.
2. After deploying with `sync_audit.py <工程>`, check the Console; there should be a line
   `[AvatarAudit] 已启用单按钮对话框屏蔽（AVATARAUDIT_SUPPRESS_DIALOGS=1，id=local.avatar-audit.dialog-guard）。`
3. Enter Play: the VRCFury parameter-limit warning that always popped up before should no longer appear, and the Console shows
   `[AvatarAudit] 已屏蔽对话框：<标题> | <消息前500字>`; UnityMCP remains usable in the same session (`manage_scene get_active` responds).
4. Read `<工程>/Library/AvatarAudit/suppressed_dialogs.log`; there are lines with matching timestamps.
5. Reverse verification: restart without `AVATARAUDIT_SUPPRESS_DIALOGS` → no `已启用…` (enabled…) line, and the dialog pops up as before (don't test while a single-button dialog is blocking the way).

### 14.2 Offline verification done (Unity not started)

- Compiled all of `unity/Editor/*.cs` against Project A's built ScriptAssemblies: both branches, with the version macro and without, give 0 errors.
- After removing `0Harmony.dll` from the reference set, both “whole assembly (no-macro fallback)” and “compile only `AuditDialogGuard.cs`” give 0 errors
  → the reflection approach doesn't depend on a compile-time Harmony reference.
- Using the real `0Harmony.dll` (2.0.5) + `UnityEditor.CoreModule.dll`, the same reflection patch as this class was run through under mono:
  `DisplayDialog(string,string,string)` was found, the `Patch` overload resolved successfully, and after patching the call returned `True` without popping a dialog;
  positional binding via `__0/__1` works, and the four-parameter overload was not hooked.
- Scripts and logs: `_长程任务_20260918/派工/tmp/bu/` (`compile_bu.sh` / `compile_bu.log` / `harness2.cs`).
