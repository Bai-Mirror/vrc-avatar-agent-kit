# T-12 构建期截获与零残留 · 原理与输出 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §12 / §12.1–12.3.1。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T-05 部件盘点 · 同名键跟随 key_follow 与已知局限](part-inventory-key-follow.md) · 下一页：[T-12 构建期截获 · 判据、部署、请求与验收](build-capture-verify.md) <!-- nav -->

## 12. 构建期截获与零残留（T-12）

> 出处：`_长程任务_20260918/感知机制研究/04_第一期开工清单.md` T-12；原理 `03_研究与方案.md` §3 / Q4 / Q6 / Q7。
> 代码：`unity/Runtime/AuditMappingProbe.cs`、`unity/Editor/{AuditBuildPasses,AuditHarmonyMA,AuditMappingProbeInfo,AuditFxExport}.cs`。

### 12.1 为什么 / 闸

T-14 `verdict.py` 的写者归因与 AAO 改名对账要三份「构建后真值」：MA 反应式写者图
（`ma_analysis.json`）、最终 FX（`fx_final.json`）、构建前名字→构建后名字/键（`mapping.json`）。
截获由一个 NDMF 插件 `local.avatar-audit` 完成。

**注册方式（CB 根因，2026-09-19 修）**：NDMF 只从**程序集特性**发现插件——`PluginResolver.FindPluginTypes()`
遍历 AppDomain 各程序集的 `[ExportsPlugin(...)]`（`nadena.dev.ndmf/Editor/API/Solver/PluginResolver.cs:91`）。
`AuditBuildPasses.cs` 文件顶必须有：

```csharp
[assembly: ExportsPlugin(typeof(AvatarAudit.AuditBuildPlugin))]
```

只继承 `Plugin<T>` 而不写这一行，`Configure()` 永不执行、pass A/B 全不跑，但四个 SDK 回调照打——
现象正是「`callbacks.log` 四次次序正确 + `build_status.json` 里 `avatar_root:null`、`errors/notes` 为空、
mapping/fx_final/ma_analysis 全静默缺席」，而 NDMF 自己的 `Packages/nadena.dev.ndmf/__Generated/<根名>(Clone)`
照样生成（证明 NDMF 确实在 Play 里跑了、只是没跑本插件）。

**硬闸**（所有 pass 与 SDK 回调共用）：

```
EditorApplication.isPlaying && File.Exists("<工程>/Library/AvatarAudit/request.json")
```

不满足 → 所有 pass 立即 `return`、四个 SDK 回调立即 `return true`。因此 **上传（VRCSDK 与 Play 走同一段
预处理回调）永不执行本工具**；编辑模式 `ManualProcessAvatar` 也只跑别人的构建，本工具零输出。

### 12.2 三段落点

| 段 | 时机 | 做什么 |
|---|---|---|
| pass A `AuditPinPass` | Resolving，`BeforePlugin("nadena.dev.modular-avatar")` | 读 `_感知/decl.json`，按 `parts[].objects[].path` 解析构建克隆上的 GameObject/SMR，逐个 `ObjectRegistry.GetReference` 钉住；uv8 标记；`synthetic_poke` 改绑权重；实例表挂 `AuditMappingProbe` |
| Harmony `AuditHarmonyMA` | MA `ReactiveObjectAnalyzer.Analyze` 的 Postfix | `_context != null` 且 root 是本工程头像根时，反射序列化 `Shapes`/`InitialStates` → `ma_analysis.json`；不 fork MA、不重跑 `Analyze`（F14） |
| pass B `AuditOptimizingPass` | Optimizing，`AfterPlugin("com.anatawa12.avatar-optimizer")` | 从 `AnimatorServicesContext.ControllerContext.Controllers[AnimLayerType.FX]` 导出层/状态/条件/曲线 → `fx_final.json` |

`mapping.json` 由 AAO 在 Optimizing 的 `ObjectMappingContext.OnDeactivate` 里回调
`AuditMappingProbeInfo.ApplySpecialMapping` 写出。探针是 Runtime 组件 + `VRC.SDKBase.IEditorOnly`：
AAO 跑 `-1025`（还在），VRCSDK `-1024` 自动删它——零清理代码。

**uv8 先 `Instantiate(sharedMesh)` 再 `RegisterReplacedObject`**：`sharedMesh` 是工程资产，直接写会污染交付；
克隆 + 登记替换后 AAO 合并才认这条替换（03 Q4）。uv8 内容是 `Vector2(源网格序号, 顶点序号)`。

**只 `MarkEntrypoint`、不 `ModifyProperties`**：`ModifyProperties` 会被 AAO 当成运行时改动，
让 `InternalAutoFreezeNonAnimatedBlendShapesProcessor` 不再冻结这些键（观测者效应）。冻结/合并
由 AAO 自己的 `RecordRemoveProperty`/`RecordMoveProperty` 播进映射，`TryMapProperty` 仍能区分。

