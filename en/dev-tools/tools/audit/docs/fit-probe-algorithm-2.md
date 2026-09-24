> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/fit-probe-algorithm-2.md)

# T2 Fit Probe · Algorithm and Criteria (7–10), v2 Exclusions and Rejections <!-- nav -->

> Formerly: T2 (originally `审查/README_T2.md`) second half of §4 / §4.5. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T2 Fit probe · algorithm and criteria (1–6)](fit-probe-algorithm.md) · Next: [T2 Fit probe · v3 coverage scope, output, performance](fit-probe-scope-output.md) <!-- nav -->

7. **Foot-specific checks** (`foot.enabled`; v3 changed to “each foot × each piece of clothing covering that foot”):
   - **Covers that foot** = the clothing's set of covered regions (§4.6) includes that side's `LeftFoot/LeftToes` (or `RightFoot/RightToes`);
     when the clothing's skinning can't be judged (`region_source=no_bones`, etc.) it falls back to the old `footCoverage>0` convention.
   - Foot = body vertices whose region is `LeftFoot/LeftToes` or `RightFoot/RightToes` (v2 goes through the parent-chain mapping of 1.5,
     so names like `Foot_L$Toe_L$85` are classified correctly); excluded vertices don't take part.
   - **Classification** (each `feet[]` entry carries `class` + `class_source` + `class_detail` + `thickness_p50_mm`/`thickness_count`),
     priority **(a) explicit in request > (b) geometric thickness > (c) name keywords**:
     - (a) request `foot.footwear` / `foot.legwear` path lists (full path or leaf name) → `class_source="request"`;
     - (b) **thickness** below the sole: cast along `-Y` from the sole vertices to that clothing; the distance between the first and last hits, taking the p50 over the
       sole vertices of both feet. `>= sole_min_mm` (default 4 mm) → `footwear`; `< 2 mm` (skin-tight) → `legwear`;
       falling within `[2mm, sole_min_mm)` → geometry abstains, fall through to (c). `class_source="geometry"`.
       Implemented with `Physics.RaycastNonAlloc` to get all hits at once; in the occasional case where only one hit comes back, an extra ray is cast “upward from
       `probe_mm` below the sole” to get the outsole, then the insole distance is subtracted (an equivalent convention).
     - (c) path keywords: `(?i)(shoe|boot|loafer|heel|sandal|sneaker|靴|鞋)` → `footwear`;
       `(?i)(sock|stocking|tights|袜)` → `legwear`. `class_source="name"`.
     - None match → `other`, `class_source="default"`.
   - **footwear**: keeps the original sole metrics. Sole = vertices in that foot whose normal points down (`n.y < -0.5`). Cast down `-Y` `probe_mm`
     and hit the **front face** of the shoe insole (normal pointing up) → floating, recorded positive; nothing hit downward but the **back face** of the insole hit upward `+Y` (normal pointing up, in the same direction as
     `+Y`) → through the sole, recorded negative. Outputs p05/p50/p95 of `signed_mm`, `below_sole` (count <0), `floating_gt5mm` (count >5mm).
   - **footwear**: heel = the rearmost 10% of **sole** vertices projected along the `Foot→Toes` line, with the p50 of their signed distances;
     toe tip = the frontmost 10% of **foot** vertices along that line, with the count `pierced` by that shoe (whether they poke out of the toe cap).
   - **legwear / other**: **no sole signed distance is computed** (meaningless for skin-tight socks); only reports `covered`/`pierced`/`coverage`/
     `pierce_ratio` and `gap_avg_mm` (over the foot's enclosed vertices, the mean outward hit distance from the body surface to the clothing's inner surface),
     `gap_count`.
   - Every `feet[]` entry carries `foot_verts` / `sole_verts` / `shape_keys`. `shape_keys` = the current weights of blend shapes on the body mesh whose names match
     `(?i)(foot|heel|toe|shoe|highheel|sock)` (read directly via `GetBlendShapeWeight`, including 0).
   - *Why it changed*: socks (skin-tight) don't have the “sole — shoe insole” structure; the old version measured p50≈-13 mm on `stocking`, all
     `below_sole`, meaningless numbers; and the old version only reported the piece with the most coverage, so with two layers (socks + shoes) the other layer was invisible.
8. **markers**: world coordinates of the top `markers_top` pierced vertices sorted by depth + region + clothing + depth + vertex index.
9. **Self-check modifications**: `perturb` sets blend shapes before baking, `hide` turns off renderers before baking; both are restored in `finally`/`Cleanup`.
10. **Cleanup**: all temporary GameObjects / Meshes are `Object.DestroyImmediate`d; `Physics.queriesHitBackfaces`,
    blend shapes, and `renderer.enabled` are restored; **no `MarkSceneDirty`, no scene save**.

---

## 4.5 v2's three exclusions + two rejections (criteria and reasons)

