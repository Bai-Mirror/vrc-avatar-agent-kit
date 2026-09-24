# 探针 poke · 命中数与面积门槛口径、Unity 验收 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.5 后段（含「Claude·Unity·Play 验收」）。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 poke（静态穿出斑块）· 判据、请求与输出](probe-poke.md) · 下一页：[探针 poke · diag 诊断与外壳/法线修法](probe-poke-diag.md) <!-- nav -->

**命中数 = 达到面积阈值的斑块总数**（各配对 `patches` 条数之和）。

`hits`/`patch_count` 只是参考；**主判据 = `pairs[].total_patch_area_cm2` 与 `patches[].area_cm2`**。
面积门槛（任务 CW，2026-09-20 起；口径任务 CX 复查修正）默认**可推导**：`min_patch_area_cm2 = max(absolute_floor 0.05 cm²,
min_verts_for_patch 8 × area_per_vert_cm2)`，其中 `area_per_vert_cm2` 是**本次配对被测区**的每顶点面积份额
（`pairs[].area_per_vert_cm2 / region_verts / region_area_cm2 / area_per_vert_pos_source` 写明依据）。
**数值口径（任务 CX 写死，别再猜）**：分子 = 三顶点「都在 `covers_regions` 覆盖到、且 `Usable`」的身体三角形面积和（cm²）；
分母 = 同一集合里的顶点数；位置取 **bind pose 稳定参考**（`sharedMesh.vertices × localToWorld`，字段
`area_per_vert_pos_source:"bind_pose"`），`sharedMesh` 读不到时才回落 `"baked"` 的当前形变位置。
**旧行为一键取回**：请求 `poke.min_patch_rule:"legacy"` 仍用固定 0.5 cm²；请求 `poke.min_patch_area_cm2`（旧键 `min_patch_cm2`）
显式覆盖，`min_patch_area_source` 标明 `request`/`adaptive`/`legacy`。
初值 0.5 的来源：Kaguya 身体顶点间距 3–6 mm、脚趾出鞋 3–8 cm²。
**CW 报告里「Milfy 脚趾区每顶点只摊到约 0.0043 cm²」那句是错的**：0.0043 是把 `shrink_cover` 的
`uncovered_area_cm2=11.34` 除以 `affected_verts=2641` 得来的**未遮挡份额/受影响顶点**，不是被测区的每顶点面积份额；
实测 `r9_Set05_t34.json` 的 `area_per_vert_cm2` 在 `none` 候选是 **0.1083**（见 §3.2.5.2 的任务 CX 复查）。
**无论门槛怎么定，被丢掉的分量都要暴露**：`dropped_components` / `dropped_max_area_cm2` /
`dropped_total_area_cm2` / `dropped_max_depth_mm`（配对级与顶层都有）。若某 `sub_part` 的
`d_v_mm.outside>0` 且 `max>tau` 却 `patch_count==0`，该行标 `suspect_subthreshold:true` 并给中文
`suspect_reason`——多半是面积门槛太高，或 `opening`/NaNimation 删点切断了连通（见 §3.2.5.2）。

T2（`AuditFitProbe`）在请求写 `"poke": true` 或 `"poke": {…}` 时，会在同一次 Play 的 `geo_<state_id>.json`
里内嵌同样的 `poke` 块（T2 输出文件名自 v4 起由 `fit_<state>.json` 改为 `geo_<state>.json`）。

**[Claude·Unity·Play 验收]（离线只做 csc 编译，以下必须在 Unity 里跑；随 T-08 第 6 日那次 Play）**：
1. **量 Winter 正常状态分布（I5，先量后定）**：工程C Winter 靴正常状态，打印脚趾/脚掌区 `by_region[].d_v_mm`
   的 p50/p95/p99/max，并记 `shell_faces`/`mesh_triangles`（估靴壁层数）。据此确认/修正 `tau_*`；v2 的
   「擦边 ≤1 mm」无实测依据，不用。
2. **Winter 正负分离**：正常状态脚趾斑块 `total_patch_area_cm2 < 0.5`；`pre_probe_blendshapes` 把
   `Toe_heels=0` 后脚趾斑块 `> 2 cm²`（正样本）——今天穿越计数报 0 的那类。
3. **LUNALICE 正常状态**（含 Delete 后剩余顶点）无 `≥0.5 cm²` 斑块。
4. **MMN 修前补丁**（`pre_probe_blendshapes` 放开 `foot_heel_OFF`）脚趾斑块 `>2 cm²`，修后 `0`
   （并入 T-16 复验）。
5. **剂量单调**：`sailor_shrink` / Itazura `Shrink_Knees`(厂商值 100) 用 `poke_doses:[100,75,50,25,0]`，
   `dose_response[].total_patch_area_cm2` 随剂量上升不下降（`monotone_nondecreasing=true`）。
6. **hide 自检**：`poke_hide` 指向该鞋/上衣后 `hide_selfcheck.ok=true` 且总斑块面积为 0（若它是唯一覆盖件）。
7. **确定性**：同一状态同请求两遍，`pairs[].d_v_mm` 与 `patches` 逐项差 ≤1e-6（BVH 建树已按 `(质心,面序号)` 定序）。
8. **工程C两个活跃根**：`garment_candidates`/`shell` 只见被测根；另一根不参与射线、不把对方三角形当遮挡物。
9. 上面正负样本各渲 2 张图，经 agy＋用户确认后才把 τ/面积阈值从 advisory 升为卡口（`thresholds.yaml`）。
