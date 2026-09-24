> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/deliverables.md)

# Delivered File List and Machine Verification Done <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable`, etc. (originally `审查/README.md`) §0 / §0.1 / §0.2. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Next: [Deployment (sync_audit.py) and invocation](deploy.md) <!-- nav -->

## 0. Deliverables and machine verification done

### 0.1 Files

> Since T-09 the source is split by asmdef: `.cs/.shader` are in `开发工具/通用工具/审查/unity/Editor/`;
> `unity/Runtime/` currently holds only the asmdef (`AuditMappingProbe` pending T-12). Deployment no longer uses manual `cp`;
> it all goes through §1's `perception/sync_audit.py`.

> ⚠ **Don't sync from the workspace while DSH is modifying the `审查/unity/` source** (2026-09-19 Project F: a half-edited `AuditStateDriver.cs` from AN was copied into the project → compilation failed → the MCP bridge couldn't start). Use `sync_audit.py --from-git <rev>` instead: it fetches the specified revision file by file with `git show <rev>:<源路径>` (task AR, landed 2026-09-19), and warns and lists each item when the workspace has uncommitted changes; the old manual approach `for f in $(git ls-tree …); do git show HEAD:$f > …; done` is no longer needed. You can also self-check first with `git status 开发工具/通用工具/审查/unity`.