### 12.3 输出（`<工程>/_感知/out/build/`，均带 `tool_version` 源 hash）

- `capture.json`：pass A 摘要（解析/钉住/uv8/poke 计数、声明路径）。
- `ma_analysis.json`：`{available, shapes[], rules[], initial_states[]}`。`shapes[]` 每项
  `{target_object,target_object_name,target_kind,property,current_state,override_static_state,rules[]}`；
  `rules[]` 每条 `{value,inverted,initially_active,is_constant,controlling_object,conditions[{parameter,lo,hi,
  initial_value,initially_active,is_constant,reference_object,debug_name}]}`。顶层再给一份扁平 `rules` 便于
  按键 grep（验收「MMN 两条 rule」）。版本宏不匹配时只写 `{"available": false}`。
- `mapping.json`：`{available, meshes:[{mesh,renderer_path,keys:{<源键>:{status,target,target_mesh,
  merged_from}}}]}`。`status ∈ mapped | merged(1:n) | removed_frozen | unavailable`；`mesh` 是**声明口径的
  源路径**，与 `verdict.py._mapping_lookup` 的 (mesh,key) 对得上。
- `fx_final.json`：`{available, controller, parameters[], layers[{index,virtual_layer_index,name,weight,
  blending,ik_pass,synced_layer_index,state_machines[],states[{name,machine,write_defaults,motion,clip,
  curves[],transitions[]}]}], curve_bindings[]}`。`curve_bindings` 是`{layer,state,path,type,property,kind}` 扁平表；
  ObjectReference 曲线额外带 `values[].value/asset_path`。用它按曲线绑定定位 `MA Responsive: Body_b` 与
  `Decl: *` 层。
- `synthetic_poke.json`：每条请求的 `{status,reason,vertices}`。
- `callbacks.log`：SDK 回调次序（本工具在 `-11000 / -10000 / -1025 / int.MaxValue` 各挂一个只记日志的回调）。
  每次 Play 的第一条 `-11000` 会先把旧日志截断，所以文件里只应有本次的四行；`-11000` 之前不会再有别的行。
- `build_status.json`：`{avatar_root, avatar_root_normalized, mapping_written, fx_written, ma_written,
  capture_written, pin_pass_ran, optimizing_pass_ran, harmony_installed, ndmf_apply_on_play, artifacts{...},
  phases[], notes[], errors[]}`。`artifacts.<名>` = `{file, written, producer_written, available,
  reason_code?, reason?}`。**任何没写的产物都必须在 `artifacts` 里带 `reason_code`，禁止静默缺席**；
  收尾（`int.MaxValue` 回调）还会给缺席产物落一份 `available:false` 的占位文件（原因码见 12.3.1）。
  `avatar_root_normalized` 去掉 NDMF/VRCFury 在 Play 构建时临时加的 `(Clone)`，用于和声明 `avatar.root` 对齐。

#### 12.3.1 产物缺席原因码（`build_status.json.artifacts.*.reason_code`）

| 原因码 | 含义 / 下一步 |
|---|---|
| `plugin_not_run` | pass A 从未执行。NDMF 没跑本插件：`ExportsPlugin` 未注册 / 插件被禁用 / NDMF `Config.ApplyOnPlay=false` / 本次构建没走 NDMF。先看 `ndmf_apply_on_play` 与 `notes`。 |
| `pass_b_not_run` | pass A 跑了但 Optimizing 的 pass B 没跑（`AnimatorServicesContext` 未激活或 Optimizing 中途失败）。 |
| `mapping_no_aao` | pass 跑了但 AAO `ApplySpecialMapping` 没回调：头像无 `AvatarTagComponent`（AAO 未参与）、AAO 未跑，或 `ComponentInfoRegistry` 没收录 `AuditMappingProbeInfo`。看 `notes` 里 pass A 的 `AAO registry 自检：...`。 |
| `fx_export_failed` | pass B 跑了但取 `AnimatorServicesContext` / FX 控制器失败，或枚举层时异常。看 `errors`。 |
| `harmony_unavailable` | Harmony 未装上：MA 程序集/`ReactiveObjectAnalyzer`/`Analyze` 找不到，或 MA 版本宏 `AUDIT_MA_1_18_1` 不匹配。 |
| `ma_analyze_not_called` | Harmony 已装但 MA `Analyze` 没以本头像根被调用（该头像可能没有 MA 反应式组件）。 |
| `capture_failed` | pass A 跑了但 `capture.json` 没写出。看 `errors`。 |
| `stale_file` | 文件存在但**不是**本次写的（上一次运行的残留）。以文件内 `tool_version`/时间为准。 |

> 注：`reason_code` 与文件内的 `reason_code` 同源；占位文件一律 `available:false`，真实产物一律
> `available:true`。`artifacts.*.available` 直接读文件里的字段，避免「文件在 = 本次成功」的误判。
