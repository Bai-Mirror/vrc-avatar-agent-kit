# 工程A 回归验收口径 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.6。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 poke · 假阴性两处硬卡与面积口径复查](probe-poke-false-negative.md) · 下一页：[探针 delete_coverage（MA ShapeChanger 删除区覆盖）](probe-delete-coverage.md) <!-- nav -->

#### 3.2.6 工程A 回归（Claude 在 工程A 上的验收口径）

以下数值来自 2026-09-18 的实测（`_长程任务_20260918/感知机制研究/00_当日补充_1830.md` 与
`工程A/_施工记录.md` 18:20 条），写在这里给第一轮跑本工具时对照（**本轮只做离线编译，
未启动 Unity，需在 工程A 工程里按下面两组状态复跑确认**）：

1. **鞋脚趾包含 / 穿越**：状态显式写 `A2_Outfit = 1.5/7`（整套档位；用精确分数，即 `0.214286`，不要用被截断的
   小数，否则轮盘会落到上一档）、`A2_Sok = 0`（袜关）、`A2_Sho = 1`（鞋开），其余部位参数显式写 `1`。
   跑 `probes=["containment"]`：**修复前的 git 版本**（`Foot_heel_OFF` 只挂在袜上）`by_region` 里
   `LeftToes`/`RightToes` 的 `inside_ratio` 为**个位数百分比**（实测脚趾 2%）；**修复后**（鞋上补挂同一
   ShapeChanger）脚趾应 **≥ 95%**（实测 100%）。脚掌 85–87% 属正常。任务 U 后 `inside_ratio` 只是参考，
   判据看穿越（下条）。
   本轮改动后 `by_region` 必须能**分别**看到 `LeftFoot` 与 `LeftToes`（手工实测脚趾约 1149 顶点、脚掌约
   852 顶点，供对照）；同一区域在 83 个状态里的 `body_region_verts_total` 应恒定，不再出现
   `LeftFoot` 2033↔3222 的跳变。`A2_Sok = 1`（袜开）时脚趾被 MA ShapeChanger 用 NaNimation 删除，
   会落到 `excluded.deleted_nanimated`、`verts` 随之下降甚至为 0——**这时候脚趾 `flagged` 无意义**
   （几何已不存在），测包含 / 穿越必须用 `A2_Sok = 0` 的状态。
   配对侧：本例自动配对不应再出现 `windowA`…`windowE`/`final-window` 这些抓屏窗口；每件鞋/手套应带
   `pair_source=name_token` 与 `pair_matched_token`（如 `shoes`→`shoes`、`(B)Boots`→`boots`、`Gloves`→`gloves`）。
   任务 U 后判据换成穿越：修复前该状态 `LeftToes`/`RightToes` 的 `crossing_edges` 应明显 ≥ 20、
   `crossing_ratio` ≥ 1%（正样本、`flag_basis=crossing`）；修复后应回到 0 / 个位数（负样本）。
   开口鞋（Silent Twilight）即使 `inside_ratio` 只有 3–6%，`crossing_edges` 也应接近 0。
2. **头饰抓屏**：状态显式写 `A2_Head = 0.5`，跑 `probes=["grab_chain"]`：
   **修复前的 git 版本**（我方换色 clip 引用厂商原件）`grab_point_queue` 应为 **2450**，
   且 `hidden_materials` 里应出现头发等 `renderQueue ≥ 2450` 的可见槽（透过抓屏窗口看不见）；
   **修复后**（改指抓屏副本）抓取点应回到 **3050**（实测 28/28 状态），`hidden_materials` 相应减少。
3. **穿越计数正样本（人为制造，任务 U）**：在 `A2_Sok = 0`（袜关）、`A2_Sho = 1`（鞋开）状态下加请求
   `"pre_probe_blendshapes": [{"renderer": "Body_b", "shape": "foot_heel_OFF", "weight": 0}]`
   （`foot_heel_OFF` 会模糊匹配到 AAO 改名的 `AAO_Merged_foot_heel_OFF_1`）：脚趾被放回高跟姿态、大量穿越鞋头，
   鞋配对里 `LeftToes`/`RightToes` 的 `crossing_edges`/`crossing_ratio` 应显著抬高、`flagged=true`；
   `state_<id>.json` 的 `pre_probe_blendshapes_applied` 必须列出实际设的项（`requested_renderer` /
   `requested_shape` vs 实际 `renderer` / `shape`、`weight`、`old_weight`），且 `blendshapes` 里仍是快照时的原值
   （覆盖只影响探针，不回写快照）。把这个覆盖去掉再跑一次，穿越数应回落——这是「正 / 负样本配对」的核心。
