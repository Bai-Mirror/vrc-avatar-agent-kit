# T2 贴合探针 · 算法与判据（7–10）、v2 排除与拒绝 <!-- nav -->

> 旧称：T2（原 `审查/README_T2.md`） §4 后半 / §4.5。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T2 贴合探针 · 算法与判据（1–6）](fit-probe-algorithm.md) · 下一页：[T2 贴合探针 · v3 覆盖范围、输出、性能](fit-probe-scope-output.md) <!-- nav -->

7. **脚部专项**（`foot.enabled`，v3 改为「每只脚 × 每件覆盖该脚的衣物」）：
   - **覆盖该脚** = 该衣物的覆盖部位集合（§4.6）含该侧的 `LeftFoot/LeftToes`（或 `RightFoot/RightToes`）；
     衣物蒙皮判不了（`region_source=no_bones` 等）时退回旧的 `footCoverage>0` 口径。
   - 脚 = 部位为 `LeftFoot/LeftToes` 或 `RightFoot/RightToes` 的身体顶点（v2 经由 1.5 的父链映射，
     所以 `Foot_L$Toe_L$85` 这类名字能正确归类）；被排除顶点不参与。
   - **分类**（每条 `feet[]` 带 `class` + `class_source` + `class_detail` + `thickness_p50_mm`/`thickness_count`），
     优先级 **(a) 请求显式 > (b) 几何厚度 > (c) 名称关键词**：
     - (a) 请求 `foot.footwear` / `foot.legwear` 路径清单（全路径或叶子名）→ `class_source="request"`；
     - (b) 脚底下方**厚度**：沿 `-Y` 从脚底顶点打到该衣物，第一次与最后一次命中的距离，取双脚底顶点的
       p50。`>= sole_min_mm`（默认 4 mm）→ `footwear`；`< 2 mm`（贴身）→ `legwear`；
       落在 `[2mm, sole_min_mm)` → 几何不表态，落 (c)。`class_source="geometry"`。
       实现用 `Physics.RaycastNonAlloc` 一次取全部命中；个别情况只回一条时，补一条「脚底下方
       `probe_mm` 处向上」的射线取外底，再减内底距离（等价口径）。
     - (c) 路径关键词：`(?i)(shoe|boot|loafer|heel|sandal|sneaker|靴|鞋)` → `footwear`；
       `(?i)(sock|stocking|tights|袜)` → `legwear`。`class_source="name"`。
     - 都不中 → `other`，`class_source="default"`。
   - **footwear**：保留原有鞋底指标。脚底 = 该脚里法线朝下（`n.y < -0.5`）的顶点。向下 `-Y` `probe_mm`
     打到鞋内底**正面**（法线朝上）→ 悬空，记正；向下没打到、向上 `+Y` 打到内底**背面**（法线朝上且与
     `+Y` 同向）→ 穿底，记负。输出 `signed_mm` 的 p05/p50/p95、`below_sole`（<0 数）、`floating_gt5mm`（>5mm 数）。
   - **footwear**：脚跟 = 沿 `Foot→Toes` 连线投影最靠后的 10% **脚底**顶点，其中有向距离 p50；
     脚尖 = 沿该连线最靠前的 10% **脚部**顶点，其中被该鞋 `pierced` 的数量（有没有穿出鞋头）。
   - **legwear / other**：**不算鞋底有向距离**（对贴身袜子无意义），只报 `covered`/`pierced`/`coverage`/
     `pierce_ratio` 与 `gap_avg_mm`（该脚被包住的顶点上，身体表面到衣物内表面的外向命中距离均值）、
     `gap_count`。
   - 每条 `feet[]` 都带 `foot_verts` / `sole_verts` / `shape_keys`。`shape_keys` = 身体网格上名字匹配
     `(?i)(foot|heel|toe|shoe|highheel|sock)` 的形态键当前权重（直接读 `GetBlendShapeWeight`，含 0）。
   - *为什么改*：袜（贴身）没有「脚底—鞋内底」这个结构，旧版对 `stocking` 量出 p50≈-13 mm、全部
     `below_sole`，数值无意义；且旧版只报覆盖最多的一件，穿两层（袜+鞋）时看不到另一层。
8. **markers**：按深度排序的前 `markers_top` 个穿出顶点世界坐标 + 部位 + 衣物 + 深度 + 顶点号。
9. **自检改动**：`perturb` 在烘焙前置形态键、`hide` 在烘焙前关 renderer，均在 `finally`/`Cleanup` 恢复。
10. **清理**：临时 GameObject / Mesh 全部 `Object.DestroyImmediate`；恢复 `Physics.queriesHitBackfaces`、
    形态键、`renderer.enabled`；**不 `MarkSceneDirty`、不保存场景**。

---

## 4.5 v2 的三类排除 + 两类拒绝（判据与理由）

这一节是 v2 针对 工程A 实测问题加的：薄部位（脚趾/手指/手腕）内向射线穿出身体打中对侧衣物，
被误算成「已穿出」；MA ShapeChanger 的 Delete 顶点还在网格里参与统计。判据都在射线统计之前/之中生效，
计数输出在 `excluded_vertices` 与每件衣物/每个部位的 `rejected_*` 字段。

