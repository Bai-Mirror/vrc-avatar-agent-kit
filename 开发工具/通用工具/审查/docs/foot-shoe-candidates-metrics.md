# R9 脚鞋选型 · 教训、鞋垫面口径与验收 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.4 后段。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[R9 脚鞋选型 · 新增字段（CS / D2 / CW）](foot-shoe-candidates-fields.md) · 下一页：[T1 输出格式 · `state_<id>.json`](state-driver-output.md) <!-- nav -->

**⚠ 教训（这条必须记住，任务 CS 的直接来源）**：
> 只把候选自己列的键 `SetBlendShapeWeight` 写上去、**不动别的键**，是**测不出**「这个键要不要清零」的。
> 当服装本身已经把脚部键驱动成 100 时，候选 `none`（不列键）、`=50`、`=100`、`current=…` 量到的是**同一个姿势**——
> 5 行度量完全一致，排序照旧从里面挑一个当推荐，看起来「测过了」，其实所有候选都没被真正区分。
> 实证：`_长程任务_20260918/审查产出/工程B/seq_play_0920/02_r9_Set05_LopEar/r9_Set05_LopEar.json`
> 里 5 行只有 `Foot_heels=50` 那行的 `si`/`tilt` 不同，其余 4 行 `si_p50=4.060768`、`tilt=24.106232` 完全一致，
> 推荐却照样给了 `Foot_heels=100`。
> **规矩**：R9 候选请求一律显式写 `candidates_zero`（列出该部位会被服装/驱动器改写的键）；
> 结果里看到 `state_indistinguishable=true` 时先看 `indistinguishable_kind`：`not_zeroed` 才**不要看推荐**，
> 先查清零域是否漏键、键是否真的写进去了；`candidate_equivalent`（读回两两不同）说明候选本身等价，
> `recommended` 保留、任选其一即可。

**为什么换成「鞋垫面」口径（任务 CF，v2）**：BZ 的 `sd` 量到的是「最近朝下壳面」，实测里就是鞋**外底**；
`Foot_heel_OFF=50`（半抬脚跟）时前掌陷进鞋底实体、离外底反而近，`|sd p50|=2.6 mm` 比平脚的 `=100`
（`11.1 mm`）还小，于是 =50 仍靠 `|sd p50|` 抢到第一——B-T08b 标定没过（工程A 09-19 BZ_after 实测）。
所以 v2 不再拿外底当鞋垫：直接选「法线朝上、在脚部 covers 包围盒内、位于外底之上」的鞋件三角形当
**鞋垫面**（内壳也算，不要求是外壳），量脚底朝下顶点到它的有向距离 `si`，并另算脚底平面与鞋垫平面的
夹角 `tilt_deg`。平底鞋脚贴鞋垫 ⇒ `|si p50|` 小、`tilt` 小；半抬脚跟的前掌陷进鞋垫 ⇒ `si` 负得多、`tilt` 大。
出处：04 T-08 的排序方向（面积↓、深度↓）+ CF 对 B-T08b 标定失败的复盘。

**`si` / `tilt` / 跟隙（v2）口径**（`r9` 的 `note` 与每对配对的 `si_meta` 里也写明）：
- **鞋垫面**：鞋件里 **法线朝上**（**几何法线**按绕序 · 世界向上 ≥ `poke.insole_up_cos`，默认 `0.5`≈60°；
  注意不是 `OrientedNrm`——后者是「远离脚骨」定向，空腔里的鞋垫会被定向成朝下）、
  质心落在**脚部 covers 身体顶点包围盒**（外扩 `poke.insole_bbox_margin_mm`，默认 5 mm）内、
  且**高出朝下外壳面（外底）** `poke.insole_sole_min_mm`–`poke.insole_sole_max_mm`（默认 0.5–80 mm）
  的三角形。`insole_faces` 是认到的面数；**0 = 没认到**（例如实心鞋没有朝上内壳），此时 `si`/`tilt` 为 null，
  排序落到 `|sd p50|` 再落到 `|d_v p50|`（宁缺勿猜，别拿缺失度量冒充最优）。
- **`si`**：脚部 covers 内**朝下**身体顶点（同 `sd` 的法线筛选）到**最近鞋垫面**的有向距离，
  **正=悬空、负=陷入鞋垫**。输出 `si_mm{count,p05,p50,p95,min,max,mean,negative_count}`；
  排序读 `|p50|` 与陷入量 `max(0,-p05)`。`si_foot_verts` 是有鞋垫面时的朝下顶点数。
- **`tilt_deg`**：脚底朝下顶点最小二乘拟合平面与鞋垫面质心拟合平面的夹角（度）；
  另出 `foot_plane_tilt_deg` / `insole_plane_tilt_deg`（各自 vs 水平）便于排障。
  拟合用世界 `y = a·x + b·z + c`（近水平平面），**假定被测状态站立**。
- **跟隙（v2）**：同一批里 `sub_part=ankle`（Foot→Toes 轴向参数 `t<0.15`，脚跟段）的 `si`，
  输出 `heel_gap_mm`（排序读 `p50`）；**顶点数**看 `heel_vert_count`（只数朝下的脚跟顶点，
  旧 v1 会取到脚跟后侧）。旧口径另存 `heel_gap_sole_mm` 只作诊断。
- 取自每个候选那次 poke 配对中 **`si_mm.count` 与 `sd_mm.count` 较大者的配对**（只测一件鞋/袜时就是它）。
- 旧 v1 的 `sd_mm` / `sd_meta{foot_verts,sole_facing_verts}` 仍输出（参考列）：`sd_foot_verts` = 脚部顶点数、
  `sd_vert_count` = 「身体朝下 + 最近壳面朝下」顶点数，两者差太大说明脚底朝向异常或鞋不在脚上。
