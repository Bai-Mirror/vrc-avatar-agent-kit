> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-shrink-cover-output.md)

# Probe shrink_cover · output, diagnostics, self-check, and calibration <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) latter part of §3.2.8. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe shrink_cover · criterion revision history (CU / CX / CT)](probe-shrink-cover-rule.md) · Next page: [T1 · version stamp, state read-back assertions, step slot numbers, sentinels, sequence/history](state-driver-readback.md) <!-- nav -->

**Output**: the full result is written to `<out>/shrink_cover_<stateId>.json` (the repeat pass writes `.repeat.json`);
the top-level `shrink_cover` in `state_<id>.json` in the same directory is a compact row (`probes.shrink_cover` also holds a full object).
For each key in the full result's `keys[]`:

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

`verdict`: `uncovered` (determined by `verdict_rule`: `or` = `uncovered_ratio ≥ ratio_thr` **or** `uncovered_area_cm2 ≥ area_thr`;
`and` = both required; `ratio_only` / `area_only` = only one side) / `ok` / `too_few_verts` / `key_missing`
(the key couldn't be matched on the body mesh, with `error` attached) / `undecidable` (when `self_check.suspicious`, see below; **no `uncovered` is given**).
Each row carries `verdict_rule` / `ratio_ok` / `area_ok` / `verdict_by` (`ratio`/`area`/`both`/`none`).
`covered_verts` / `uncovered_ratio` / `uncovered_area_cm2` are counted under **this run's `cover_rule`** (default outward rays);
`uncovered_area_cm2` = sum of the triangle area shares of uncovered affected vertices (each body triangle's area is split evenly among its vertices, and only the affected and uncovered shares are accumulated);
`ray_covered_verts` = number of vertices covered under the ray basis, `cover_criterion` = the basis actually used for this row;
`nearest_cover_path` / `nearest_cover_dist_mm` / `covered_near_ratio` = reference columns of the old distance basis (not participating in the default verdict);
`covered_by_ray_top` = the top 3 pieces hit by outward rays (sorted descending by the number of vertices for which that piece is the nearest hit; `hit_verts` is the hit vertex count; `[]` means the rays hit no piece at all);
`covered_by_top` = the top 3 pieces under the old distance basis; `hits` = number of `uncovered` keys.

**Diagnostics `diagnostics` (task CV, only with `diag:true`; read-only, doesn't change the verdict or default thresholds)**:
answers problems where data and eyes disagree, like "the verdict says covered, but the render shows it exposed". Request example:

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

Output `diagnostics.keys[]` per key:
- `bbox_mm` / `ray_covered_verts` / `ray_uncovered_ratio` / `bone_groups[]` / `region_groups[]`: A(K)'s **world bounding box**
  (`min_mm`/`max_mm`/`size_mm`/`center_mm`), covered/uncovered counts under the outward-ray basis, and `verts` and
  `ray_uncovered` (the number of vertices in each group not covered by outward rays) grouped by **dominant skin bone Transform name**
  (`LeftFoot`/`LeftToes`/`LeftLowerLeg`…) and by **humanoid region** (`Foot`/`Toes`/`LowerLeg`…) — used to judge whether this key affects just the ring around the ankle or the whole lower leg;
- `sample_count` / `samples[]`: ≤ `diag_samples` evenly sampled vertices, each recording `vert`, `world_mm`, `delta_mm`,
  `outward_normal`, `bone`, `region`;
- `samples[].rays[]`: the **per-ray** results `{dir, kind, hit, path, leaf, dist_mm}` for the central axis `dir=0` + the 4 cone rays `dir=1..4`.
  Unlike the production judgment, here all 5 rays are **always cast** (production `any` stops at the first hit), and the hit piece is "the nearest hit among all visible clothing",
  so you can see exactly which piece blocked the ray and at what distance;
- `sample_hit_by_leaf_axis` / `sample_hit_by_leaf_any`: among the sampled vertices, counts of leaf pieces hit by the central axis / by any direction —
  directly answering "which piece is the 92.8% 'cloth outside'";
- `eps_sweep[]`: `affected_verts` / `affected_verts_raw` for each step of `diag_eps_mm` (counting only; doesn't change the default `eps_delta_mm`).

`diagnostics.rays_used` is the number of ray directions consumed independently by diagnostics; `diagnostics.keys_truncated` indicates the key count was truncated by `diag_max_keys`.
Diagnostics reuse the body mesh and clothing BVH already baked by the main probe, build no extra colliders, and don't participate in `self_check`.

**`self_check` (task CT: the probe refutes itself)**: present at both the top level and in `compact`.
If any of the following holds → `suspicious=true`, `reason` is written in Chinese as `遮挡集合可能被排除规则吃掉了，结论不可信：…` (the occluder set may have been eaten by the exclusion rules; the conclusion is not trustworthy: …),
and **all rows'** verdicts are changed to `undecidable`, `hits=0`:
`garments_used == 0`; `keys_resolved` is empty; all keys are `uncovered`; `garments_used / garments_considered < 0.2`.
Also attached: `garments_considered` (total visible SMRs) / `garments_used` (number entering the set) / `keys_total` / `keys_uncovered` / `used_ratio`.
`garments_excluded[]` records each piece as `{path, leaf, rule, hit?}`, with `rule` = `body_self` / `body_family` / `exclude_regex` (`hit` is the whole name or word that matched).

Geometric basis: A(K)'s delta takes the blendshape **last frame** (normalized to 100% by that frame's weight) multiplied by `lossyScale`;
vertex world coordinates take `BakeMesh` in the current pose (directly reusing `BuildBodyInfo`, with the same bake and exclusions as `containment`/`poke`).

**Offline self-check (task CT/CU, without starting Unity)**:

```
python3 开发工具/通用工具/审查/perception/selftest_shrink_cover.py
```

It extracts the pure layer between `SHRINK_COVER_RULES_BEGIN/END` in `AuditProbes.cs` (`ShrinkCoverRules` list rules +
`ShrinkCoverRayRules` outward-ray geometry) wholesale, pairs it with a minimal C# test, and compiles and runs it with mono mcs (testing the very same source as production;
in production `PokeBvh.Raycast` also calls the same `RayHitsTriangle`). Covers: a path containing `ear` is not excluded / leaf name `Ear` is excluded /
the body mesh is excluded / `garments_used==0` → verdict all `undecidable`, a regression on the production 43% snapshot fixture
(old basis used=3 `[Body,Bra,Crown]` reproduces the false positives; new basis 25/37 recovers the whole LopEar outfit), and task CU's geometry-level cases:
cloth 20 mm outside the vertex → covered / cloth beside it → not covered / one case each of `any` vs `majority` / `cover_ray_mm` length takes effect.
**Task CX adds ⑦**: one case for each of the four `verdict_rule` values (including the positive-sample shape "ratio fails but area passes → or judges uncovered, and judges ok")
+ the four `verdict_by` values `ratio`/`area`/`both`/`none` + normalization + `DefaultAreaThrCm2=1.0`.
Output is written to `_长程任务_20260918/派工/tmp/cu/`. Currently **53 PASS / 0 FAIL**.
There is also task CX's `tmp/cx/CxSelfCheck.cs` (`bash _长程任务_20260918/派工/tmp/cx/compile_cx.sh`), which verifies ① the same verdict rules
together with ③ the numerator/denominator basis of `area_per_vert_cm2`, **23 PASS / 0 FAIL**; the same script also recompiles the existing poke self-check (57 PASS) to confirm the signature change didn't break it.

**⚠ Calibration status (task CU)**: the old criterion (`cover_dist_mm`) was falsified by `seq_t33_calib`, and the default switched to outward rays
(`cover_rule=outward_ray` / `cover_ray_mm=50` / `cone_deg=20` / `ray_vote=any`). Acceptance criteria for the next actual run:
positive sample (Project B 43% socks off + `pre_probe_blendshapes` forcing `Ankle` on): `Ankle` must be `uncovered`;
negative sample (fully dressed): all keys `ok`; and the conclusion must not flip for `cover_ray_mm` between 30–80 mm.
`ratio_thr` / `area_thr` / `eps_delta_mm` / `min_verts` still use the old defaults and have not been recalibrated; `cover_rule=distance`
only serves as a comparison for the old readings (`nearest_cover_dist_mm` / `covered_near_ratio`); don't use it to draw conclusions anymore.

**⚠ Second-round calibration failure and diagnosis (task CV)**: `seq_t33_calib2` swept `cover_ray_mm` = 30/50/80 mm with the same positive and negative samples;
the change was effective on the negative side (zero false positives at 80 mm), but **the positive sample had `Ankle` verdict=ok at all three steps**: `covered_verts` 200–205/221,
`uncovered_ratio` only 0.07–0.095 (couldn't reach `ratio_thr=0.60`), and nearly all hits in `covered_by_ray_top` were `Shoes`
(P30: 200/200 all `Shoes`; P80: `Shoes` 201 + `Shoes_Ribbon` 4). That is, "the data says 92.8% of points have cloth outside" didn't match
the exposed spike in the render. `nearest_cover_dist_mm` was constant at 7.895 mm (to `Shoes`) across all six states. For the diagnostic request and predictions see
`_长程任务_20260918/派工/tmp/cv/`.

**Conclusion (task CX / B-T33b, 2026-09-20)**: these numbers were later rechecked (left by DSH CV; task CX re-read P30/P50/P80/N30/N50/N80) —
the positive sample `Ankle` had `uncovered_ratio` 0.095/0.072, unable to reach `ratio_thr=0.60`, but `uncovered_area_cm2` 6.86/6.29,
`verdict_by=area`. So **neither was the sample wrongly chosen nor was the criterion wrong**: the `Shoes` hits in `covered_by_ray_top` are **legitimate occlusion** (rays from
body points inside the shoe cavity hit the shoe surface), and what's really exposed is only the 21 points above the shoe opening; the `"and"` shape multiplies "the majority that is legitimately covered" by "the exposed minority",
so it must miss. **Change the criterion shape (`verdict_rule:"or"`), not the rays**. This data still covers only one positive sample;
B-T33b must recalibrate `cover_ray_mm` × `area_thr` per the dedicated item above.
