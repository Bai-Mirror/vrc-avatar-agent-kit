# T-05 部件盘点导出 AuditPartInventory · 范围与口径 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §11 / §11.1。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1/T3 已知局限](known-limits.md) · 下一页：[T-05 部件盘点 · 输出骨架](part-inventory-output.md) <!-- nav -->

## 11. T-05 部件盘点导出 `AuditPartInventory`

> 文件：`unity/Editor/AuditPartInventory.cs`（T-05）。**编辑模式**菜单动作，不走 `request.json` / 状态机泵。
> 菜单：`Tools/AvatarAudit/Export Part Inventory`（priority 110）。也可在 `execute_code` 里调
> `AvatarAudit.AuditPartInventory.Export(null)` 拿到写出路径。
> 输出：`<工程>/_感知/out/inventory.json`（目录自动建）；进度另写同目录 `status.json`。
> 只读：不 MarkSceneDirty、不改资产、不建临时物体（`BakeMesh` 的临时 Mesh 用完 `DestroyImmediate`）。

### 11.1 范围与口径

- **只盘活跃根**：`Resources.FindObjectsOfTypeAll(VRCAvatarDescriptor)` 过滤 `activeInHierarchy` 且非预制体资产；
  一个根下**全部** `SkinnedMeshRenderer` 与 `MeshRenderer`（含 inactive 隐藏件）都出，按 avatar 根相对路径分别排序、
  依次写进 `renderers[]`；`ParticleSystemRenderer` **只计数不展开**。渲染器条目用 `type` 区分。
- **部位映射（SMR）**：沿父链向上遇到的第一个 `HumanBodyBones` 即该骨骼部位（与 T2 §4.6 同一套；取不到人形
  Animator 时退化骨骼原名）。**MA MergeArmature 服装骨按 `mergeTarget` + 骨名映射**（任务 B-补-18，BF 返工）：
  `RegionMapper` 反射调 MA 的 `GetBonesMapping()`（返回 `(baseBone, mergeBone)` 对），把服装骨映射到它要并进去的
  头像人形骨再取部位；装饰骨（鞋链、蝴蝶结）沿父链找最近的已映射骨。**身份匹配落空时按骨骼名兜底**
  （任务 AY，B-补-03）：`Foot.L` / `Foot_L` /
  `Lower_leg.L` / `Toe.R` / `leftfoot` 等常见写法映射到 `LeftFoot` / `LeftLowerLeg` / `LeftToes` 等人形部位；
  装饰骨（`Shoes_Chain.001.L`）认不出时继续沿父链上溯（经 `Foot.L` 归位），仍认不出才记 `Other`。
  *为什么*：导入服装/配饰常带自己的独立骨架，bones 不是头像的人形 Transform，身份匹配整片落 `Other`，
  鞋底厚度因此为 `null`（工程B垂耳兔 `Shoes`），MA 合并件（如 `08_WhitePink_Milfy_MA/Shoes`）的 `covers`
  也整片 `Other`、`key_gaps` 判不了。优先级：MA 映射 > 身份匹配 > 骨名兜底。
  `region_weights` = 蒙皮权重占比；`region_vertex_share` = 主骨骼顶点数占比，
  `covers` = 后者占比 ≥ `region_share_min`（0.02）的部位。权重读法三档：`GetBonesPerVertex/GetAllBoneWeights`
  → legacy `Mesh.boneWeights` → 不可读时最近骨骼近似，`region_source` 标明用了哪档。
- **部位近似（MR，任务 AQ）**：MeshRenderer 没有蒙皮权重，改把 `MeshFilter.sharedMesh` 顶点变换到世界后找
  **最近骨骼**（候选优先人形骨骼全集，退身体 SMR 骨骼、再退全部 SMR 骨骼），取其部位。有顶点 →
  `region_source="nearest_bone"`；网格未开 Read/Write（MR 不能 `BakeMesh`）→ 退物体位置单点 →
  `region_source="nearest_bone_object"`（单部位满占比，粗但非空）。两者都不是蒙皮权重，看 `region_source` 区分。
- **`part_like`（任务 AQ）**：名字或任一祖先名（到 avatar 根）含排除子串 → `false`，否则 `true`；SMR 与 MR
  都有。排除表是文件头 `PartLikeExcludeTokens`（可配置，改表即改判据；`inventory.part_like_rule` 也写了一份）：
  `PCS Preview Icon` / `AreaShow` / `AvatarHight` / `APS_` / `Timer` / `功能_` / `SpsScreenMarker`。
  这判的是「是不是工具/预览/调试物」，只看名字、大小写不敏感，**不替代人工核**——真件被误排只影响 MR 清单
  可读性，漏排会让人多看一眼，取舍是宁可误排也不误放行；工程A 实测里 58 个 MR 约 50 个是 AreaShow/SPS
  标记/插件计时器等。
