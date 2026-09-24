# 探针 poke（静态穿出斑块）· 判据、请求与输出 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.5 前段。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 containment 命中数口径 · 探针 range](probe-containment-crossing.md) · 下一页：[探针 poke · 命中数与面积门槛口径、Unity 验收](probe-poke-area.md) <!-- nav -->

#### 3.2.5 `poke`——T-28a 静态穿出斑块（几何 v4 主判据，任务 AA / 04 T-10）

**为什么换判据**（`工程C/_施工记录.md` 19:05/21:30、`03 §8.2`）：包含率被厂商 Delete 删顶点
与开口款拉低（LUNALICE 9%/19% 却无穿模）；穿越计数是**边**级统计，贴身靴正常状态几百条擦边而脚趾整段出靴
反而 0 条（Winter 负样本 脚趾 199/202 条、`Toe_heels=0` 后 0 条）。所以主判据换成「外壳有向深度 × 连通
斑块面积」，穿越计数与包含率降为**参考列**（不判）。

- **配对**：只来自声明 `covers`（请求 `poke_covers:[{garment,covers:[…]}]`，或 `poke_decl` 指向
  `decl.json` 的 `parts[].covers`；`objects[]` 兼容字符串与 `{path,renderer}` 对象，**每个 object 各配一条**，
  任务 CI 修复）。无声明时退回渲染器
  GameObject 名关键词（鞋/靴/手套）并标 `pair_confidence=low`。**被测件与部位包围盒在任一轴上不重叠即
  拒绝配对**（`bbox_overlap=false`，PixelBoot 83×6 假命中的教训）。`foot`/`hand` 会展开成所有具体身体部位
  （`LeftFoot`/`LeftToes`…）。
- **① 外壳三角形**：只对活跃头像根下的衣物建临时 `MeshCollider`（身体与其它根**不建**），层 `poke_layer`
  （默认 30），`queriesHitBackfaces=true`。每三角形外向 = 「质心 − 到该覆盖区锚骨线段的最近点」（脚用
  `Foot→Toes`、手用 `Hand→MiddleProximal`、其余父→本骨）；绕序法线与外向相反者计 `normals_flipped`，
  并按外向翻正后供伪法线使用（不信网格法线朝向）。从质心沿外向 +`origin_mm`（默认 1 mm）起发 5 条射线
  （外向与 ±`cone_deg`=20° 锥），**任一条**在 `shell_ray_m`（默认 0.5 m）内不打到本根衣物三角形即外壳。
  内衬、被外套盖住的上衣、袖筒内壁因此不算外壳——身体只顶穿内层但没露出来不是缺陷。
  （任务 CI：这三处判定都可请求切换 —— `poke_shell_rule` = `any`(默认)/`outward`/`majority`、
  `poke_normal_sign` = `parity`(默认，09-20 起)/`anchor`/`winding`，`poke_diag` 出逐顶点证据。**09-20 Claude 实测改默认**：`anchor` 在工程C Winter 靴（正常态 19.1 cm²、Toe_heels=0 仅 2.67）与 工程A 水手服（默认态 82.6 cm²、剂量反向）都判错；`parity` 下 Winter 正常态 0 / Toe_heels=0 61.3、MMN `=100` 0 / `=0` 5.63，标定通过；水手服降到 33.4 cm²（2 斑块，剂量近乎平，疑为同件蝴蝶结下的自遮挡，已知局限）；`winding` 在水手服更差（138.7）。原文：默认保持旧行为，
  上衣假阳性的诊断与修法见 §3.2.5.1。）
- **② 有向深度 d_v**：被覆盖部位每个可用身体顶点（剔除码同 `containment`：NaN/NaNimation 删除/零权重/
  超 3 m）到最近**外壳**特征（面/边/顶点分类，自建 BVH 最近点）的距离，符号 = `dot(v − p, n_pseudo)`，
  `n_pseudo` 为**角度加权伪法线**（面用定向法线、边用相邻定向法线和、顶点用角度加权和）。最近特征是
  **边界边**（只被 1 个三角面引用：靴口/裙摆/袖口）记 `opening`，不算穿出；`opening` 顶点 `d > 3τ` 另记
  `opening_deep`（advisory，防袖壁大角度漏报）。τ 初值：躯干（Hips/Spine/Chest/UpperChest）`tau_torso_mm`=2、
  其它 `tau_limb_mm`=3；**先量后定**，见下面验收。
- **③ 斑块**：身体网格邻接图上 `d_v > τ` 的连通分量（union-find）；面积 = 该分量内身体三角形面积和（cm²，
  与顶点密度无关），报 `max/avg/min_depth_mm`、`region`、`sub_part`、`anchor_local_centroid`、`cams`（2 机位：
  `normal_back`＝质心沿法线反向 0.35 m、`three_quarter`，fov 30）。`sub_part` 把脚细分：`LeftToes`→`toe`；
  `LeftFoot` 按 `Foot→Toes` 轴参数 t 分 `ball`(t>0.55)/`arch`/`ankle`(t<0.15)；手→`hand`。
