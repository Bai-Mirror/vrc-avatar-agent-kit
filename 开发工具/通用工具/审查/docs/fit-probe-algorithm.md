# T2 贴合探针 · 算法与判据（1–6） <!-- nav -->

> 旧称：T2（原 `审查/README_T2.md`） §4 前半。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T2 贴合探针 AuditFitProbe · 部署、分派、请求](fit-probe.md) · 下一页：[T2 贴合探针 · 算法与判据（7–10）、v2 排除与拒绝](fit-probe-algorithm-2.md) <!-- nav -->

## 4. 算法与判据（为什么这么判）

1. **定身体**（`body=auto`，v4 起改走共享判据 `AuditBodyPick`，任务 AY）：
   - 先建立人形骨骼集合 `{ GetBoneTransform(全部 HumanBodyBones) }`（第 1.5 条的部位映射基础）。
   - **名字候选**（大小写不敏感：`Body_b` / `Body_base` / `Body`）里优先选**蒙皮权重同时覆盖脚与躯干**
     的那个：把候选每根骨骼映射成人形部位，脚的份额与躯干的份额都要 ≥ 0.1%（`GetBonesPerVertex`/`GetAllBoneWeights`，
     退 `Mesh.boneWeights`）；多个满足取顶点最多。
   - 名字都不满足（网格不可读等）再退几何启发：候选 `bones[]` 的部位集合**同时**含 `LeftFoot` 或
     `LeftLowerLeg`，且含 `Chest` 或 `Spine`，取顶点最多者。
   - 全部可见候选（含不合格的）连同 `regions` / `vertex_count` / `has_foot` / `has_torso` / `selected`
     写进输出 `body_candidates` 供核对；选错时用 `body` 显式指定。
   - *为什么再改*：v2 只按「部位集合 + 顶点最多」在 Kipfel 素体上会把脸网格 `Body`（顶点比真身体
     `Body_Base` 还多、权重全在 Head/眼）当成身体。T-05 部件盘点、T-10 poke、T2 三处现在共用
     `AuditBodyPick.FindBodySmr`，不再各修各的（AM 教训 1 遗留的 K20）。
   - *为什么 v2 就不精确匹配骨骼 Transform*：Play 模式下 MA/AAO 会插入 `Head_Const`、把骨骼合并成
     `Foot_L$Toe_L$85`，`SMR.bones` 里往往找不到与 `GetBoneTransform` 完全相同的 Transform。
1.5. **部位映射**（v2）：对每个骨骼 Transform，沿父链向上走，遇到的**第一个**人形骨骼
   （`HumanBodyBones` 集合里的）名即该顶点的部位；走到头像根还没遇到记 `Other`；没有 Humanoid
   Animator 时退化为骨骼原名（保持可用）。结果按 Transform 缓存。输出 `region_bone_examples`
   给每个部位列最多 3 个原始骨骼名，用来核对映射。*为什么*：`Foot_L$Toe_L$85`、`Head_Const` 这类
   中间骨骼的父链最终能上溯到 `Foot_L` / `Head`，于是脚趾顶点能正确归到 `LeftFoot/LeftToes`，
   脚部专项不会再报「covered=0」。
2. **衣物候选**：头像下所有 `activeInHierarchy && enabled` 的 SMR / MeshRenderer，排除身体本身与
   名字匹配 `exclude_name_regex` 者；v2 再用 `include_only`（若非空）只留下匹配的。**先收集、后应用
   `hide`**，这样被 hide 的衣物仍出现在结果里、数值为 0，便于「隐藏后 covered 必须为 0」的自检。
3. **烘焙当前姿势**：SMR 用 `BakeMesh(mesh, true)`，再用 `renderer.transform.localToWorldMatrix`
   把顶点/法线变到世界；MeshRenderer 用 `MeshFilter.sharedMesh` + 同一矩阵。
   *为什么 `useScale=true` 还要乘 `localToWorldMatrix`*：官方文档（2023.2 英文）写明 `useScale`
   是 “compensate for the SMR Transform scale”，位置/旋转始终补偿到局部空间；所以烘焙结果是
   **已去掉 SMR 缩放的局部坐标**，再乘完整 `localToWorldMatrix` 正好得到世界坐标，不会二次缩放。
4. **射线目标**：每件衣物一个临时 GameObject（layer 30），身体一个临时 GameObject（layer 29），
   都挂非凸 `MeshCollider`、`HideFlags.HideAndDontSave`，`sharedMesh` 为世界坐标网格（临时物体自身为
   单位变换）。`Physics.SyncTransforms()` 后逐件启用衣物；身体碰撞体整轮启用。两次查询各用一个 mask：
   衣物问 `1<<30`、身体问 `1<<29`。
   *为什么用独立 layer*：避免打到场景里的 PhysBone Collider 等；若头像自己已有 layer 29/30 的碰撞体，
   输出的 `warnings` 会提示。
5. **逐身体顶点**（`v`、`n`，米；结果毫米）：先排除三类无效顶点（见 4.5），只对保留顶点打射线。
   - 外向：`v + n*0.5mm` 沿 `n`，长 `cover_mm`。命中且是**衣物背面** → `covered_inside`（身体在衣物里）。
   - 内向：`v - n*0.5mm` 沿 `-n`，长 `pierce_mm`。命中且是**衣物正面** → `pierced`（衣物表面在顶点里面，
     即顶点已穿出），深度 `= 命中距离 + 0.5mm`（补回起点偏移，从身体顶点量起）；`< min_depth_mm` 不计。
   - v2 两类拒绝（见 4.5）：任一方向**在衣物命中之前先命中身体** → 该次不算，计 `rejected_through_body`；
     内向命中正面但衣物法线与身体顶点法线**反向** → 不算，计 `rejected_opposite_normal`。
   - **v3 覆盖范围过滤（先于覆盖区统计）**：按 §4.6 得到的「该衣物覆盖部位集合」，身体顶点部位不在集合里
     的命中不计入 `covered`/`pierced`/`rejected_*`，改记 `out_of_scope`（逐件 `total` 与逐部位都输出）。
   - **覆盖区 = covered_inside ∪ pierced**；只统计覆盖区内的顶点。`covered` = covered_inside 数，
     `coverage` = 并集数，`pierce_ratio = pierced / coverage`；拒绝数不计入 `coverage`，单独输出。
   - `pierced` 的深度进 `max_depth_mm` 与 `p95_depth_mm`（线性插值分位数）；`p95_depth_mm >= 0.9*pierce_mm`
     时该部位标 `depth_saturated:true`（见 4.5 第 3 条）。
   - 部位按 1.5 的父链映射。权重优先 `GetBonesPerVertex/GetAllBoneWeights`（每顶点已按权重降序），
     退回 `Mesh.boneWeights`；都读不到（网格未开 Read/Write）时用**最近骨骼**近似，并在
     `weights_source` 标 `nearest_bone`、`warnings` 说明。
6. **正面/背面怎么判**：优先 `dot(射线方向, hit.normal)` 的符号（与任务书一致）。但 Unity 在
   `queriesHitBackfaces=true` 时 `hit.normal` 是否被翻向射线、叉乘 winding 与正面的对应，版本间不保证；
   符号一旦反了会得到「全 0」的静默错误。所以首部做一次**标定**（`Calibrate`）：自建一块四边形，
   先关背面命中确定正面在叉乘法线的哪一侧（定 `winding_sign`），再开背面命中看 `hit.normal` 是否指向正面
   （定 `hit_normal_usable`）。标定失败才退回任务书默认。结果写进输出的 `calibration`。
   4.5 的「同向法线」判据用的也是这套标定后的外法线。
