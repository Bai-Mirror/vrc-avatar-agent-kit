# 探针 containment（包含率） <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.3 前半。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1 纯数据探针总览 · grab_chain / coincident](probes.md) · 下一页：[探针 containment 命中数口径 · 探针 range](probe-containment-crossing.md) <!-- nav -->

#### 3.2.3 `containment`——封闭件把身体部位包住没有 / 身体有没有穿越衣物表面

对应厂商只在袜子上挂 `Foot_heel_OFF`、却让鞋在袜关时脚回高跟姿态、脚趾整段穿出包趾鞋头的缺陷。
T2 的「身体顶点沿法线找衣物表面」有结构性盲区（脚趾离鞋面有距离），最初改用**包含测试**；
2026-09-18 工程C实测发现包含率会被「厂商 Delete 掉鞋内顶点」「开口 / 不水密网格」两类情况拉低而与穿模无关，
所以任务 U 再把判据换成**表面穿越计数**（见下），包含率降级为参考字段。

- **配对**：请求 `containment_pairs`，缺省自动取可见、**只看渲染器所在 GameObject 的名字**、按 token 命中
  鞋/手套关键词的渲染器。匹配规则对齐 `t5_shapekey_matrix.py` 的 `match_any`：名字按「驼峰 / 下划线 /
  空格 / 括号」切成 token，ASCII 关键词按完整 token 匹配（长度 ≥4 允许 token 以关键词为前缀，`Shoes`→`shoe`、
  `Boots`→`boot`、`Gloves`→`glove`），CJK（`靴`/`鞋`/`手袋`）按子串。**故意不拿层级路径**：路径里祖先名会把
  子物体误配（工程A 发饰 `Acc_发饰_PixelBoot/.../multi-window/windowA` 的抓屏窗口曾被当靴子：`windowA`–`E`
  各 83 个状态、`final-window` 56 个状态，每个状态假命中 LeftFoot/RightFoot 两个部位，把命中总数抬到 1160）。
  命中手套关键词归 `hand`，否则归 `foot`。每条配对输出
  `pair_source`（`request`|`name_token`）、`pair_matched_token`（命中的词）与 `pair_region_source`；显式
  `containment_pairs` 里没写 `region` 的，也用该渲染器 GameObject 名按同一规则推断，推不出才跳过。
- **部位**：身体网格（`body` 或自动识别）每个顶点的**主蒙皮权重骨骼**沿父链上溯到最近的人形部位；
  **权重从 `sharedMesh` 读，不从 `BakeMesh` 产物读**（烘焙网格是静态快照、不保证带可用 bone weight，读到空
  权重会静默退化到「按世界坐标找最近骨骼」，部位随姿势漂移；此口径与 T2 一致）。脚拆成 **`Foot`（Foot 骨）
  与 `Toes`（Toe 骨及其子骨）各自统计**，手按 `Hand` 与 `Thumb/Index/Middle/Ring/Little` 指节。每个区域
  输出它用到的骨骼名 `region_bones`（沿父链归并后的主骨骼 Transform 名，已去重升序）。
- **顶点数随状态变化**：`body_region_verts_total` = 该区域在身体网格里的**原始顶点总数**，只由身体网格与
  蒙皮权重决定，**不随状态变**；`verts` = 实际参与射线测试的数；`excluded` = 被剔掉的部分及原因
  （`nan` 非有限坐标；`deleted` = 权重为 0，或主骨骼及其父链含 `NaNimat`；`beyond_3m` = 离 Hips 超过 3 m）。
  关系：`verts = body_region_verts_total - excluded.total`。顶层另有 `body_excluded`（整具身体的分项）、
  `body_region_source`（`bone_weights`|`bone_weights_legacy`|`nearest_bone`）、`body_shared_vertices` /
  `body_baked_vertices`。
  **为什么单列**：工程A 的 `Body_b` 用 MA ShapeChanger 按袜子状态（工程里可见
  `Property Overlay controlled by socks VertexFilterByShape: toe_/toe_short_/foot_/ankle_`、骨骼
  `.../Foot_L/NaNimation buffer/NaNimatedBone for Body_b (...).deletedShape.toe_`）把脚/趾顶点用
  NaNimation 移走；袜开时脚趾被删。旧版只把「坐标有限」当可用、其余**静默丢弃**也不报告，于是同一只脚
  `LeftFoot` 在 3222（袜关）与 2033（袜开）之间跳。现在总量恒定，差额进 `excluded.deleted_nanimated`。
- **在外顶点定位**：每个区域额外给 `outside_centroid_local`（在外顶点转到**该区域锚骨**局部系的坐标均值，米；
  没在外顶点时为 `null`）与 `outside_extent`（在外点包围盒尺寸），用来分辨是脚尖、脚跟还是脚背露在外面。
  锚骨取该部位对应的 `HumanBodyBones`（`LeftToes` 取 Toe 骨），取不到退回头像/身体根；骨骼带非单位缩放时
  该局部坐标不是严格米。