### 三类排除（`excluded_vertices`，只看身体网格；满足任一即整顶点不参与统计）

| 键 | 判据 | 为什么 |
|---|---|---|
| `nanimated` | 权重最大的骨骼名**或其父链上**含 `NaNimat`（大小写不敏感） | MA ShapeChanger 的 Delete 用 `NaNimation buffer$NaNimatedBone for ...deletedShape.xxx` 把顶点移走；运行时不显示，不能进统计。父链也查是因为实际骨骼名可能是 `Foot_L$NaNimation ...` 这种拼接形式。 |
| `non_finite` | 烘焙后的世界坐标或法线含 `NaN` / `±Infinity` | 这种值参与任何距离/比较都无意义；同时它们不能进 MeshCollider 烘焙（bounds 会 NaN）。 |
| `zero_weight` | 两选一：① 顶点总蒙皮权重 `<= 0`（没有骨骼驱动，不可见）；② 顶点到 `Hips` 的距离 `> 3 m` | ① 是「未蒙皮/被删」的直接表现；② 对应「MA 的 Delete 也可能通过形态键把顶点拉到极远处」——3 m 远大于任何人形身体尺寸（Hips 到脚尖约 0.9 m），只用来抓明显异常，不会误伤正常顶点。字段名沿用任务书。 |

- 权重读不到（网格未开 Read/Write，`weights_source=nearest_bone`）时，第 ① 条无数据，只按 ② 判。
- 优先级：`non_finite` > `nanimated` > `zero_weight`（一个顶点只进一个桶），所以三桶相加 =
  `body_vertex_count - body_vertex_used`。
- 被排除顶点也不进身体 MeshCollider 的三角面（顶点数组里清成 0/up 只为避免 NaN 烘 bounds）。

### 两类拒绝（`rejected_through_body` / `rejected_opposite_normal`，逐件衣物 + 逐部位计数）

1. **`rejected_through_body`**：射线在**衣物命中点之前**先命中了身体网格，`distance < 衣物命中距离`
   且 `> 0.5 mm`（`<= 0.5 mm` 视为起点自命中忽略）。外向、内向都算。
   *理由*：内向射线从薄部位进去，先穿出身体（打到身体对侧内壁），之后才打到衣物——那件衣物在对侧，
   不是「这一侧被顶穿」；旧代码只看法线符号，会把它算成 `pierced`。外向同理：先撞到身体的其它部位
   （腋下、指缝），说明那次衣物命中不是包住该顶点的方向。
2. **`rejected_opposite_normal`**：内向射线命中衣物**正面**、但该命中点的**外法线**与身体顶点法线
   的夹角 `>= 90°`（`dot <= 0`，反向）。
   *理由*：同一侧、真正包住顶点的衣物，其外法线应与身体顶点法线大致同向；反向说明打到的是对侧衣物
   的内表面（正是薄部位误报的形态）。这是身体碰撞体没兜住（例如对侧身体面缺失）时的第二道闸。
   「外法线」用第 6 条标定出的约定（`hit_normal_usable` 时 `hit.normal`，否则 winding 法线 × `winding_sign`）。

两类拒绝都**不计入** `covered`/`pierced`/`coverage`，单独计数；即使该顶点本来就不在覆盖区也会记，
以便回答「为什么这里没被算」。

### 饱和标记

某部位 `p95_depth_mm >= 0.9 * pierce_mm` 时输出 `depth_saturated:true`（`total` 也带一份）。
*理由*：深度顶到射线长度上限说明这个数已经不是真实穿出深度，而是「打到对侧/更远处」的伪命中；
`pierce_mm=15` 时阈值 13.5。看到某个高 `pierce_ratio` 的部位同时 `depth_saturated=true`，
应优先怀疑剩余的误报，而不是直接判定穿模。

### 预期（工程A 默认服装，`body=Body_b`，`pierce_mm=15`）

- 旧结果：`kaguya_cloth/loafer` 脚趾区 `Foot_L$Toe_L$85` pierce_ratio≈0.55、
  `stocking` 的 `Left Hand_Const`≈0.89、`sailor` 的 `Right Hand_Const`≈0.81，且 p95 多在 13.6~15.2。
- v2 预期：这些高比例应**大幅下降**（薄部位射线被 `rejected_through_body` / `rejected_opposite_normal`
  否掉；被删除的 `NaNimation ...deletedShape.*` 部位整片消失、进 `excluded_vertices.nanimated`）。
- 若下降不明显，用输出定位：`rejected_through_body` 大 → 身体碰撞体生效但仍有对侧命中（看是否
  `body` 选错、或该处身体面也确实缺失）；`rejected_opposite_normal` 大 → 身体命中没兜住、靠法线兜底；
  两者都小但 `depth_saturated=true` 多 → 射线长度上限或标定约定可能有问题，先看 `calibration`。

---
