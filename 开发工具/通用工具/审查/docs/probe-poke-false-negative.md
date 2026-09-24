# 探针 poke · 假阴性两处硬卡与面积口径复查 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.5.2 /「任务 CX 复查」。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 poke · diag 诊断与外壳/法线修法](probe-poke-diag.md) · 下一页：[工程A 回归验收口径](regression-工程A.md) <!-- nav -->

##### 3.2.5.2 任务 CW：poke 假阴性的两处硬卡（面积门槛跨身体 + 低置信不许输出 0）

**现象（作者 2026-09-20，工程B第 5 档垂耳兔白粉厚底运动鞋）**：R9 候选 `none`（脚部键全清零＝光脚）报
`patch_count=0 / total_patch_area_cm2=0 / max_depth_mm=0`，据此撤掉鞋件全部收缩键，**用户 Play 里直接看到
脚趾从鞋头穿出来**。证据 `审查产出/工程B/seq_lopear_r9/01_measure/r9_Set05_shoe.json`：
探头**量到了**穿出——`by_sub_part[toe].d_v_mm = {count:2540, outside:472, p95:6.56, p99:10.82, max:14.86}`，
而 `tau_limb_mm=3`。被吃掉的正是**斑块聚合**那一步，三个叠加原因：

1. **面积门槛按另一具身体标定**：`min_patch_area_cm2=0.5` 来自 Kaguya（顶点间距 3–6 mm）。
   CW 当时以为 Milfy 每顶点面积是 0.0043 cm²（把 `shrink_cover` 的 `keys[Toe]: uncovered_area_cm2=11.34 /
   affected_verts=2641` 当成密度），据此认为固定 0.5「物理上到不了」。**任务 CX 复查否定该推导**：0.0043 是
   「未遮挡份额/受影响顶点」，不是被测区每顶点面积；实测被测区密度是 0.1083（`none`）。见下方「任务 CX 复查」。
2. **`opening` 打孔切断连通**：opening 顶点既不成 poke 也不进 union-find 连边，把超阈值区域切成互不相连的小块。
3. **NaNimation 删点二次切断**：连边与面积累加都要求三角形三顶点全可用。

**修法 A：面积门槛跟身体网格密度走（`AuditProbes.cs`）**
- 每配对输出 `area_per_vert_cm2 / region_verts / region_area_cm2 / area_per_vert_pos_source`。
  **任务 CX 修正后的口径**：分子 = 三顶点「都在 `covers_regions`、且都 `Usable`」的身体三角形面积和（cm²），
  与被测斑块的面积累加口径一致；分母 = 同一集合里的顶点数；位置取 **bind pose 稳定参考**
  （`sharedMesh.vertices × localToWorld`，`area_per_vert_pos_source:"bind_pose"`），读不到才回落 `"baked"`。
  旧口径（含不可用顶点、用当前形变位置）会随形态键漂移并虚高——见下方「任务 CX 复查」。
- `min_patch_area_cm2 = max(absolute_floor, min_verts_for_patch × area_per_vert_cm2)`；默认
  `absolute_floor=0.05 cm²`、`min_verts_for_patch=8`（「至少 8 个连通顶点」是顶点数判据、跨身体可比）。
  请求键：`poke.min_patch_rule`（`adaptive` 默认 / `legacy` 固定 0.5）、`poke.absolute_floor_cm2`、
  `poke.min_verts_for_patch`、`poke.min_patch_area_cm2`（旧键 `min_patch_cm2` 仍认）。
  `min_patch_area_source` = `request`/`adaptive`/`legacy`。
- 永远输出被丢掉的分量：`dropped_components / dropped_max_area_cm2 / dropped_total_area_cm2 /
  dropped_max_depth_mm`（配对级 + 顶层）。
- 自检：某 `by_sub_part` 行 `outside>0 && max>tau && patch_count==0` → `suspect_subthreshold:true` + 中文
  `suspect_reason`（「多半是面积门槛或 opening/删点切断了连通」）。

**修法 B：低置信时不输出看着像通过的 0（`AuditStateDriver.cs`）**
`low_confidence=true` **或** `top2_gap_ratio=0` **或** `state_indistinguishable=true` 时，R9 行把
`patch_count / total_patch_area_cm2 / max_patch_area_cm2 / max_depth_mm` **输出成 `null`**（内部排序仍用原值），
行加 `patch_verdict:"undecidable"`，状态加 `patch_columns_suppressed:true` 与中文
`patch_columns_suppressed_reason`。`recommended` 的既有逻辑不变（任务 D2 起：`state_indistinguishable=true`
时 `recommended` 是否作废取决于 `indistinguishable_kind`，见 §3.4 的「任务 D2 / B-T33d」一条）。
**理由**：读那一列的人（人或脚本）
不该拿到 0——0 在别的状态下是真的「无穿出」，混在一起就是假阴性来源；要判几何请查该行的
`si/sd/tilt/d_v_p50` 或原始 poke 产出。

