# T2 贴合探针 · v3 覆盖范围、输出、性能 <!-- nav -->

> 旧称：T2（原 `审查/README_T2.md`） §4.6 / §5 / §6。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T2 贴合探针 · 算法与判据（7–10）、v2 排除与拒绝](fit-probe-algorithm-2.md) · 下一页：[T2 贴合探针 · 自检 1：API 签名](fit-probe-selfcheck-api.md) <!-- nav -->

## 4.6 v3 覆盖范围（region scope / `out_of_scope`）

**问题**：`sailor`（水手服上衣）在 RightHand 109 个、RightThumb* 60 个身体顶点上记为 `pierced`——手在
袖口外面，本来就不在上衣覆盖范围内。旧版只要「外向射线打到背面 / 内向射线打到正面」就算覆盖，袖口、
下摆这类悬空几何落进 25 mm 射程就会把手/腿的顶点误算进去；`loafer` pierce_ratio 0.42、`bag` 1.0
大概率同类。

**判据**（对每件衣物，在射线统计之前算一次）：
1. 读该衣物**自己网格**的每顶点主骨骼（权重最大的骨骼；优先 `GetBonesPerVertex/GetAllBoneWeights`，
   退 `Mesh.boneWeights`）。
2. 主骨骼经 §4 第 1.5 条的父链映射归并到部位（与身体顶点同一套映射）。
3. 统计各部位占该衣物顶点数的比例，**占比 ≥ `region_min_share`（默认 0.02）的部位**组成该衣物的
   覆盖部位集合；输出 `coverage_regions`（`region`/`vertices`/`share`）与 `region_source`。
4. 主探测里，身体顶点的部位不在集合里、但射线给出了命中（`covered_inside` 或 `pierced` 至少一个）→
   不计入 `covered`/`pierced`/`rejected_*`，计 `out_of_scope`（逐件 `total.out_of_scope` +
   逐部位 `out_of_scope`，输出保留便于核对）。没有任何命中的顶点不计数（否则每件衣物都会有几万个）。

**取舍**：
- 用衣物自身蒙皮、不用公共包围盒或标签：蒙皮是「这件衣服设计上包住哪里」的直接证据。
- 阈值 2% 挡掉袖口/下摆上极少量被手指骨骼带动的顶点；某件衣物所有部位都 < 阈值时退回「所有出现过的
  部位」并写 `warnings`。
- 衣物部位集合与身体部位集合**完全不相交**（两者父链映射对不上，例如衣物自带一套骨架）时，取消范围
  限制、`region_source="map_mismatch"`，避免把整件衣物清零；`warnings` 会点名。
- 非蒙皮网格（`MeshRenderer` 无骨骼）与网格未开 Read/Write 时判不了，`region_source=no_bones` /
  `unreadable_weights`，同样不限制范围（保持旧行为）。看到这些值就要知道该件的 `covered`/`pierced`
  仍含旧口径的误报。
- `region_min_share` 只影响「哪些部位算覆盖面」，不改变射线的几何判据本身。

---

## 5. 输出

`<out>/geo_<state_id>.json`（**pretty 打印，键序 = 下面的顺序，两次运行逐字节一致**）：

> **v4（任务 AA / 04 T-10）两点变化**：① 输出文件名由 `fit_<state_id>.json` 改为 `geo_<state_id>.json`
> （`03c` L3 的统一命名，T-14 读 `geo_*.json`）；② 请求写 `"poke": true` 或 `"poke": {…}` 时，在
> `params` 之后追加顶层 `poke` 块 = T-28a 静态穿出斑块（外壳有向深度 × 连通斑块面积，主几何判据）。
> 字段、阈值与 Unity 验收见主 `README.md` §3.2.5；T2 既有的距离/脚鞋指标保留，`poke` 是并列的一块。


