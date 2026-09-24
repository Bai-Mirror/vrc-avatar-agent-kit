> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/build-capture.md)

# T-12 Build-Time Capture and Zero Residue · Principles and Output <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable`, etc. (originally `审查/README.md`) §12 / §12.1–12.3.1. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T-05 Part inventory · same-name key following key_follow and known limitations](part-inventory-key-follow.md) · Next: [T-12 Build-time capture · criteria, deployment, requests and acceptance](build-capture-verify.md) <!-- nav -->

## 12. Build-time capture and zero residue (T-12)

> Source: `_长程任务_20260918/感知机制研究/04_第一期开工清单.md` T-12; principles in `03_研究与方案.md` §3 / Q4 / Q6 / Q7.
> Code: `unity/Runtime/AuditMappingProbe.cs`, `unity/Editor/{AuditBuildPasses,AuditHarmonyMA,AuditMappingProbeInfo,AuditFxExport}.cs`.

### 12.1 Why / gate

T-14 `verdict.py`'s writer attribution and AAO rename reconciliation need three pieces of “post-build ground truth”: the MA reactive writer graph
(`ma_analysis.json`), the final FX (`fx_final.json`), and pre-build name → post-build name/key (`mapping.json`).
Capture is done by an NDMF plugin `local.avatar-audit`.

**Registration (CB root cause, fixed 2026-09-19)**: NDMF discovers plugins only through **assembly attributes** — `PluginResolver.FindPluginTypes()`
iterates over `[ExportsPlugin(...)]` in each assembly of the AppDomain (`nadena.dev.ndmf/Editor/API/Solver/PluginResolver.cs:91`).
The top of `AuditBuildPasses.cs` must have:

```csharp
[assembly: ExportsPlugin(typeof(AvatarAudit.AuditBuildPlugin))]
```

If you only inherit `Plugin<T>` without this line, `Configure()` never executes and pass A/B never run, but the four SDK callbacks still fire —
the symptom is exactly “`callbacks.log` shows four entries in the correct order + `avatar_root:null` in `build_status.json`, empty `errors/notes`,
mapping/fx_final/ma_analysis all silently absent”, while NDMF's own `Packages/nadena.dev.ndmf/__Generated/<根名>(Clone)`
is still generated (proving NDMF really did run in Play, just not this plugin).

**Hard gate** (shared by all passes and SDK callbacks):

```
EditorApplication.isPlaying && File.Exists("<工程>/Library/AvatarAudit/request.json")
```

If not satisfied → all passes immediately `return`, and the four SDK callbacks immediately `return true`. Therefore **upload (VRCSDK goes through the same
preprocessing callbacks as Play) never executes this tool**; edit-mode `ManualProcessAvatar` also only runs other plugins' builds, and this tool produces zero output.

### 12.2 Three landing points

| Stage | Timing | What it does |
|---|---|---|
| pass A `AuditPinPass` | Resolving, `BeforePlugin("nadena.dev.modular-avatar")` | Reads `_感知/decl.json`, resolves GameObjects/SMRs on the build clone by `parts[].objects[].path`, pins each one with `ObjectRegistry.GetReference`; uv8 marking; `synthetic_poke` rebinds weights; attaches `AuditMappingProbe` to the instance table |
| Harmony `AuditHarmonyMA` | Postfix of MA `ReactiveObjectAnalyzer.Analyze` | When `_context != null` and the root is this project's avatar root, reflectively serializes `Shapes`/`InitialStates` → `ma_analysis.json`; doesn't fork MA, doesn't rerun `Analyze` (F14) |
| pass B `AuditOptimizingPass` | Optimizing, `AfterPlugin("com.anatawa12.avatar-optimizer")` | Exports layers/states/conditions/curves from `AnimatorServicesContext.ControllerContext.Controllers[AnimLayerType.FX]` → `fx_final.json` |

`mapping.json` is written by AAO calling back
`AuditMappingProbeInfo.ApplySpecialMapping` in `ObjectMappingContext.OnDeactivate` during Optimizing. The probe is a Runtime component + `VRC.SDKBase.IEditorOnly`:
while AAO runs at `-1025` it's still there, and VRCSDK at `-1024` deletes it automatically — zero cleanup code.

**uv8: first `Instantiate(sharedMesh)`, then `RegisterReplacedObject`**: `sharedMesh` is a project asset, and writing to it directly would pollute the delivery;
only after cloning + registering the replacement does AAO's merge recognize this replacement (03 Q4). The uv8 contents are `Vector2(源网格序号, 顶点序号)` (source mesh index, vertex index).

**Only `MarkEntrypoint`, not `ModifyProperties`**: `ModifyProperties` would be treated by AAO as a runtime modification,
making `InternalAutoFreezeNonAnimatedBlendShapesProcessor` no longer freeze these keys (observer effect). Freezing/merging
is propagated into the mapping by AAO's own `RecordRemoveProperty`/`RecordMoveProperty`, and `TryMapProperty` can still distinguish them.