**下次实跑该看什么**（工程B第 5 档 `none` 候选为例，原产出 `r9_Set05_shoe.json` 的 `m_sok_off`
就正好是 `low_confidence=true / top2_gap_ratio=0 / 7 行全 patch_count=0`）：该状态四列应为 `null` 且
`patch_verdict=undecidable`，**同时每行的 `suspect_subthreshold` / `dropped_max_depth_mm` /
`rows[].by_sub_part[toe].suspect_subthreshold` 照写**——这三个里有一个为真/大于 `tau`（脚趾 `max=14.86>3`）
就说明「0 斑块是门槛或 opening/删点切断连通，不是没穿出」。状态可判时，脚趾 `total_patch_area_cm2` 不应再为 0。
对照实验：把 `poke.min_patch_rule` 改 `"legacy"`（或 `poke.min_patch_area_cm2:0.5`）重跑，应复现旧 0 斑块。

##### 任务 CX 复查：`area_per_vert_cm2` 的分子/分母到底是什么（B-T34b）

**实测（`审查产出/工程B/seq_t34_verify/01_adaptive/r9_Set05_t34.json`，同一身体、同一
`covers=[LeftFoot,RightFoot,LeftToes,RightToes]`、只差形态键）**：

| 候选 | `area_per_vert_cm2` | `min_patch_area_cm2`(adaptive) | 可用区顶点数 |
|---|---|---|---|
| `none` | 0.1083 | 0.867 | 3302 |
| `Toe=100` | 0.0772 | 0.618 | 3302 |
| `Foot+Toe` | 0.0094 | 0.075 | 3302 |

**根因（两个，都在分子 / 顶点集合上，分母稳定）**：
1. **分子用了「烘焙形变后」的位置**：`PokeAreaPerVertCm2` 原来吃 `bi.Pos`（当前 `BakeMesh`），`Foot`/`Toe`
   这类收缩键把被测区压小时，面积跟着塌 → 密度跟着形态键走（0.0094↔0.1083，11 倍）。
2. **分子把 `Usable=false` 的顶点也算进去**：`covers` 里 LeftFoot/LeftToes/RightFoot/RightToes 共 **5109**
   个顶点，其中 **1807** 个被 NaNimation 删除（`body_excluded.deleted_nanimated`；`seq_toe_fix` 的
   `by_region.body_region_verts_total` 可直接读到）。这些顶点在烘焙网格里被移走，含它们的三角形面积巨大，
   把 density 抬高一整个数量级；而斑块面积累加（`patchArea`）本来就要求三顶点全 `Usable`，两边口径不一致。
   CW 当时写「分母含被 NaNimation 删掉的顶点 → 门槛偏**宽松**、只会减少假阴性」——**实测相反**：分母只是
   多算了 1807（+55%），分子被拉远顶点抬高得更多，净效果是门槛**偏严**（0.867 > legacy 0.5）。

**修法（`AuditProbes.cs`）**：`PokeAreaPerVertCm2` 加 `usable` 过滤（分子分母都只收可用顶点），位置改用
`BodyMeshInfo.RestPos`（bind pose 稳定参考）；产出加 `area_per_vert_pos_source`（`bind_pose`/`baked`），
R9 行同步加该列。构造数据离线自检（`tmp/cx/CxSelfCheck.cs`）证明：不过滤不可用顶点时一个被拉远的 5 号点能把
density 从 2500 抬到 27500（**11×**），过滤后回到 2500；用烘焙形变位置则从 2500 掉到 750，换回 bind pose 两个
候选完全一致。

**回答「0.867 > 0.5 是不是预期行为」：不是预期，是上述两个口径 bug 叠加出来的假严**。修完后本例
`none` 的 density 应落到 Milfy 脚部网格的真实数量级（`area_per_vert_pos_source:"bind_pose"`、`region_verts` 从
5109 降到可用数 3302），`8 × that` 预计 ≤ legacy 0.5（**下次实跑核对：adaptive 门槛必须 ≤ 0.5**；
若仍 > 0.5，说明该身体脚部网格确实比 Kaguya 的 0.5 假设更稀，那就要按「8 个连通顶点」重新标定，而不是
认 0.867）。其余可读证据：`pairs[].region_verts` / `region_area_cm2` / `area_per_vert_pos_source`，
R9 行的 `area_per_vert_cm2` / `area_per_vert_pos_source` / `min_patch_area_source`。