- 衣物烘焙网格转世界坐标后建**临时 MeshCollider**（临时 layer，`Physics.queriesHitBackfaces=true`，结束恢复并销毁）；
- **穿越计数（任务 U，判据）**：取该区域可用的三角形边（两端都 `ExOk`、同区域、共享边只算一次），
  对每条边 **A→B 与 B→A 各做一次线段射线**（`Physics.Raycast` 限长 = 边长，`queriesHitBackfaces=true`），
  任一方向命中该衣物即记一条**穿越边**。区域判据 = **`crossing_edges ≥ containment_min_crossings`（默认 20）
  且 `crossing_ratio ≥ containment_min_crossing_ratio`（默认 0.01）**。
- 每个区域输出 `edges`（可测边总数）、`crossing_edges`、`crossing_ratio`；
  `crossing_midpoint_local`（穿越边中点转到区域锚骨局部系的均值，米）与 `crossing_extent`（中点包围盒尺寸）
  用来定位穿越发生在脚尖 / 脚跟 / 脚背；`max_crossing_depth_mm` 是**穿出深度**（mm）：穿越边里判在外的
  端点到命中面料点的距离，两端都判在外时取两端较小值（贴身擦边），两端都判在内记 0。
- 包含率（**参考字段，不再参与 flagged**）：每个目标身体顶点向 **±X ±Y ±Z 六方向做迭代射线计交点**，
  命中后从命中点沿方向前进 `1e-4 m` 再射、单方向最多 30 次；单方向交点数为奇数记 1 票，**≥4 票判为在内**；
  输出 `verts / inside / inside_ratio`。它仍是「这个区域有多少身体顶点在衣物内」的直观读数，只是不再当穿模判据。
- **为什么把判据从包含率换成穿越**（2026-09-18 工程C实测）：厂商 MA ShapeChanger 用 NaNimation **Delete**
  删掉鞋里的脚部顶点后，剩下的身体顶点都在鞋外，`inside_ratio` 天然只有个位数（LUNALICE 9%/19%，
  人工与 agy 看图都判无穿模）；开口款（浅口 / 露趾 / 绑带）与不水密的鞋网格同理天然偏低
  （Silent Twilight 鞋 3–6%，看图无穿模）。真穿模（工程A MMN 光脚穿鞋、脚趾穿破封闭鞋头）是
  **身体表面与鞋面相交**，一定会让该区域的三角形边命中鞋面。
- **阈值取舍（为什么 20 条边 + 1%）**：两条门互补——`20 条`挡住零散 / 单三角形级别的擦边误差
  （数值共面、一个顶点恰好压线会造成 2–4 条边命中）；`1%` 挡住大区域里少量擦边被绝对数放大
  （脚部区域约 3000–6000 条边，1% ≈ 30–60 条，与 20 条同量级）。**贴身件（袜子、紧身衣）的擦边误差**
  表现为个位数到十几条穿越边，低于 20 条不判；**开口件不受影响**：身体是从网格的**开口**穿过去的，
  开口处没有面，线段不会与面料相交，`crossing_edges` 通常为 0；只有身体压到开口边沿的实体面料时才计。
- **`open_mesh_suspect` = 衣物网格的边界边（只被 1 个三角面引用）占比**，`nonmanifold_edge_ratio` =
  被 >2 个三角面引用的边占比。这两个数字仍输出，但只作「这双鞋是不是开口件」的提示，不参与判定。

`probes.containment` 字段：`method`、`pair_rule`、`region_rule`、`crossing_rule`、`flag_rule`、
`inside_votes_threshold`(4)、`ray_iter_max`(30)、`ray_advance_m`、`min_region_verts`、`min_ratio`(0.5，参考)、
`min_crossings`(20)、`min_crossing_ratio`(0.01)、`ray_budget`、`body`、`body_source`、`body_shared_vertices`、
`body_baked_vertices`、`body_region_source`、`body_max_distance_m`、`body_excluded{nan,deleted,
deleted_nanimated,deleted_zero_weight,beyond_3m,total}`、`rays_used`、`truncated`、
`pairs[{garment,garment_name,body,region_filter,pair_source,pair_matched_token,pair_region_source,mesh_vertices,
mesh_triangles,open_mesh_suspect,nonmanifold_edge_ratio,verts,inside,inside_ratio,edges,crossing_edges,
crossing_ratio,by_region[{region,region_bones,body_region_verts_total,excluded{nan,deleted,deleted_nanimated,
deleted_zero_weight,beyond_3m,total},verts,inside,inside_ratio,edges,crossing_edges,crossing_ratio,
max_crossing_depth_mm,crossing_midpoint_local,crossing_extent,flagged,flag_basis,outside_centroid_local,
outside_extent}],hits,note?}]`、`hits`。