### 12.3 Output (`<工程>/_感知/out/build/`, all carrying a `tool_version` source hash)

- `capture.json`: pass A summary (resolve/pin/uv8/poke counts, declared paths).
- `ma_analysis.json`: `{available, shapes[], rules[], initial_states[]}`. Each item in `shapes[]` is
  `{target_object,target_object_name,target_kind,property,current_state,override_static_state,rules[]}`;
  each entry in `rules[]` is `{value,inverted,initially_active,is_constant,controlling_object,conditions[{parameter,lo,hi,
  initial_value,initially_active,is_constant,reference_object,debug_name}]}`. The top level additionally gives a flat `rules` list for easy
  grepping by key (acceptance “two MMN rules”). When the version macro doesn't match, only `{"available": false}` is written.
- `mapping.json`: `{available, meshes:[{mesh,renderer_path,keys:{<源键>:{status,target,target_mesh,
  merged_from}}}]}`. `status ∈ mapped | merged(1:n) | removed_frozen | unavailable`; `mesh` is the **source path in the declaration's
  convention**, matching the (mesh,key) of `verdict.py._mapping_lookup`.
- `fx_final.json`: `{available, controller, parameters[], layers[{index,virtual_layer_index,name,weight,
  blending,ik_pass,synced_layer_index,state_machines[],states[{name,machine,write_defaults,motion,clip,
  curves[],transitions[]}]}], curve_bindings[]}`. `curve_bindings` is a flat table of `{layer,state,path,type,property,kind}`;
  ObjectReference curves additionally carry `values[].value/asset_path`. Use it to locate the `MA Responsive: Body_b` and
  `Decl: *` layers by curve binding.
- `synthetic_poke.json`: `{status,reason,vertices}` for each request.
- `callbacks.log`: SDK callback order (this tool hooks a log-only callback at each of `-11000 / -10000 / -1025 / int.MaxValue`).
  The first `-11000` of each Play truncates the old log first, so the file should only contain this run's four lines; nothing else will appear before `-11000`.
- `build_status.json`: `{avatar_root, avatar_root_normalized, mapping_written, fx_written, ma_written,
  capture_written, pin_pass_ran, optimizing_pass_ran, harmony_installed, ndmf_apply_on_play, artifacts{...},
  phases[], notes[], errors[]}`. `artifacts.<名>` = `{file, written, producer_written, available,
  reason_code?, reason?}`. **Any artifact not written must carry a `reason_code` in `artifacts`; silent absence is forbidden**;
  the wrap-up (`int.MaxValue` callback) also drops an `available:false` placeholder file for each absent artifact (reason codes in 12.3.1).
  `avatar_root_normalized` strips the `(Clone)` that NDMF/VRCFury temporarily add during the Play build, for aligning with the declaration's `avatar.root`.

#### 12.3.1 Artifact absence reason codes (`build_status.json.artifacts.*.reason_code`)

| Reason code | Meaning / next step |
|---|---|
| `plugin_not_run` | pass A never executed. NDMF didn't run this plugin: `ExportsPlugin` not registered / plugin disabled / NDMF `Config.ApplyOnPlay=false` / this build didn't go through NDMF. Check `ndmf_apply_on_play` and `notes` first. |
| `pass_b_not_run` | pass A ran but the Optimizing pass B didn't (`AnimatorServicesContext` not activated, or Optimizing failed midway). |
| `mapping_no_aao` | The pass ran but AAO's `ApplySpecialMapping` wasn't called back: the avatar has no `AvatarTagComponent` (AAO not involved), AAO didn't run, or `ComponentInfoRegistry` didn't register `AuditMappingProbeInfo`. Check pass A's `AAO registry 自检：...` (AAO registry self-check) in `notes`. |
| `fx_export_failed` | pass B ran but getting `AnimatorServicesContext` / the FX controller failed, or an exception occurred while enumerating layers. Check `errors`. |
| `harmony_unavailable` | Harmony wasn't installed: the MA assembly/`ReactiveObjectAnalyzer`/`Analyze` couldn't be found, or the MA version macro `AUDIT_MA_1_18_1` doesn't match. |
| `ma_analyze_not_called` | Harmony is installed but MA's `Analyze` wasn't called with this avatar root (the avatar may have no MA reactive components). |
| `capture_failed` | pass A ran but `capture.json` wasn't written. Check `errors`. |
| `stale_file` | The file exists but was **not** written this time (residue from a previous run). Go by the `tool_version`/time inside the file. |

> Note: `reason_code` shares its source with the `reason_code` inside the file; placeholder files are always `available:false`, and real artifacts are always
> `available:true`. `artifacts.*.available` reads the field directly from the file, avoiding the misjudgment “file exists = this run succeeded”.