- **计数（任务 AQ）**：根与每个头像各写 `smr_count`/`mr_count`/`psr_count`；旧的 `renderer_count` 保留，
  值 = `smr_count + mr_count`（= `renderers[]` 长度，与旧口径一致，PSR 不展开）。
- **`body_keys`（任务 AQ）**：每个头像写身体 SMR 的**全部**形态键名（`GetBlendShapeName` 顺序，不排序去重），
  另带 `body_key_count`；身体未识别时为空列表。给 `perception/profile_keys.py` 写素体档案 `all_keys:` 用。
- **闭合度**：三角形顶点按位置焊接（1e-5 m）后，只被 1 个三角形使用的边 ÷ 唯一边数 =
  `boundary_edge_ratio`；`closed = ratio ≤ 0.10`。0.10 的来源：Blender 对 工程A 网格离线标定，
  MMN `Shoes` 三角化后 3.7%、`Socks` 1.0%、平整布片 29%+，取 10% 容得下鞋口/袖口又挡得住纯平面。
- **鞋底厚度启发**：身体（同时含脚与躯干、可见、顶点最多）脚部顶点最低世界 Y − 该件脚部顶点最低世界 Y；
  `shoe_like = sole_thickness_mm ≥ 4`（`03a` S6）。编辑模式不建碰撞体、不做射线，是**启发**不是 T2 精度值。
  身体识别与部位映射现与 T-10 / T2 共用 `AuditBodyPick`（任务 AY）；导入服装自带骨架按骨骼名兜底后，
  Milfy 类服装的 `Shoes` 不再是 `Other`，该件因此有 `sole_thickness_mm`（B-补-03）。
- **切换方式**：扫 descriptor 的 `baseAnimationLayers` + `specialAnimationLayers` 与头像下所有
  MA MergeAnimator 的控制器，逐 clip 抽 `m_Enabled` / `m_IsActive` 曲线。MA MergeAnimator 的
  `pathMode: Absolute`（工程A 两个 A2_FX 合并器）路径已是 avatar 根相对、直接用；
  `Relative` 则按宿主/`relativePathRoot` 拼上 avatar 根相对前缀。`switch.method` 取值
  `m_Enabled | m_IsActive | none`，**两者都有时记 `m_Enabled`**；`by_enabled`/`by_active_self`/
  `by_active_ancestor` 三个标志与 `sources[]`（clip/资产路径/源控制器）都在，供 T-04 细判。
  工程A 的 `kaguya_cloth/outer` 既被整套 radial 写 activeSelf、又被厂商 ON/OFF clip 写 m_Enabled，
  按此规则记 `m_Enabled`（T-05 验收期望）。
- **P8 默认与 `switch.method` 口径（B-补-04，09-19 签字）**：**以 `switch.method` 为准，`by_active_self`/
  `by_active_ancestor` 只是信息字段，不得用它们覆盖 `switch.method`。** `kaguya_cloth/outer` 三标志皆 true，
  但厂商 clip 只写 `m_Enabled`、我方 `On_部位_外套` 只写 `m_IsActive`；`AuditPartInventory.cs:615` 的
  `byEnabled ? "m_Enabled" : …` 优先 `m_Enabled`，故记 `m_Enabled`。P8 默认「不改」下，`vis(kaguya.outer)`
  的 D1/D3 候选在 `DepPlan.BuildTargets`（`DepPlan.cs:1394`）按 `MethodFor(path)` 写 `m_Enabled`；
  又因 `SwitchAllActiveSelf`（`DepPlan.cs:1220-1241`：只要 vis 件有一个 `m_Enabled` 就把候选从 sc 踢出）
  **落 clip 后端**（实测 `AJ_T06_依赖编译器.log:47`：「kaguya_cloth/outer 按 inventory 是 m_Enabled
  切换 → 落 clip 后端」；对比 `kaguya.body_under_sailor` 走 sc）。改 P8（`03:35`）必须改工程并**重导
  `inventory.json`**，否则声明与工程不一致、仍落 clip。
- **MA 控制**：反射扫 `ModularAvatarObjectToggle`（`m_objects[].Object` 解析到 avatar 根相对路径）与
  `ModularAvatarMenuItem`；命中「该渲染器自身或其祖先」才算控制，写进 `renderers[].ma`。MA 的显隐在
  构建期才落到 activeSelf，编辑期没有对应曲线，所以它是 `switch` 之外的独立列。
