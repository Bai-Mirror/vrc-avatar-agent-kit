# 探针 shrink_cover · 输出、诊断、自检与标定 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.8 后段。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 shrink_cover · 判据改版记录（CU / CX / CT）](probe-shrink-cover-rule.md) · 下一页：[T1 · 版本戳、状态回读断言、档位槽号、哨兵、sequence/history](state-driver-readback.md) <!-- nav -->

**输出**：完整结果写 `<out>/shrink_cover_<stateId>.json`（repeat 遍写 `.repeat.json`），
同目录 `state_<id>.json` 顶层 `shrink_cover` 是精简行（`probes.shrink_cover` 里也有一份完整对象）。
完整结果 `keys[]` 每键：

```json
{ "key": "Foot_heel_OFF_...", "weight": 100, "affected_verts": 812, "affected_verts_raw": 900,
  "covered_verts": 120, "ray_covered_verts": 96, "cover_criterion": "outward_ray(any)",
  "uncovered_ratio": 0.85, "uncovered_area_cm2": 41.2,
  "nearest_cover_path": "_Outfit/.../Socks", "nearest_cover_dist_mm": 1.2, "covered_near_ratio": 0.78,
  "covered_by_ray_top": [ {"path": "_Outfit/.../Socks", "leaf": "Socks", "hit_verts": 96} ],
  "covered_by_top": [ {"path": "_Outfit/.../Socks", "leaf": "Socks", "covered_verts": 118} ],
  "cover_by": { "_Outfit/.../Shoes": 80 }, "verdict": "uncovered",
  "verdict_rule": "or", "verdict_by": "area", "ratio_ok": false, "area_ok": true }
```

`verdict`：`uncovered`（由 `verdict_rule` 决定：`or` = `uncovered_ratio ≥ ratio_thr` **或** `uncovered_area_cm2 ≥ area_thr`；
`and` = 两者都要；`ratio_only` / `area_only` = 只看其中一边）/ `ok` / `too_few_verts` / `key_missing`
（键在身体网格上匹配不到，附 `error`）/ `undecidable`（`self_check.suspicious` 时，见下；**不给 `uncovered`**）。
每行附 `verdict_rule` / `ratio_ok` / `area_ok` / `verdict_by`（`ratio`/`area`/`both`/`none`）。
`covered_verts` / `uncovered_ratio` / `uncovered_area_cm2` 按**本次 `cover_rule`** 统计（默认外向射线）；
`uncovered_area_cm2` = 未遮挡影响顶点的三角形面积份额之和（每个身体三角形按顶点均分面积，只累加受影响且未遮挡的份额）；
`ray_covered_verts` = 射线口径盖住的顶点数，`cover_criterion` = 本行实际用的口径；
`nearest_cover_path` / `nearest_cover_dist_mm` / `covered_near_ratio` = 旧距离口径的参考列（不参与默认 verdict）；
`covered_by_ray_top` = 外向射线命中的前 3 件（按被该件作为最近命中件的顶点数降序，`hit_verts` 为命中顶点数，`[]` 表示射线一件都没打到）；
`covered_by_top` = 旧距离口径的前 3 件；`hits` = `uncovered` 的键数。

**诊断 `diagnostics`（任务 CV，`diag:true` 才有；只读，不改 verdict 与默认阈值）**：
回答「verdict 说被遮住，但渲图里却裸露」这类数据与眼睛对不上的问题。请求示例：

```json
{
  "probes": ["shrink_cover"],
  "shrink_cover": {
    "body": "Body_base", "keys": ["auto_nonzero"],
    "cover_rule": "outward_ray", "cover_ray_mm": 50, "cone_deg": 20, "ray_vote": "any",
    "diag": true, "diag_keys": ["Ankle"], "diag_samples": 50,
    "diag_eps_mm": [0.5, 0.2, 0.1, 0.05], "diag_max_keys": 4
  }
}
```