- **⑦ Delete/NaN**：`body_excluded{nan,deleted,deleted_nanimated,deleted_zero_weight,beyond_3m,total}` 单独计。
- **剂量分档**：请求 `poke_doses:[100,75,50,25,0]` + `poke_perturb:{renderer,blendshape}`（或顶层
  `perturb:{renderer,blendshape,doses:[…]}`）：逐档设形态键、重算斑块，输出 `dose_response[{dose,
  total_patch_area_cm2,patch_count,opening_verts,opening_deep_verts}]` 与 `monotone_nondecreasing`（按剂量
  升序总面积不下降）/`monotonicity`。
- **hide 自检**：`poke_hide`（渲染器路径或叶子名）隐藏后该件不应再进配对；输出
  `hide_selfcheck{path,found,garment_paired_after_hide,hidden_garment_patch_area_cm2,total_patch_area_cm2,ok}`。
- **参考列**：`poke_reference=true`（默认 false，省一次重活）时，内嵌同一配对上的既有 `containment`
  读数到每对的 `reference{inside,inside_ratio,crossing_edges,crossing_ratio,max_crossing_depth_mm}`。
  不内嵌时，把这支探针与 `containment` 一起请求（`probes:["containment","poke"]`）由调用方合并。
  穿越/包含率**不参与判定**。

请求（顶层 `poke_*` 或嵌套 `poke:{}` 二选一，嵌套优先）：`poke_min_patch_cm2`(0.5)、`poke_tau_torso_mm`(2)、
`poke_tau_limb_mm`(3)、`poke_shell_ray_m`(0.5)、`poke_cone_deg`(20)、`poke_origin_mm`(1)、
`poke_opening_deep_factor`(3)、`poke_reference`(false)、`poke_max_patches`(500)、`poke_layer`(30)、
`poke_hide`、`poke_include`/`poke_exclude`（默认排除发/脸/眼/头/粒子等）、`poke_region_min_share`、
`poke_decl`、`poke_covers`、`poke_doses`、`poke_perturb`、`poke_ray_budget`(3e6)。
任务 CI 新增：`poke_diag`(false)、`poke_shell_rule`("any"/"outward"/"majority")、`poke_shell_majority_min`(3)、
`poke_normal_sign`("anchor"/"winding"/"parity")。
任务 CW 新增：`poke_min_patch_rule`("adaptive"/"legacy")、`poke_min_verts_for_patch`(8)、
`poke_absolute_floor_cm2`(0.05)、`poke_min_patch_area_cm2`（显式覆盖；旧 `poke_min_patch_cm2` 仍认）。
详见 §3.2.5.2 与下面的 `patch_rule`。

`probes.poke` 字段：`method`、`thresholds{…}`、`pair_rule`、`shell_rule`、`depth_rule`、`patch_rule`、
`reference_rule`、`dose_rule`、`body`/`body_source`（身体识别与 T-05/T2 共用 `AuditBodyPick`：名字候选
`Body_b`/`Body_base`/`Body` 过「脚+躯干蒙皮权重」关，再退几何启发；任务 AY / K19）、`body_excluded{…}`、
`body_baked_vertices`、
`body_shared_vertices`、`body_region_source`、`garment_candidates[{garment,name,vertices,triangles}]`、
`rays_used`、`truncated`、`diag_rule`、`pairs[{garment,garment_name,pair_source,pair_confidence,pair_reason,bbox_overlap,
covers_regions,mesh_vertices,mesh_triangles,shell_faces,normals_flipped,normals_flipped_ratio,
shell_rule,shell_majority_min,normal_sign,shell_outward_escaped,shell_rescued_by_cone,shell_rescued_ratio,opening_verts,
opening_deep_verts,d_v_mm{p50,p95,p99,max,min,mean,count,outside},by_region[{region,coarse_part,
body_region_verts_total,excluded{…},d_v_mm{…},opening,opening_deep,patch_count,total_patch_area_cm2}],
by_sub_part[{sub_part,d_v_mm{…},opening,patch_count,total_patch_area_cm2,suspect_subthreshold,suspect_reason?}],
area_per_vert_cm2,area_per_vert_pos_source,region_verts,region_area_cm2,min_patch_area_cm2,min_patch_area_source,
dropped_components,dropped_max_area_cm2,dropped_total_area_cm2,dropped_max_depth_mm,suspect_subthreshold,
patches[{area_cm2,max_depth_mm,avg_depth_mm,min_depth_mm,verts,
region,sub_part,anchor_local_centroid{x,y,z},cams[{id,pos,look_at,dist_m,fov}],
diag[{world{x,y,z},d_v_mm,nearest_feature,nearest_feature_code,nearest_face,garment,tri_index,shell_ray,
shell_ray_kind,shell_ray_end{x,y,z},winding_dot_outward,normals_flipped,nearest_face_cone_rescued,opening,
pseudo_normal{x,y,z},inside_by_parity?,parity_agree_axes?}]（仅 poke.diag=true）}],patch_count,
total_patch_area_cm2,reference{…}}]`、`dose_response`（可选）、`monotone_nondecreasing`/`monotonicity`（可选）、
`hide_selfcheck`（可选）、`shell_faces_total`、`normals_flipped_total`、`patch_count`、
`total_patch_area_cm2`、`opening_verts`、`opening_deep_verts`、`hits`。
