# 探针 poke · diag 诊断与外壳/法线修法 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.5.1。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 poke · 命中数与面积门槛口径、Unity 验收](probe-poke-area.md) · 下一页：[探针 poke · 假阴性两处硬卡与面积口径复查](probe-poke-false-negative.md) <!-- nav -->

##### 3.2.5.1 任务 CI：`poke.diag` 诊断 ＋ 外壳/法线可选修法（上衣假阳性）

**现象（Claude 2026-09-19，工程A `kaguya__Coat_off`，素体水手服）**：`poke_covers=[{garment:"kaguya_cloth/sailor",
covers:["Chest","UpperChest","Spine"]}]`，产出 17 斑块 / 82.6 cm² / 最深 29.9 mm，`shell_faces=14042/27570`；
但同状态 Chest 四方位渲图（`seq_BT10_sailor_view/`、只渲 Body_b+sailor 的 `seq_BT10_sailor_only/`）**看不到皮肤**；
且剂量 `AAO_Merged_sailor_shrink_1`（在 `Body_b` 上，收缩身体）0→100 面积反而 73.2→82.6 cm²（物理上应减少）。
同状态两遍逐位相同（82.59626），hide 自检 ok —— 不是随机/配对问题，是几何判定错。

**开启诊断**：请求加 `poke.diag:true`（或顶层 `poke_diag:true`）。输出：
- 每个斑块的 `patches[].diag`：≤20 个样本顶点（沿身体网格等距抽样，确定性），每条给
  `world`、`d_v_mm`、`nearest_feature`(face/edge/vertex)+`nearest_face`+`tri_index`+`garment`、
  `shell_ray`(0=外向 / 1..4=锥向第 k 条，`shell_ray_kind` 同义)、`shell_ray_end`、
  `winding_dot_outward`(绕序法线·计算外向，<0 即该面被判 `normals_flipped`)、`nearest_face_cone_rescued`、
  `opening`、`pseudo_normal`；`normal_sign=parity` 时另给 `inside_by_parity` / `parity_agree_axes`。
- 每对 `shell_outward_escaped`(外向自己逃逸的面数) / `shell_rescued_by_cone`(外向被挡、靠锥向救回的面数) /
  `shell_rescued_ratio`，以及本次生效的 `shell_rule` / `shell_majority_min` / `normal_sign`。

**假设清单与判据**（先用 diag 数字证实/推翻，再选修法，别直接信）：

| # | 假设 | 用 diag 证实 | 用 diag 推翻 |
|---|---|---|---|
| **H1** | `any`（任一条射线逃逸即外壳）太宽：领口/蝴蝶结/袖口下方的**外表面或衬面**，外向射线被挡，但 ±20° 锥向从遮挡边缘绕出去 → 被当外壳 | 斑块样本的最近外壳面 `shell_ray_kind∈{cone1..cone4}`、`nearest_face_cone_rescued=true` 占多数；该对 `shell_rescued_by_cone` 高、`shell_rescued_ratio` 大 | 样本最近面 `shell_ray_kind=outward` 占多数 → 外壳本身是向外的，H1 不是主因 |
| **H2** | 双层（里衬）网格的**里层面**被当外壳，`normals_flipped` 把伪法线翻反 | 斑块样本的最近面 `winding_dot_outward<0`(`normals_flipped=true`) 且 `shell_ray_kind∈{cone}`（里层被外层挡、锥向从缝隙逃）→ H1+H2 同时成立 | 最近面 `winding_dot_outward≥0`（绕序与外向一致）→ 符号没翻，H2 不成立 |
| **H3** | 锚骨线段外向在胸部（大胸）对上胸/侧胸方向错，伪法线符号反 → 身体收缩离开衣服时 `d_v` 反而变大（解释「收缩越多面积越大」） | 样本 `d_v_mm>0`（报穿出）但 `normal_sign=parity` 下 `inside_by_parity=true`（身体顶点其实在衣服**内**）→ 符号反；改 `normal_sign=parity` 或 `winding` 重跑，**斑块面积塌回 0/小值**、剂量随收缩**下降** | `inside_by_parity=false`（顶点确实在衣服外，穿出是真的）；或改符号后面积不变 → H3 不成立，回到 H1 |

**可选修法（都做成请求参数，不重编译即可对照；默认仍旧行为）与代价**：

1. `poke_shell_rule:"outward"` —— 只有**外向射线自己逃逸**才算外壳（被任何东西挡住的一律不算）。
   最贴合 README 原意「被外套/蝴蝶结盖住的不算露」。代价：贴身但确实露出的薄边可能因 1 mm 起射点贴面而误判（
   可配合 `poke_origin_mm`）；射线数比 `any` 少（外向被挡即停），**更快**。自检里对遮挡片/双层都把它从假阳性救回。
2. `poke_shell_rule:"majority"` + `poke_shell_majority_min:3` —— 5 条里 ≥3 条逃逸才算。
   代价：**治不了小遮挡片**（20° 锥在 5 cm 高的小片旁 4 条全逃逸，仍判外壳，见自检第 `escapes=4` 条）；
   且必须发满 5 条射线，最慢。
3. `poke_normal_sign:"winding"` —— 伪法线直接用网格绕序法线，不信锚骨外向。
   代价：依赖模型绕序正确（厂商网格可能翻面）；`normals_flipped` 仍照旧统计，便于对照。