输出 `diagnostics.keys[]` 每键：
- `bbox_mm` / `ray_covered_verts` / `ray_uncovered_ratio` / `bone_groups[]` / `region_groups[]`：A(K) 的**世界包围盒**
  （`min_mm`/`max_mm`/`size_mm`/`center_mm`）、外向射线口径遮住/未遮住计数，以及按**主蒙皮骨骼 Transform 名**
  （`LeftFoot`/`LeftToes`/`LeftLowerLeg`…）和**人形部位**（`Foot`/`Toes`/`LowerLeg`…）分组的 `verts` 与
  `ray_uncovered`（各组里外向射线没遮住的顶点数）—— 用来判断这个键到底影响脚踝那一圈还是整条小腿；
- `sample_count` / `samples[]`：≤ `diag_samples` 个等距抽样顶点，每个记 `vert`、`world_mm`、`delta_mm`、
  `outward_normal`、`bone`、`region`；
- `samples[].rays[]`：中轴 `dir=0` + 4 条锥向 `dir=1..4` 的**逐条**结果 `{dir, kind, hit, path, leaf, dist_mm}`。
  与生产判定不同，这里 5 条**全发**（生产 `any` 命中即停），且命中件取「到全部可见服装的最近命中」，
  所以能看出到底是哪一件、在多远处把这条射线挡下的；
- `sample_hit_by_leaf_axis` / `sample_hit_by_leaf_any`：抽样顶点里，中轴 / 任一方向命中的叶子件计数 ——
  直接回答「92.8% 的『外面有布』是哪个件」；
- `eps_sweep[]`：`diag_eps_mm` 各档的 `affected_verts` / `affected_verts_raw`（只计数，不改默认 `eps_delta_mm`）。

`diagnostics.rays_used` 是诊断独立消耗的射线方向数，`diagnostics.keys_truncated` 表示键数被 `diag_max_keys` 截断。
诊断复用主探针已经烘好的身体网格与服装 BVH，不额外建 collider，也不参与 `self_check`。

**`self_check`（任务 CT：探针自己否定自己）**：顶层与 `compact` 都有。
任一成立 → `suspicious=true`、`reason` 写中文「遮挡集合可能被排除规则吃掉了，结论不可信：…」，
并把**所有行** verdict 改 `undecidable`、`hits=0`：
`garments_used == 0`；`keys_resolved` 为空；所有键都 `uncovered`；`garments_used / garments_considered < 0.2`。
附带 `garments_considered`（可见 SMR 总数）/ `garments_used`（进集合数）/ `keys_total` / `keys_uncovered` / `used_ratio`。
`garments_excluded[]` 逐件记 `{path, leaf, rule, hit?}`，`rule` = `body_self` / `body_family` / `exclude_regex`（`hit` 是命中的整名或词）。

几何口径：A(K) 的 delta 取 blendshape **frame 最后一帧**（按该帧权重归一化到 100%）乘 `lossyScale`；
顶点世界坐标取当前姿势的 `BakeMesh`（直接复用 `BuildBodyInfo`，与 `containment`/`poke` 同一烘焙与剔除）。

**离线自检（任务 CT/CU，不起 Unity）**：

```
python3 开发工具/通用工具/审查/perception/selftest_shrink_cover.py
```

