> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/build-capture-verify.md)

# T-12 Build-Time Capture · Criteria, Deployment, Requests and Acceptance <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable`, etc. (originally `审查/README.md`) §12.4–12.8. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T-12 Build-time capture and zero residue · principles and output](build-capture.md) · Next: [Request sequence](sequence.md) <!-- nav -->

### 12.4 Zero-residue criteria

1. After exiting Play, the source mesh's `uv8` is empty (the clone was written, the source asset untouched);
2. Scene `isDirty == false` (the gate is closed in edit mode, nothing is added);
3. `git status` shows only whitelisted items (`_感知/out/build/*` are expected artifacts);
4. `AuditMappingProbe` is deleted by VRCSDK at `-1024`, and the Harmony patch is removed in the `int.MaxValue` callback or on exiting Play.

### 12.5 asmdef / deployment

On top of T-09, `AvatarAudit.Editor.asmdef` adds: `nadena.dev.modular-avatar.core.editor` and
`AvatarAudit.Runtime` to `references`; to `precompiledReferences`: `VRCSDKBase-Editor.dll` (`IVRCSDKPreprocessAvatarCallback`
lives in it, not in the script assembly `VRC.SDKBase.Editor.dll`), `VRCSDK3A.dll` (`VRCAvatarDescriptor` lives in it,
not in the script assembly `VRC.SDK3A.dll`), and `System.Collections.Immutable.dll` (needed by NDMF virtual animator types).

> ⚠ AAO's `ComponentInfoRegistry` is an `[InitializeOnLoadMethod]` that scans the whole AppDomain to build a type table. After deploying a new type,
> if no domain reload happened (Enter Play Mode Options has domain reload turned off), it can't see `AuditMappingProbeInfo`, and `mapping.json`
> won't be produced. **Since CB, pass A self-checks and registers on the spot**: it reflectively reads `ComponentInfoRegistry.InformationByType`,
> and if missing, calls its private `LoadType(typeof(AuditMappingProbeInfo), [ComponentInformation(...)])`, writing the result into
> `build_status.notes` (`AAO registry 自检：...`). A failed self-check doesn't affect other artifacts; it's just noted in `notes`.

### 12.6 Request fields

- `decl` (optional): declaration path; defaults to `<工程>/_感知/decl.json`. Relative paths are resolved from the project root.
- `synthetic_poke` (optional): `[{part, region, from_bone, to_bone}]`. `from_bone`/`to_bone`/`region` are
  `HumanBodyBones` names. Before AAO merging, rebinds the weights of vertices within that piece's coverage area that are influenced by `from_bone` to `to_bone`
  (when `region` resolves, only vertices whose dominant bone is within the `region` subtree are touched); each piece uses a private mesh copy, so shared pieces aren't polluted.

### 12.7 Unity acceptance steps for Claude

**Re-verification after the CB fix (Project A, 2026-09-19)**
0. **Deploy this change first** (otherwise Unity still has the old code):
   `python3 开发工具/通用工具/审查/perception/sync_audit.py 工程A`
   → `refresh_unity` → `read_console` should show 0 errors; the hash/time in `Assets/AvatarAudit/VERSION` should change.
   After a domain reload pass A's AAO self-check acts as a fallback, but **try to let Unity complete one domain reload**.
1. Put the T-12 request back into `工程A/Library/AvatarAudit/request.json`
   (`tool:"state"`, `avatar`, absolute `decl`, `out`; template in `审查产出/工程A/t1_T12_capture.json`).
2. Enter Play, and after the current state task finishes, read `_感知/out/build/`:
   - `callbacks.log` has **exactly four lines**: `-11000 → -10000 → -1025 → 2147483647`, all with `play` in the last column.
   - `build_status.json`: `pin_pass_ran == true`, `optimizing_pass_ran == true`;
     when `avatar_root` ends with `(Clone)`, `avatar_root_normalized` should equal the declaration's `avatar.root`;
     the three `artifacts` have `available == true` and no `reason_code`.
   - `capture.json`: `smr_uv8_marked > 0`, `source_meshes > 0`, `pinned_objects > 0`.
   - `ma_analysis.json`: the `shapes[]` item for the MMN shoes/socks `Foot_heel_OFF` has `rules_count == 2`.
   - `mapping.json`: each part key referenced by the declaration (e.g. `Foot_heel_OFF` of `_Outfit/Outfit_MMN_黑/Shoes`)
     has a `mapped/merged/removed_frozen` verdict; `notes` contains `AAO registry 自检：...已注册` (registered) or
     `...已现场补注册` (registered on the spot).
   - `fx_final.json`: `layer_names` includes `MA Responsive: Body_b` and `Decl: *`; find the corresponding curves in `curve_bindings` by
     `path`/`property`.
   - **If anything is still absent**: read `build_status.artifacts.<名>.reason_code` directly and locate it via the 12.3.1 table; don't guess again.
3. Exit Play: source mesh `mesh.uv8 == null` (read the original asset mesh with `execute_code`), and `git status` shows only whitelisted items.

**Edit mode (zero residue, can be done along the way)**
1. `execute_code` records whether `_感知/out/build` is empty; run `ManualProcessAvatar` on the scene avatar
   (same as `AvatarProcessor`/VRCFury TestCopy), and confirm **no** new `_感知/out/build/*` appeared and no extra
   `AuditMappingProbe` is in the scene (CB fixed the hole where `AuditSdkCallbackMax` wrote `build_status.json` even with the gate closed).
2. `DestroyImmediate` the clone, and read `EditorSceneManager.GetActiveScene().isDirty == false`.

### 12.8 Known limitations

- `mapping.json` depends on AAO's `ObjectMappingContext` being active (an `AvatarTagComponent`, such as TraceAndOptimize, under the avatar);
  without AAO components **no ground truth is produced**, but the wrap-up writes an `available:false` + `reason_code:"mapping_no_aao"` placeholder,
  also visible in `build_status.artifacts.mapping.reason_code`, from which T-14 records `no_data` rather than “file lost”.
- `TryMapProperty=false` only means “frozen/removed”; it **can't distinguish `frozen` from `frozen_meaningless`** (the latter requires zero-displacement geometry;
  verdict's four-way `frozen_meaningless` classification is still missing this half).
- The virtual controller paths in `fx_final.json` are NDMF virtual paths; the final rewrite by AAO's `ObjectPathRemapper` is authoritative upon commit,
  and individual layers may still carry a virtual prefix.
- `synthetic_poke`'s `region` only filters by “dominant bone within the subtree”, without precise coverage-area clipping; not measured in Unity.
- uv8 = `Mesh.uv8` = the 8th UV channel (index 7), within the 0–7 range allowed by AAO's `UVUsageCompabilityAPI`; if
  T&O's OptimizeTexture uses that channel, the marking will be altered (to be verified in E4).

---