```json
{
  "avatar": "Kaguya-...",
  "avatar_path": "Kaguya-...",
  "state_id": "default",
  "body_path": "Body",
  "body_vertex_count": 51234,
  "body_vertex_used": 50410,
  "weights_source": "bone_weights",
  "mode": "play",
  "ray_backend": "raycast_command",
  "excluded_vertices": {"nanimated": 780, "non_finite": 0, "zero_weight": 44},
  "region_bone_examples": {"LeftFoot": ["Foot_L$Toe_L$85", "Foot_L_Const", "Toe_L"], "Hips": ["Hips"]},
  "calibration": {"hit_normal_usable": true, "winding_sign": 1, "detail": "..."},
  "params": {},
  "garments": [
    {"path": "Outfit/Skirt", "material_names": ["M_Skirt"], "vertex_count": 8123,
     "skipped": false, "skip_reason": null,
     "region_source": "bone_weights", "region_share_min": 0.02,
     "coverage_regions": [{"region": "Hips", "vertices": 7300, "share": 0.899},
                          {"region": "LeftUpperLeg", "vertices": 400, "share": 0.049}],
     "total": {"covered": 12000, "pierced": 340, "coverage": 12100, "pierce_ratio": 0.0281,
               "max_depth_mm": 6.2, "p95_depth_mm": 4.1, "depth_saturated": false,
               "rejected_through_body": 12, "rejected_opposite_normal": 7, "out_of_scope": 55},
     "regions": [{"region": "Hips", "covered": 900, "pierced": 120, "coverage": 950,
                  "pierce_ratio": 0.1263, "max_depth_mm": 6.2, "p95_depth_mm": 4.4,
                  "depth_saturated": false, "rejected_through_body": 0, "rejected_opposite_normal": 0,
                  "out_of_scope": 0}]}
  ],
  "feet": [
    {"side": "Left", "garment_path": "Outfit/Shoes", "class": "footwear", "class_source": "geometry",
     "class_detail": "脚底下方厚度 p50 >= sole_min_mm", "thickness_p50_mm": 9.3, "thickness_count": 430,
     "foot_verts": 610, "sole_verts": 430,
     "signed_mm": {"p05": -1.2, "p50": 0.8, "p95": 4.0}, "signed_count": 420,
     "below_sole": 18, "floating_gt5mm": 12, "heel_p50_mm": -0.4, "heel_count": 41,
     "toe_pierced": 3, "toe_checked": 60, "shape_keys": {"Foot_Size": 100}},
    {"side": "Left", "garment_path": "Outfit/Socks", "class": "legwear", "class_source": "geometry",
     "class_detail": "脚底下方厚度 p50 < 2mm（贴身）", "thickness_p50_mm": 1.1, "thickness_count": 430,
     "foot_verts": 610, "sole_verts": 430,
     "covered": 430, "pierced": 5, "coverage": 435, "pierce_ratio": 0.0115,
     "gap_avg_mm": 0.9, "gap_count": 430, "shape_keys": {"Foot_Size": 100}}
  ],
  "markers": [{"pos": [0.01, 0.82, -0.03], "region": "Hips", "garment": "Outfit/Skirt",
               "depth_mm": 6.2, "vertex": 12345}],
  "body_candidates": [
    {"path": "Body", "vertex_count": 51234, "has_foot": true, "has_torso": true,
     "selected": true, "regions": ["Chest", "Head", "Hips", "LeftFoot", "LeftLowerLeg", "Spine"]}
  ],
  "warnings": [],
  "timings_ms": {"bake_body": 40.1, "bake_garments": 380.5}
}
```

- `params` 是请求对象原样嵌入（示例里省略内容用了 `{}`）。真实运行时它是完整请求。
- `excluded_vertices` / `body_vertex_used` / `region_bone_examples` 与每处
  `rejected_*` / `depth_saturated`、`coverage`、`signed_count`、`toe_checked`、`foot_verts`、`sole_verts`、
  `body_candidates`、`warnings`、`calibration`、`weights_source`、`mode`、`ray_backend`
  是任务书之外的**诊断附加字段**；判据见 4.5。
- **v3 新增字段**：每件衣物 `region_source` / `region_share_min` / `coverage_regions` 与
  `total.out_of_scope`、每个部位 `out_of_scope`（判据见 §4.6）；每条 `feet[]`
  `class` / `class_source` / `class_detail` / `thickness_p50_mm` / `thickness_count`（判据见 §4 第 7 条）。
- **`feet[]` 结构 v3 变了**：v2 是「每只脚一条、只报一件覆盖最多的衣物、只报鞋底指标」；v3 是
  「每只脚 × 每件覆盖该脚的衣物各一条」。`class=footwear` 的条目有 `signed_mm`/`below_sole`/
  `floating_gt5mm`/`heel_*`/`toe_*`；`class=legwear|other` 的条目**没有**这些鞋底字段，只有
  `covered`/`pierced`/`coverage`/`pierce_ratio`/`gap_avg_mm`/`gap_count`。消费方按 `class` 分支读。
- `thickness_p50_mm` 在几何无数据时是 `null`（JSON `null`）。
- `body_candidates` v2 是对象数组（`path` / `vertex_count` / `has_foot` / `has_torso` / `selected` / `regions`），
  旧版是字符串数组。
- `skipped=true` 的衣物（不可见 / 网格未开 Read/Write）其 `total` 全 0、`regions` 为空，
  `skip_reason` 说明原因。
- `status.json` 由 AuditIO 的 `AuditStatus` 统一写（含 `tool`/`time`）；运行中 T2 逐件更新
  `progress="3/10"`、`message=衣物路径`。
- **不标记 / 不保存场景**（Play 模式下的临时改动退出 Play 即丢）。

---

## 6. 性能预估（估算，非实测）

- 身体 10 万顶点、衣物 10 件 → 主探测 `2 × 10万 × 10 = 200 万` 条射线，另加 v2 身体命中
  `2 × 10万 = 20 万` 条（只算一次），Play 模式下 `RaycastCommand.ScheduleBatch` 按 32 条/作业并行。
  整轮（含 11 个 MeshCollider 烹饪 + 10 次 BakeMesh）**约 5~25 秒**；大头是射线与 collider 烹饪。
  身体是非凸 MeshCollider，烹饪稍贵，但只建一次。
- 非 Play 模式（若把 `RequiresPlayMode` 改成 false 或直接调 Probe）退回逐条 `Physics.Raycast`，
  同样规模 **约 1~3 分钟**。所以本工具要求 Play 模式。
- v3 追加的开销：脚底厚度用逐条 `Physics.RaycastNonAlloc`（脚底顶点数 × 2 侧 × 衣物件数，工程A
  约 `645 × 2 × 10 ≈ 1.3 万` 条，个别衣物补一轮向上的射线），相对主探测可忽略（< 1 秒量级）；
  衣物蒙皮部位统计是每件一次线性扫描。
- 内存：临时数组约 `O(2 × 顶点数)`（10 万顶点约 20~25 MB），加上身体碰撞体的一份顶点/法线拷贝
  （约 `2 × 顶点数 × 12 B`）；每件衣物用完即释放；Play 模式本身的 10 GB+ 占用与本工具无关。

---