把 `AuditProbes.cs` 里 `SHRINK_COVER_RULES_BEGIN/END` 之间的纯层（`ShrinkCoverRules` 名单规则 +
`ShrinkCoverRayRules` 外向射线几何）整段抽出，配最小 C# 测试用 mono mcs 编译运行（测的就是生产同一份源码；
生产中 `PokeBvh.Raycast` 也调同一段 `RayHitsTriangle`）。覆盖：路径含 `ear` 不被排除 / 叶子名 `Ear` 被排除 /
身体网格被排除 / `garments_used==0` → verdict 全 `undecidable`，生产 43% 快照夹具回归
（旧口径 used=3 `[Body,Bra,Crown]` 复现误报，新口径 25/37 收回 LopEar 整套），以及任务 CU 的几何级用例：
顶点外侧 20 mm 有布→遮住 / 布在旁边→没遮住 / `any` vs `majority` 各一例 / `cover_ray_mm` 长度生效。
**任务 CX 新增 ⑦**：`verdict_rule` 四种取值各一例（含正样本形态「ratio 不过但 area 过 → or 判 uncovered、and 判 ok」）
+ `verdict_by` 的 `ratio`/`area`/`both`/`none` 四值 + 归一化 + `DefaultAreaThrCm2=1.0`。
产物写 `_长程任务_20260918/派工/tmp/cu/`。当前 **53 PASS / 0 FAIL**。
另有任务 CX 的 `tmp/cx/CxSelfCheck.cs`（`bash _长程任务_20260918/派工/tmp/cx/compile_cx.sh`）把 ① 相同的 verdict 规则
与 ③ `area_per_vert_cm2` 的分子/分母口径一起验，**23 PASS / 0 FAIL**；同一脚本还会重编既有 poke 自检（57 PASS）确认签名改动没破坏它。

**⚠ 标定状态（任务 CU）**：旧判据（`cover_dist_mm`）已被 `seq_t33_calib` 证伪，默认改用外向射线
（`cover_rule=outward_ray` / `cover_ray_mm=50` / `cone_deg=20` / `ray_vote=any`）。下次实跑的验收判据：
正样本（工程B 43% 关袜子 + `pre_probe_blendshapes` 强开 `Ankle`）`Ankle` 必须 `uncovered`，
负样本（全穿）所有键 `ok`，且 `cover_ray_mm` 在 30–80 mm 之间结论不翻转。
`ratio_thr` / `area_thr` / `eps_delta_mm` / `min_verts` 仍沿用旧默认、尚未重标；`cover_rule=distance`
只是给旧读数做对照（`nearest_cover_dist_mm` / `covered_near_ratio`），不要再用它下结论。

**⚠ 第二轮标定失败与诊断（任务 CV）**：`seq_t33_calib2` 用同一正负样本扫 `cover_ray_mm` = 30/50/80 mm，
负样本这边改动有效（80 mm 零误报），但**正样本三档全部 `Ankle` verdict=ok**：`covered_verts` 200–205/221，
`uncovered_ratio` 仅 0.07–0.095（`ratio_thr=0.60` 够不到），且 `covered_by_ray_top` 命中的几乎全是 `Shoes`
（P30：200/200 全是 `Shoes`；P80：`Shoes` 201 + `Shoes_Ribbon` 4）。即「数据说 92.8% 的点外面有布」与渲图里
裸露的尖锥对不上。`nearest_cover_dist_mm` 在六个状态下恒为 7.895 mm（到 `Shoes`）。诊断请求与预判见
`_长程任务_20260918/派工/tmp/cv/`。

**结论（任务 CX / B-T33b，2026-09-20）**：这些数字后来复核过（DSH CV 留下、任务 CX 重新读 P30/P50/P80/N30/N50/N80）——
正样本 `Ankle` 的 `uncovered_ratio` 0.095/0.072，够不到 `ratio_thr=0.60`，但 `uncovered_area_cm2` 6.86/6.29，
`verdict_by=area`。所以**不是样本选错，也不是判据错**：`covered_by_ray_top` 里的 `Shoes` 命中是**合法遮挡**（射线从
鞋腔内的身体点打到鞋面），真正裸露的只有鞋口以上那 21 个点；`"and"` 形状把「被合法遮住的大部分」和「裸露的少数」
乘在一起，必然漏。**改判据形状（`verdict_rule:"or"`）而不是改射线**。这份数据仍然只覆盖一个正样本，
B-T33b 必须按上面的专条重标 `cover_ray_mm` × `area_thr`。