- 开关：`poke.insole_enabled`（默认 `true`）、`poke.sd_enabled`（默认 `true`）；阈值见上。
  **状态整体倾斜时 si/tilt/sd 都会偏**——这是「假定站立」的代价，倾斜态要另立口径。

**取舍（写死在这里，免得下次又摇摆）**：
1. 为什么不用「脚底垂直向下射线第一命中当鞋垫」：鞋底常有厚度/双层壳，第一命中不一定是鞋垫；用「朝上内壳 + 外底厚度约束」更接近「脚该踩在哪」。
2. 为什么 `insole_sole_max_mm=80`：鞋垫到外底超过 8 cm 的多半是鞋口/鞋帮的朝上面，不是脚床；阈值偏大只会多收，宁可交给 `si` 数值暴露。
3. 为什么 `si` 排 `|sd p50|` 前：`sd` 在 B-T08b 上已被实测证伪（把 =50 排前），保留它只作参考/缺 `si` 时的兜底。
4. `tilt` 排在陷入量之后：`si p50`/陷入量是「贴不贴」，`tilt` 是「正不正」，同分再比更稳。

**本版没算的度量**（`r9` 的 `note`/`not_implemented` 里也写明）：**拉丝**（03b 定义：烘焙三角形与基线比，
最长边比 >3 或面积 <1% 或法线翻转；收缩键过量触发）与**类别约束**——本版只标 `not_implemented`，不参与排序。
`si`/`tilt`/`sd`/跟隙/斑块/`opening`/子部位 `d_v` 与 `containment` 参考列已算；这些度量要另写实现，不得用现有字段顶替。

**[Claude·Unity·Play 验收]**（另见 §3.2.5 与 `审查产出/requests_r9/`）：
> **CF 改版（2026-09-19）后的预期**：新增 `si_p05/p50/p95`、`insole_faces`、`tilt_deg`
> （+`foot_plane_tilt_deg`/`insole_plane_tilt_deg`），排序键变成
> `面积↑ → 深度↑ → |si p50|↑ → si 陷入量↑ → tilt↑ → |sd p50|↑ → 跟隙↑ → |d_v p50|↑`。
> **先跑一遍离线自检**（不占 Play）：
> `bash _长程任务_20260918/派工/tmp/cf/compile_cf.sh`（按 asmdef 取引用，两分支 0 error + 15 PASS，
> 含 工程A BZ_after 回放与「v1 会把 =50 排 =100 前」的对照）。
> 自检里 `si` 是按 `si = sd − H`（`H` = `=100` 的 `sd_p50`，即鞋垫高出外底）**离线注入**的，`tilt` 是假设值；
> **Unity 实测要替换这两个假设**，看下面要读的数字。
1. 工程A MMN 鞋（`A2_Outfit=0.214286`、`A2_Sok=0`、`A2_Sho=1`）：
   **前置**：当前工作区场景已补挂鞋上的 ShapeChanger（`foot_heel_OFF=100`），直接跑会看到 `none`
   与 `=100` 并列 0 斑块。要看「修前」真值先
   `python3 开发工具/通用工具/审查/replay/replay.py apply mmn_foot`（去掉该 SC），跑完
   `replay.py revert mmn_foot`。**任何 `replay apply` 之前先跑 `git status --porcelain`，非空就停**。
   键名出处用 `审查产出/工程A/t1_full_probes/state_MMN__all.json`（构建后名
   `AAO_Merged_Foot_heel_OFF_____足_ヒールオフ_3`）。
   - **修后**（当前场景，`none` 读到键 100）：`=100` 与 `none` 应并列第一档（0 斑块），
     **靠 `|si_p50_mm|` / `tilt_deg` 把 `=50` 罚下**。要读的数字：
     * `=100`/`none`：`si_p50_mm` 在 0 附近（±3 mm）、`tilt_deg` 小（<3°）、`insole_faces` >0；
     * `=50`：`si_p50_mm` 明显更负（前掌陷入，比如 −5～−15 mm）、`tilt_deg` 明显更大（>5°）；
     * `=0` 仍垫底（`total_patch_area_cm2 > 2`）。
     **若 `insole_faces=0`** → 没认到朝上内壳，`si`/`tilt` 全 null、排序退回 `|sd p50|`；
       必须记下 `insole_faces`、`si_vert_count`、`sd_vert_count` 与状态姿势回报，别当 v2 通过。
     **若 `=50` 的 `|si_p50|` 反而更小** → 鞋垫面选错（选到鞋帮/鞋口）或法线筛选有问题，
       记下 `foot_plane_tilt_deg`/`insole_plane_tilt_deg` 与本状态姿势，别直接下结论。
   - **修前**（apply `mmn_foot` 后）：`=100` 第一、`none`/`=0` 垫底且脚趾 `total_patch_area_cm2 > 2`。
2. 工程C Winter 靴（`Outfit=0.875`、`Part_Shoes=1`、`Part_Socks=0`，请求 `requests_r9/project-c_winter_boots.json`）：
   正常态（`none`）脚趾斑块 <0.5 cm²、`si_p50_mm` 接近 0、`tilt_deg` 小，应排第一；
   `Toe_heels=0` >2 cm²（正样本）且 `si_p50_mm` 更负 / `tilt_deg` 更大，排最后。
   **`insole_faces=0` 或正负分不开就整表标 low**，写明原因，定稿等 T-31 后重跑。
3. 排序两遍差 ≤1e-6（poke 已定序）；同一状态两次跑出的 `si_p05/p50/p95`、`tilt_deg`、`heel_gap_p50_mm`
   也应逐位相同。

---