4. `poke_normal_sign:"parity"` —— 绕序法线定朝向，每个身体顶点用 +X/+Y/+Z 三条 `RaycastAll` 的奇偶投票
   （`PokeParityFromHitCounts`，3 轴多数；**只数本件 collider 的命中**，避免多件叠穿时内外无定义）
   判「在不在衣服里」来定符号：在内取负、在外取正。
   代价：每个被覆盖顶点多 3 条射线（大网格 × 3，可能显著变慢，注意 `poke_ray_budget`）；对非闭合/自交网格
   投票可能不可靠（开口处奇偶本就无定义），此时退回 `winding` 并标注。**建议先 `winding` 看符号是否整体反，
   再决定要不要上 `parity`。**

**离线自检**（`_长程任务_20260918/派工/tmp/ci/CIPokeSelfCheck.cs --selftest`，随本工具源码一起编；
任务 CW 起可用更轻的 `_长程任务_20260918/派工/tmp/cw/compile_cw.sh`——只编 12 个可离线编译文件 + 该自检，
不依赖 MA/AAO 程序集）：

```
bash _长程任务_20260918/派工/tmp/ci/compile_ci.sh          # 全量（含 MA/AAO）
bash _长程任务_20260918/派工/tmp/cw/compile_cw.sh          # 轻量（12 文件，0 error/0 warning）
```
覆盖：decl 解析（字符串 / 对象 / part 级 garment / 每个 object 一条 / 无 covers 不配 / 真实 工程A decl
的 `kaguya_cloth/sailor`）+ 人造网格**平板 正/负例、遮挡片 正/负例、双层 正/负例**、规则边界
+ 奇偶投票聚合 + **任务 CW：面积门槛推导（adaptive/legacy/request）、每顶点面积份额、「有顶点超阈值却
patch_count=0」自检、低置信状态四列抑制成 null + `patch_verdict=undecidable`、抑制时诊断列仍可读**。
当前 **52 PASS / 0 FAIL**。

**声明解析修复（同一个 bug）**：`decl.json` 的 `parts[].objects` 是 `{path,renderer}` 对象，旧
`PokeReadDeclCovers` 写的是 `objs[0] as string` → 恒 null → 带 `poke.decl` 的请求全部退回关键词配对。
F13 的 `audit.log` 实测只剩 `请求没有声明 covers，退回关键词配对 1 件`（只配到 `kaguya_cloth/loafer`，
sailor 完全没测）。现改为 `PokeParseDeclCovers`：对象取 `path`（兼容 `garment/mesh/object/name`）、
字符串直接当件名、**每个 object 各生成一条配对**；`AuditBuildPasses.AuditDecl.Load` 一并兼容字符串 objects。
**Unity 复验时应看到 `pair_source=decl_covers`、`covers_regions=["Chest","Spine"]`（`UpperChest` 不是身体
区域会照旧 WARN）、`garment=kaguya_cloth/sailor`，而不是退回 `name_token`。**

**Claude 在 Unity 里复验步骤（同一次 Play，必须真跑）**：

1. **复现假阳性 + 打开诊断**：用 `kaguya__Coat_off` 同参数、`probes:["poke"]`、sailor covers 同前，
   请求加 `poke.diag:true`。记录基础 `total_patch_area_cm2`（应仍 ≈82.6）与每对
   `shell_rescued_by_cone`/`shell_rescued_ratio`、每个斑块 `diag[].shell_ray_kind`、
   `winding_dot_outward`、`d_v_mm`。
   - `shell_rescued_ratio` 高 + 样本多为 `cone*` → **H1 成立**；
   - 样本 `winding_dot_outward<0` 多 → **H2 成立**。
2. **验 H3（剂量）**：同请求加 `poke.doses:[100,75,50,25,0]`（`perturb` 同前、在 `Body_b`），
   `poke.diag:true`。看 `dose_response`：旧 `anchor` 规则应复现「剂量↑面积↑」；
   再各跑一遍 `poke_normal_sign:"winding"` 与 `"parity"`：**若面积随收缩下降/塌回** → H3 成立，符号确被翻反。
3. **验修法**：分别跑 `poke_shell_rule:"outward"`、`"majority"`（对照 H1）与
   `poke_normal_sign:"winding"`/`"parity"`（对照 H2/H3），记 `total_patch_area_cm2`、
   `shell_faces`、`normals_flipped`。期望：`outward` 把假阳性面积显著压下去且**不再把渲图全覆盖的区域报穿出**；
   若压到 0 但同时把真穿出也压没了，说明该件确有该露的开口，需回看 `escapes=...` 分布再定阈值。
4. **decl 复验**：用 F13 那支请求（`poke.decl` 指向 `工程A/_感知/decl.json`）重跑，
   确认 `pair_source=decl_covers`、各件 `covers_regions` 与 decl 一致、`garment_candidates` 里 28 个带 covers
   的 part 都进入配对；`audit.log` **不再**出现 `请求没有声明 covers，退回关键词配对`。
5. 两遍逐位：同请求同参数跑两遍，`patches[].diag` 与 `shell_rescued_by_cone` 逐项 ≤1e-6。
6. 任何视觉/承重结论照旧先过 agy 证伪再采纳。
