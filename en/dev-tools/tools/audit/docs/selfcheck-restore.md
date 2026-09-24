> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/selfcheck-restore.md)

# Self-check 2 · Temporary change → restore table; Self-check 3 · Compile time <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §8 / §9 / §9.1. § numbers follow the original; for cross-page § references see [Documentation index](../README.md). <!-- nav -->
> Previous: [Self-check 1 · Origins of GM / SDK symbols used via reflection](selfcheck-symbols.md) · Next: [Self-check 3 · Runtime items to verify (1–17)](selfcheck-runtime.md) <!-- nav -->

## 8. Self-check 2: Temporary change → restore table

| # | Tool | Temporary change | Where restored | Failure path |
|---|---|---|---|---|
| 1 | T1 | GM `ModuleSettings.simulateCulling`: true → false | `AuditStateDriver.Cleanup()` (restores true only if it was actually changed) | The runner's `Stop()` always calls `Cleanup()`; `Cleanup()` itself is idempotent (clears the flag after restoring) |
| 1b | T3 | Same as above (T1 restores the switch to its original value when it ends, so T3 must turn it off again itself, otherwise the render comes out blank) | `AuditTurntable.Cleanup()` | Same as above |
| 1c | T1 | When the scene has no GM, temporarily creates `__AvatarAudit_GM` (`HideFlags.DontSave`, Play mode only, see §3.1) | `AuditStateDriver.Cleanup()` → `GmgBridge.DestroyAuditManager()` (only if `_auditCreatedGo` was created by us; idempotent) | The runner's `Stop()` always calls `Cleanup()`; destroyed even if `SetModule` fails |
| 2 | T1 | Parameter values, `PoseT`/`PoseIK` changed | **Intentionally not restored** — T3 needs to shoot under the same batch of states; changed only inside Play mode, exiting Play reverts automatically | — |
| 3 | T1 | `GestureManager.SetModule` makes GM control this avatar (if it was controlling another avatar, GM `Disconnect`s the old one itself) | **Intentionally not restored** (this is GM's normal state); Play mode only | — |
| 4 | T3 | `Renderer.enabled` of all renderers in the scene: when rendering M/C0/C1 in isolation, everything except R → false | `EnterIsolation`/`ExitIsolation` (snapshot in `_enabledSnapshot`), plus a per-candidate `finally` as a second safety net | `ExitIsolation` is idempotent; `Cleanup()` also backs it up |
| 5 | T3 | Candidate R's `sharedMaterials[slot k]` → FlatColor / Invisible (→ Invisible for the B image) | Each candidate's `finally` (`r.sharedMaterials = origMats`) | Same as above |
| 6 | T3 | During ID rendering, `sharedMaterials` of every visible renderer except R → a unique-color FlatColor, and `R.enabled` → false | `finally` of `ComputeVanishedOwners` writes `saved[j]` back per renderer | Same as above |
| 6b | T3 | Camera `_cam.cullingMask` switches between `~0` (isolation) / `_originalMask` (A/B); `backgroundColor` switches between black / white / `bg` | `Enter`/`ExitIsolation` and each section's `finally` restore to `_originalMask` / `_bg`; the camera itself is a temporary object | Same as above |
| 6c | T3 | `mask_layer` | **No longer changed** (version 2 isolates via enabled; the field is kept in the output only for compatibility with old requests) | — |
| 7 | T3 | `RenderTexture.active` changed | Restored to `prev` inside `RenderToBuffer()`; `Cleanup()` sets it to `null` again | — |
| 8 | T3 | Temporary `Camera` GameObject (`HideFlags.HideAndDontSave`) | `AuditTurntable.Cleanup()` → `DestroyImmediate` | The runner's `Stop()` always calls `Cleanup()`; `SafeDestroy` swallows exceptions and warns |
| 9 | T3 | Temporary `RenderTexture` ×2 / `Texture2D` ×2 / temporary materials (FlatWhite, Invisible, one ID color per visible renderer) | `AuditTurntable.Cleanup()` (`Release()` + `DestroyImmediate`) | Same as above |
| 10 | runner | `EditorApplication.update += Pump` | `-= Pump` in `Stop()` | Every failure path goes through `Stop()` |
| 11 | runner | Pending request in `SessionState` (`auto_play`) | `SessionState.EraseString` after `TryResumePending()` reads it | If Play is never entered, the key stays until the end of this editor session (does not affect the scene) |
| 12 | runner | `EditorApplication.playModeStateChanged` subscription | Static subscription, rebuilt automatically on domain reload; never removed (idempotent) | — |
| 13 | runner (shared by T1/T2/T3) | Detaches project-side (`Assembly-CSharp*`, non-`AvatarAudit`) `EditorApplication.update` callbacks | `AuditCallbackIsolation.Restore()`: after receiving `EnteredEditMode`, reattached **in original order** via `delayCall` (§3.0.2) | Field not reachable via reflection → log warning and skip; Play killed forcibly → not restored (process ends) |
| 14 | runner (shared by T1/T2/T3) | Detaches project-side `playModeStateChanged` callbacks | Same as above, reattached via the official `add_playModeStateChanged` accessor | Same as above; `Restore` is scheduled in `delayCall`, the subscription table is not modified during event dispatch |
| 15 | runner (shared by T1/T2/T3) | `AvatarGen.RuntimeProbe._armed` true → false | **Not restored** — the old probe should not run this round; if its `OnPlay` has been reattached by the next time Play is entered, it re-arms itself | Type/field missing → skip silently |

The list is also written to `isolated_callbacks.json` in the output directory (`isolated_callbacks` / `runtime_probe_disarmed` / `restored_at`).

**Scene persistence**:

- The tools **never call `EditorSceneManager.MarkSceneDirty` and never save the scene**.
- T3 may run in Edit mode; transient changes to `enabled` / `sharedMaterials` are reverted in `finally`, and after reverting the scene data matches the state before the run;
  but Unity may set a dirty flag on the scene when properties are written (the values are restored, only the flag may remain) — so **after a run in Edit mode
  do not casually save the scene**; first `File > Revert` or confirm the diff is empty before saving.
- Output is written only to the directory specified by `out` in the request (+ `<工程>/Library/AvatarAudit/` where the caller places the request itself).

---

## 9. Self-check 3: What cannot be verified without opening Unity / Claude's acceptance focus

### 9.1 Compile time (the first thing Claude should check)

1. After running §1's `sync_audit.py "<工程>"`, does `<工程>/Assets/AvatarAudit/{Editor,Runtime}` in the project have **0 errors**
   (the shaders must also be findable via `Shader.Find("Hidden/AvatarAudit/FlatColor")` / `Hidden/AvatarAudit/Invisible`;
   if not found, `transparency.json` carries a warning and `transparency_check` silently degrades to no check). I have precompiled the 6 `.cs` files against Unity 2022.3.22f1's
   reference assemblies, so if there are errors, suspect first:
   - An assembly name referenced by the asmdef does not exist in **that project** (NDMF / `nadena.dev.modular-avatar.core` /
     `com.anatawa12.avatar-optimizer.api.editor` / `VRC.SDK3A` / `0Harmony.dll` — names were checked against the two `Packages/` of Project A and Project C;
     re-check when switching projects); `versionDefines.expression` uses **bracketed exact match** `[1.18.1]` / `[1.9.16]`
     (**a bare version number `1.18.1` means ≥1.18.1 in Unity**, source: the 2022.3 manual “Assembly definitions · Version Define
     expressions”: https://docs.unity3d.com/2022.3/Documentation/Manual/ScriptCompilationAssemblyDefinitionFiles.html#version-define-expressions ),
     so `AUDIT_MA_1_18_1` / `AUDIT_AAO_1_9_16` are defined only when the package version is **exactly** these versions; other versions (including future 1.19+)
     do not define them and the `#if` sections compile into the fallback; **three orders measured on the fallback**: Project G/Project F MA 1.17.1, Project E MA 1.18.0 → `ma_analysis.json`
     writes `available=false` (`reason_code: harmony_unavailable`; for Project F/Project E the compiled DLLs were read and confirmed to lack
     `ReactiveObjectAnalyzer`). Changing to `[1.18.1]` has no effect on current 1.18.1 orders; it only blocks “a future version silently entering the real path”; revision note (09-19, signed off `B-补-15`);
   - The old location was not fully cleaned: a same-named `AvatarAudit` type still remains under `Assets/Editor/` (sync deletes it; if you get a duplicate-name error, look here first);
   - The project uses API differences such as `GetPixelData` outside URP/HDRP (everything I use is 2022.3 baseline API).
2. Reflection-related compile-time risk = 0 (no direct references to GM / SDK types); **but this also means a misspelled symbol only surfaces at runtime
   as `note` / `params_missing`**, so per §7 confirm again that the GM package version is still 3.9.9.