This section was added in v2 for problems measured on Project A: on thin regions (toes/fingers/wrists), inward rays exit the body and hit clothing on the opposite side,
and were miscounted as “pierced”; MA ShapeChanger's Delete vertices were still in the mesh and took part in the statistics. The criteria all take effect before/during ray statistics,
and counts are output in `excluded_vertices` and in the `rejected_*` fields per clothing piece / per region.

### Three exclusions (`excluded_vertices`, body mesh only; meeting any one excludes the whole vertex from statistics)

| Key | Criterion | Why |
|---|---|---|
| `nanimated` | The name of the highest-weight bone **or anything on its parent chain** contains `NaNimat` (case-insensitive) | MA ShapeChanger's Delete moves vertices away using `NaNimation buffer$NaNimatedBone for ...deletedShape.xxx`; they aren't displayed at runtime and can't go into statistics. The parent chain is also checked because the actual bone name may be a concatenated form like `Foot_L$NaNimation ...`. |
| `non_finite` | The baked world position or normal contains `NaN` / `±Infinity` | Such values are meaningless in any distance/comparison; they also can't go into MeshCollider baking (bounds would become NaN). |
| `zero_weight` | Either: ① the vertex's total skinning weight `<= 0` (not driven by any bone, invisible); ② the vertex's distance to `Hips` `> 3 m` | ① is the direct sign of “unskinned/deleted”; ② corresponds to “MA's Delete may also pull vertices extremely far away via blend shapes” — 3 m is far larger than any humanoid body size (Hips to toe tip is about 0.9 m), used only to catch obvious anomalies, without harming normal vertices. The field name follows the task brief. |

- When weights can't be read (mesh has Read/Write off, `weights_source=nearest_bone`), criterion ① has no data and only ② is used.
- Priority: `non_finite` > `nanimated` > `zero_weight` (a vertex goes into only one bucket), so the three buckets sum to
  `body_vertex_count - body_vertex_used`.
- Excluded vertices also don't go into the triangles of the body MeshCollider (they're zeroed/set to up in the vertex array only to avoid baking NaN bounds).

### Two rejections (`rejected_through_body` / `rejected_opposite_normal`, counted per clothing piece + per region)

1. **`rejected_through_body`**: the ray hits the body mesh **before the clothing hit point**, with `distance < clothing hit distance`
   and `> 0.5 mm` (`<= 0.5 mm` is treated as a self-hit at the origin and ignored). Both outward and inward count.
   *Reason*: an inward ray enters from a thin region, first exits the body (hitting the inner wall on the opposite side of the body), and only then hits the clothing — that clothing is on the opposite side,
   not “this side being poked through”; the old code only looked at the normal's sign and would count it as `pierced`. Likewise outward: hitting another part of the body first
   (armpit, between fingers) means that clothing hit isn't in the direction that encloses the vertex.
2. **`rejected_opposite_normal`**: the inward ray hits the **front face** of clothing, but the angle between that hit point's **outward normal** and the body vertex normal
   is `>= 90°` (`dot <= 0`, opposite).
   *Reason*: clothing on the same side that truly encloses the vertex should have its outward normal roughly aligned with the body vertex normal; opposite means it hit the inner surface of clothing on the opposite side
   (exactly the form of thin-region false positives). This is the second gate for when the body collider fails to catch it (e.g. the body face on the opposite side is missing).
   “Outward normal” uses the convention calibrated in item 6 (`hit.normal` when `hit_normal_usable`, otherwise winding normal × `winding_sign`).

Neither rejection is **counted** in `covered`/`pierced`/`coverage`; they're counted separately, and recorded even if the vertex wasn't in the coverage area in the first place,
so as to answer “why wasn't this counted”.

### Saturation flag

When a region has `p95_depth_mm >= 0.9 * pierce_mm`, `depth_saturated:true` is output (also carried in `total`).
*Reason*: depth reaching the ray length limit means the number is no longer a real pierce depth, but a false hit “reaching the opposite side / farther away”;
with `pierce_mm=15` the threshold is 13.5. When a region with high `pierce_ratio` also has `depth_saturated=true`,
suspect remaining false positives first rather than directly judging it as clipping.

### Expectations (Project A default outfit, `body=Body_b`, `pierce_mm=15`)

- Old results: `kaguya_cloth/loafer` toe area `Foot_L$Toe_L$85` pierce_ratio≈0.55,
  `stocking`'s `Left Hand_Const`≈0.89, `sailor`'s `Right Hand_Const`≈0.81, with p95 mostly in 13.6~15.2.
- v2 expectations: these high ratios should **drop sharply** (thin-region rays are vetoed by `rejected_through_body` / `rejected_opposite_normal`;
  the deleted `NaNimation ...deletedShape.*` regions disappear entirely and go into `excluded_vertices.nanimated`).
- If the drop isn't obvious, locate the cause from the output: large `rejected_through_body` → the body collider works but there are still opposite-side hits (check whether
  `body` is wrongly chosen, or whether the body face there is also genuinely missing); large `rejected_opposite_normal` → body hits didn't catch it and the normal is the fallback;
  both small but many `depth_saturated=true` → the ray length limit or the calibration convention may be wrong; look at `calibration` first.

---