| File | Role |
|---|---|
| `AuditIO.cs` | Common layer: hand-written JSON parsing/serialization, `status.json`, avatar resolution by name, GestureManager/SDK reflection bridge, menu entry and the `EditorApplication.update` state machine pump |
| `AuditStateDriver.cs` | T1 state driver (Play mode only; includes `pre_probe_blendshapes`, temporary blend shapes before probing, task U) |
| `AuditProbes.cs` | Pure-data probes bundled with T1 (tasks R/U): `grab_chain` grab-pass chain / `coincident` coincident meshes / `containment` containment ratio + surface crossing count / `range` blend shape out-of-range; since task BQ, `delete_coverage` delegates to AuditDeleteCoverage.cs |
| `AuditDeleteCoverage.cs` | Probe `delete_coverage` (task BQ, B-补-20; task BV changed it to **edit-mode measurement**): whether the deletion area of an MA ShapeChanger `Delete` writer is covered by the writer's own piece; menu `Tools/AvatarAudit/Delete Coverage (Edit Mode)` + request file `Library/AvatarAudit/delete_coverage_request.json`; called from T1 in Play it returns `undecidable: MA 已处理网格` (MA already processed the mesh) |
| `AuditTurntable.cs` | T3 turntable render + transparency sorting detection (includes `only_renderers` / `hide_renderers` render filters, task U) |
| `T3ArmFreeze.cs` | T3 prerequisite (C-12): freezes the Animator + manually sets body shrink keys per request, then does the T3 render; rerun script for Project F's manual `t3_arm` `execute_code`; menu `Tools/AvatarAudit/T3 Arm Freeze (Edit Mode)`, request `Library/AvatarAudit/t3_arm_freeze_request.json`, report `<out>/report.json`; example `unity/examples/t3_arm_freeze_request.json` |
| `T3RpSyncSim.cs` | T3 prerequisite (C-12): manually simulates MA BlendshapeSync (reads `Bindings` and copies reference key values to the piece's local keys; `mode=nosync` zeroes them to reproduce the pre-fix state), then does the T3 render; rerun script for Project E's `t3_rp_*`; menu `Tools/AvatarAudit/T3 RP Sync Sim (Edit Mode)`, request `Library/AvatarAudit/t3_rp_sync_sim_request.json`, report `<out>/report.json`; example `unity/examples/t3_rp_sync_sim_request.json` |
| `NipplePatchFrames.cs` | Adds blend shape frames to clothing (C-12): body key 0/100 `BakeMesh` displacement field → nearest 4 points inverse-distance weighting → inverse skinning matrix → `AddBlendShapeFrame` saved as `.asset`; rerun script for Project D's ~40-line nipple pasties `execute_code`; menu `Tools/AvatarAudit/Nipple Patch Frames (Edit Mode)`, request `Library/AvatarAudit/nipple_patch_frames_request.json`, report `<out>/report.json`; example `unity/examples/nipple_patch_frames_request.json` |
| `AvatarAuditFlat.shader` | T3 only: unlit flat-color material (mask pure white / ID map unique color), `ZWrite On` |
| `AvatarAuditInvisible.shader` | T3 only: outputs nothing (`ColorMask 0`, `ZWrite Off`, `ZTest Always`), used to isolate material slots |
| `AvatarAudit.Editor.asmdef` | Editor assembly definition (T-09): references NDMF / MA core / AAO api.editor / VRC.SDK3A + `0Harmony.dll` precompiled; `versionDefines` define `AUDIT_MA_1_18_1` / `AUDIT_AAO_1_9_16` per MA `[1.18.1]`, AAO `[1.9.16]` (square brackets = exact match; a bare version number means ≥ in Unity; B-补-15) |
| `AvatarAudit.Runtime.asmdef` | Runtime assembly definition (T-09): container for `AuditMappingProbe`, references `VRC.SDKBase` + `VRCSDKBase.dll` (implements `VRC.SDKBase.IEditorOnly`, automatically removed by the SDK at build time) |
| `README.md` | This file |

The 8 `.cs` files under ``Editor/` (since T-05 including `AuditPartInventory.cs` / `AuditBatch.cs`) depend only on
`UnityEngine` / `UnityEditor` (`AuditProbes` / `AuditFitProbe` / `AuditPartInventory` additionally use `Unity.Collections`);
GestureManager and the VRChat SDK are always accessed via **reflection**, with no `using`,
so these `.cs` files compile even in projects without GM or with a different SDK version (they just degrade and write that into the output). The asmdef's references to MA/AAO/NDMF
are reserved for T-12 (build-time capture) and aren't used directly by current code. The two `.shader`s are fetched by name via
`Shader.Find` in `AuditTurntable`; if missing, only transparency detection is turned off and a warning is written, without affecting the turntable render.

### 0.2 What has been verified this round (reproducible)

1. **Compiles** (0 error / 0 warning). Using Unity's bundled Mono `csc.exe`, with `-nostdlib+` + Unity's
   `Data/NetStandard/ref/2.1.0` + `shims` + `Managed/UnityEngine/*.dll` + `UnityEditor.dll` as reference assemblies:

   ```bash
   MONO=<Unity安装根>/Editors/2022.3.22f1/Editor/Data/MonoBleedingEdge/bin/mono
   CSC=<Unity安装根>/Editors/2022.3.22f1/Editor/Data/MonoBleedingEdge/lib/mono/4.5/csc.exe
   BASE=<Unity安装根>/Editors/2022.3.22f1/Editor/Data
   REFS="-nostdlib+ -r:$BASE/NetStandard/ref/2.1.0/netstandard.dll"
   for f in $BASE/NetStandard/compat/2.1.0/shims/netstandard/*.dll \
            $BASE/NetStandard/compat/2.1.0/shims/netfx/*.dll \
            $BASE/Managed/UnityEngine/UnityEngine*.dll \
            $BASE/Managed/UnityEditor.dll; do REFS="$REFS -r:$f"; done
   $MONO "$CSC" -nologo -target:library -langversion:9 -warn:4 -out:audit.dll $REFS \
        开发工具/通用工具/审查/unity/Editor/AuditIO.cs \
        开发工具/通用工具/审查/unity/Editor/AuditStateDriver.cs \
        开发工具/通用工具/审查/unity/Editor/AuditTurntable.cs \
        开发工具/通用工具/审查/unity/Editor/AuditFitProbe.cs \
        开发工具/通用工具/审查/unity/Editor/AuditMenuDump.cs \
        开发工具/通用工具/审查/unity/Editor/AuditProbes.cs
   ```

   (After task G, 4 `.cs` files were recompiled with the same command: 0 error / 0 warning; temporary script `_长程任务_20260918/派工/tmp/compile_audit_G.sh`.)
   (Task R compiled 6 `.cs` files with the same command (including the new file `AuditProbes.cs`): 0 error / 0 warning; script `_长程任务_20260918/派工/tmp/compile_audit_R.sh`, log `R_compile.log`.)
   (After task T changed three places in `containment`, 6 `.cs` files were compiled with the same command: 0 error / 0 warning; script `_长程任务_20260918/派工/tmp/compile_audit_T.sh`, log `T_compile.log`. The token-pairing logic was additionally run under mono in a small reflection test, 13 items `ALL PASS`; see §3.2.3.)
   (After task U added crossing counts to `containment`, `pre_probe_blendshapes` to T1, and `only_renderers`/`hide_renderers` to T3, 6 `.cs` files were compiled with the same command: 0 error / 0 warning; script `_长程任务_20260918/派工/tmp/compile_audit_U.sh`, log `U_compile.log`. AAO blend shape name restoration and T3 substring matching were additionally run under mono in a small reflection test, 13 items `ALL PASS`; see §3.2.3.)
   (After task V (T-09) moved the code to `审查/unity/Editor/`, the new-path script `_长程任务_20260918/派工/tmp/compile_audit_V.sh` recompiled 6 `.cs` files: 0 error / 0 warning, log `V_compile.log`.)
   (Task AN (T-13 T1 v4) used `_长程任务_20260918/派工/tmp/an/compile_audit_AN.sh` to compile **all 8 `.cs` files** under `Editor/`
   (including T-05's `AuditPartInventory.cs` and `AuditBatch.cs`): 0 error / 0 warning, log `an/AN_compile_baseline.log`.
   v4 pure logic + 83-state request replay self-check: `an/compile_t1v4_selfcheck.sh` builds the exe, `an/run_t1v4_selfcheck.sh` runs it
   (`MONO_PATH` points to Unity's managed assemblies; the self-check only calls pure logic), **40 PASS / 0 FAIL**, log `an/AN_selfcheck.log`.
   Runtime behavior awaits Claude's verification in Unity/Play; see §9.2.)

   One real error was caught along the way: the fill overload `Texture2D.GetPixels32(Color32[])` doesn't exist in 2022.3's reference assemblies
   (compilation reported `cannot convert from 'UnityEngine.Color32[]' to 'int'`); it was changed to
   `_readTex.GetPixelData<Color32>(0).CopyTo(dest)` (which also avoids allocating a 4 MB managed array on every render).

2. **All JSON-layer runtime tests pass** (28 items `ALL PASS`). Using the reference assemblies above, 3 files were compiled into `audit.dll`,
   then a small test exe was compiled and run under mono on pure logic: the two request JSONs from the task brief parsed verbatim, escaping/negative numbers/nesting/empty objects/empty arrays/
   `null` round-trips, `IDictionary` serialization, the same object serialized twice being byte-for-byte identical, and bad JSON throwing `FormatException`.
   The temporary test files were under `_长程任务_20260918/派工/tmp/` and have been deleted.

3. **Reflection symbols checked one by one** (19/19 OK) — see §8.

4. **Task I (T3 second version: per submesh + transmittance model) recompiles**: 4 `.cs` files compiled with the same command,
   0 error / 0 warning under `-warn:4` (`_长程任务_20260918/派工/tmp/compile_audit_I.sh` + `I_compile.log`).
   This round likewise **did not start Unity or call MCP**; runtime behavior awaits Claude's acceptance in the Project A project.

---
