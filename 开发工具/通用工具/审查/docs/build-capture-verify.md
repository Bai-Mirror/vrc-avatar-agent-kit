# T-12 构建期截获 · 判据、部署、请求与验收 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §12.4–12.8。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T-12 构建期截获与零残留 · 原理与输出](build-capture.md) · 下一页：[请求序列 sequence](sequence.md) <!-- nav -->

### 12.4 零残留判据

1. 退 Play 后源网格 `uv8` 为空（写的是克隆，源资产没动）；
2. 场景 `isDirty == false`（编辑模式闸关，什么都不加）；
3. `git status` 只剩白名单（`_感知/out/build/*` 属预期产物）；
4. `AuditMappingProbe` 被 VRCSDK `-1024` 删，Harmony 补丁在 `int.MaxValue` 回调或退 Play 时解。

### 12.5 asmdef / 部署

`AvatarAudit.Editor.asmdef` 在 T-09 基础上补：`references` 加 `nadena.dev.modular-avatar.core.editor`、
`AvatarAudit.Runtime`；`precompiledReferences` 加 `VRCSDKBase-Editor.dll`（`IVRCSDKPreprocessAvatarCallback`
在它里面，脚本程序集 `VRC.SDKBase.Editor.dll` 没有）、`VRCSDK3A.dll`（`VRCAvatarDescriptor` 在它里面，
脚本程序集 `VRC.SDK3A.dll` 没有）、`System.Collections.Immutable.dll`（NDMF 虚拟动画器类型依赖）。

> ⚠ AAO 的 `ComponentInfoRegistry` 是 `[InitializeOnLoadMethod]` 扫全 AppDomain 建类型表。部署新类型后
> 若没发生域重载（Enter Play Mode Options 关了域重载），它看不到 `AuditMappingProbeInfo`，`mapping.json`
> 不会产生。**CB 起 pass A 会自检并现场补注册**：反射读 `ComponentInfoRegistry.InformationByType`，
> 缺了就调它的私有 `LoadType(typeof(AuditMappingProbeInfo), [ComponentInformation(...)])`，结果写进
> `build_status.notes`（`AAO registry 自检：...`）。自检失败也不影响其它产物，只在 `notes` 里说明。

### 12.6 请求字段

- `decl`（可选）：声明路径；缺省 `<工程>/_感知/decl.json`。相对路径按工程根解析。
- `synthetic_poke`（可选）：`[{part, region, from_bone, to_bone}]`。`from_bone`/`to_bone`/`region` 是
  `HumanBodyBones` 名。在 AAO 合并前把该件覆盖区内 `from_bone` 有影响的顶点权重改绑 `to_bone`
  （`region` 解析得上时只动 dominant bone 在 `region` 子树内的顶点）；每件用私有网格副本，不污染共用件。

### 12.7 给 Claude 的 Unity 验收步骤

**CB 修后复验（工程A，2026-09-19）**
0. **先部署本次改动**（否则 Unity 里还是旧代码）：
   `python3 开发工具/通用工具/审查/perception/sync_audit.py 工程A`
   → `refresh_unity` → `read_console` 应 0 error；`Assets/AvatarAudit/VERSION` 的 hash/时间应变化。
   域重载后 pass A 的 AAO 自检会兜底，但**尽量让 Unity 做完一次域重载**。
1. 把 T-12 请求放回 `工程A/Library/AvatarAudit/request.json`
   （`tool:"state"`、`avatar`、绝对 `decl`、`out`；模板见 `审查产出/工程A/t1_T12_capture.json`）。
2. 进 Play，跑完当前 state 任务后读 `_感知/out/build/`：
   - `callbacks.log` **恰四行**：`-11000 → -10000 → -1025 → 2147483647`，末列都是 `play`。
   - `build_status.json`：`pin_pass_ran == true`、`optimizing_pass_ran == true`；
     `avatar_root` 以 `(Clone)` 结尾时，`avatar_root_normalized` 应等于声明 `avatar.root`；
     `artifacts` 三份 `available == true` 且无 `reason_code`。
   - `capture.json`：`smr_uv8_marked > 0`、`source_meshes > 0`、`pinned_objects > 0`。
   - `ma_analysis.json`：MMN 鞋/袜 `Foot_heel_OFF` 的 `shapes[]` 项 `rules_count == 2`。
   - `mapping.json`：声明引用的部件键（如 `_Outfit/Outfit_MMN_黑/Shoes` 的 `Foot_heel_OFF`）
     每键有 `mapped/merged/removed_frozen` 结论；`notes` 里有 `AAO registry 自检：...已注册` 或
     `...已现场补注册`。
   - `fx_final.json`：`layer_names` 含 `MA Responsive: Body_b` 与 `Decl: *`；在 `curve_bindings` 里按
     `path`/`property` 找到对应曲线。
   - **若仍有缺席**：直接读 `build_status.artifacts.<名>.reason_code` 按 12.3.1 表定位，不要再猜。
3. 退 Play：源网格 `mesh.uv8 == null`（用 `execute_code` 读原始资产网格），`git status` 只剩白名单。

**编辑模式（零残留，可顺带）**
1. `execute_code` 记录 `_感知/out/build` 是否为空；对场景头像执行 `ManualProcessAvatar`
   （`AvatarProcessor`/VRCFury TestCopy 同款），确认**没有**新增 `_感知/out/build/*`、场景里没有多出
   `AuditMappingProbe`（CB 修了 `AuditSdkCallbackMax` 在闸关时也写 `build_status.json` 的漏洞）。
2. `DestroyImmediate` 克隆体，读 `EditorSceneManager.GetActiveScene().isDirty == false`。

### 12.8 已知局限

- `mapping.json` 依赖 AAO `ObjectMappingContext` 活跃（头像下有 `AvatarTagComponent`，如 TraceAndOptimize）；
  没有 AAO 组件时**不产生真值**，但收尾会写一份 `available:false` + `reason_code:"mapping_no_aao"` 的占位，
  `build_status.artifacts.mapping.reason_code` 同步可见，T-14 据此落 `no_data` 而不是「文件丢了」。
- `TryMapProperty=false` 只表示「冻结/移除」，**分不出 `frozen` 与 `frozen_meaningless`**（后者要零位移几何；
  verdict 的 `frozen_meaningless` 四分仍缺这一半）。
- `fx_final.json` 的虚拟控制器路径是 NDMF 虚拟路径；AAO `ObjectPathRemapper` 的最终改写以提交为准，
  个别层可能仍带虚拟前缀。
- `synthetic_poke` 的 `region` 只做「dominant bone 在子树内」过滤，不做精确覆盖区裁剪；未在 Unity 实测。
- uv8 = `Mesh.uv8` = 第 8 个 UV 通道（索引 7），在 AAO `UVUsageCompabilityAPI` 允许的 0–7 范围内；若
  T&O 的 OptimizeTexture 用到该通道，标记会被改（E4 验）。

---
