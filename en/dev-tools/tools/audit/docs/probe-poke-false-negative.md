> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-poke-false-negative.md)

# Probe poke · two hard blockers causing false negatives and area-basis review <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §3.2.5.2 / "task CX review". § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe poke · diag diagnostics and shell/normal fixes](probe-poke-diag.md) · Next page: [Project A regression acceptance basis](regression-project-a.md) <!-- nav -->

##### 3.2.5.2 Task CW: two hard blockers behind poke false negatives (area threshold across bodies + low confidence must not output 0)

**Symptom (the author, 2026-09-20, Project B step 5, lop-eared rabbit white-pink platform sneakers)**: R9 candidate `none` (all foot keys zeroed = bare foot) reported
`patch_count=0 / total_patch_area_cm2=0 / max_depth_mm=0`; on that basis all shrink keys were removed from the shoe piece, and **the user saw directly in Play
the toes poking out of the toe box**. Evidence `审查产出/工程B/seq_lopear_r9/01_measure/r9_Set05_shoe.json`:
the probe **did measure** the poke-through — `by_sub_part[toe].d_v_mm = {count:2540, outside:472, p95:6.56, p99:10.82, max:14.86}`,
while `tau_limb_mm=3`. What swallowed it was exactly the **patch aggregation** step, for three stacked reasons:

1. **The area threshold was calibrated on a different body**: `min_patch_area_cm2=0.5` came from Kaguya (vertex spacing 3–6 mm).
   CW at the time believed Milfy's per-vertex area was 0.0043 cm² (treating `shrink_cover`'s `keys[Toe]: uncovered_area_cm2=11.34 /
   affected_verts=2641` as a density), and concluded that a fixed 0.5 was "physically unreachable". **The task CX review rejected that derivation**: 0.0043 is
   "uncovered share / affected vertices", not the per-vertex area of the tested region; the measured tested-region density is 0.1083 (`none`). See "task CX review" below.
2. **`opening` punches holes that cut connectivity**: opening vertices neither become poke nor get union-find edges, cutting the over-threshold region into disconnected small pieces.
3. **NaNimation-deleted points cut it a second time**: both edge linking and area accumulation require all three vertices of a triangle to be usable.

**Fix A: the area threshold follows the body mesh density (`AuditProbes.cs`)**
- Each pair outputs `area_per_vert_cm2 / region_verts / region_area_cm2 / area_per_vert_pos_source`.
  **Basis after the task CX correction**: numerator = sum of areas (cm²) of body triangles whose three vertices are "all in `covers_regions` and all `Usable`",
  consistent with the area-accumulation basis of tested patches; denominator = number of vertices in the same set; positions use the **bind pose stable reference**
  (`sharedMesh.vertices × localToWorld`, `area_per_vert_pos_source:"bind_pose"`), falling back to `"baked"` only when unreadable.
  The old basis (including unusable vertices, using current deformed positions) drifts with blend shapes and is inflated — see "task CX review" below.
- `min_patch_area_cm2 = max(absolute_floor, min_verts_for_patch × area_per_vert_cm2)`; defaults
  `absolute_floor=0.05 cm²`, `min_verts_for_patch=8` ("at least 8 connected vertices" is a vertex-count criterion, comparable across bodies).
  Request keys: `poke.min_patch_rule` (`adaptive` default / `legacy` fixed 0.5), `poke.absolute_floor_cm2`,
  `poke.min_verts_for_patch`, `poke.min_patch_area_cm2` (the old key `min_patch_cm2` is still recognized).
  `min_patch_area_source` = `request`/`adaptive`/`legacy`.
- Always output the dropped components: `dropped_components / dropped_max_area_cm2 / dropped_total_area_cm2 /
  dropped_max_depth_mm` (pair level + top level).
- Self-check: a `by_sub_part` row with `outside>0 && max>tau && patch_count==0` → `suspect_subthreshold:true` + a Chinese-language
  `suspect_reason` ("most likely the area threshold, or opening/deleted points cut the connectivity").

**Fix B: under low confidence, don't output a 0 that looks like a pass (`AuditStateDriver.cs`)**
When `low_confidence=true` **or** `top2_gap_ratio=0` **or** `state_indistinguishable=true`, the R9 row outputs
`patch_count / total_patch_area_cm2 / max_patch_area_cm2 / max_depth_mm` **as `null`** (internal sorting still uses the original values);
the row gets `patch_verdict:"undecidable"`, and the state gets `patch_columns_suppressed:true` and a Chinese-language
`patch_columns_suppressed_reason`. The existing `recommended` logic is unchanged (from task D2: when `state_indistinguishable=true`,
whether `recommended` is voided depends on `indistinguishable_kind`; see the "task D2 / B-T33d" item in §3.4).
**Rationale**: whoever reads that column (human or script)
shouldn't get 0 — 0 in other states genuinely means "no poke-through", and mixing them is a source of false negatives; to judge the geometry, check that row's
`si/sd/tilt/d_v_p50` or the raw poke output.

**What to look at on the next actual run** (taking Project B step 5's `none` candidate as the example; in the original output `r9_Set05_shoe.json`, `m_sok_off`
happens to be exactly `low_confidence=true / top2_gap_ratio=0 / all 7 rows patch_count=0`): that state's four columns should be `null` and
`patch_verdict=undecidable`, **while each row's `suspect_subthreshold` / `dropped_max_depth_mm` /
`rows[].by_sub_part[toe].suspect_subthreshold` are still written** — if any one of these three is true / greater than `tau` (toes `max=14.86>3`),
it means "0 patches is due to the threshold or opening/deleted points cutting connectivity, not the absence of poke-through". When the state is decidable, the toe `total_patch_area_cm2` should no longer be 0.
Control experiment: change `poke.min_patch_rule` to `"legacy"` (or `poke.min_patch_area_cm2:0.5`) and rerun; it should reproduce the old 0 patches.

##### Task CX review: what exactly are the numerator/denominator of `area_per_vert_cm2` (B-T34b)

**Measurement (`审查产出/工程B/seq_t34_verify/01_adaptive/r9_Set05_t34.json`, same body, same
`covers=[LeftFoot,RightFoot,LeftToes,RightToes]`, only the blend shapes differ)**:

| Candidate | `area_per_vert_cm2` | `min_patch_area_cm2`(adaptive) | Usable-region vertex count |
|---|---|---|---|
| `none` | 0.1083 | 0.867 | 3302 |
| `Toe=100` | 0.0772 | 0.618 | 3302 |
| `Foot+Toe` | 0.0094 | 0.075 | 3302 |

**Root causes (two, both in the numerator / vertex set; the denominator is stable)**:
1. **The numerator used "post-bake deformed" positions**: `PokeAreaPerVertCm2` originally consumed `bi.Pos` (the current `BakeMesh`); when shrink keys like `Foot`/`Toe`
   compress the tested region, the area collapses with it → the density follows the blend shapes (0.0094↔0.1083, 11×).
2. **The numerator also included `Usable=false` vertices**: in `covers`, LeftFoot/LeftToes/RightFoot/RightToes total **5109**
   vertices, of which **1807** are deleted by NaNimation (`body_excluded.deleted_nanimated`; readable directly from `by_region.body_region_verts_total` in
   `seq_toe_fix`). These vertices are moved away in the baked mesh, and the triangles containing them have huge areas,
   raising the density by a whole order of magnitude; while patch area accumulation (`patchArea`) already requires all three vertices `Usable`, so the two bases were inconsistent.
   CW at the time wrote "the denominator includes vertices deleted by NaNimation → the threshold is too **lenient** and will only reduce false negatives" — **measurement shows the opposite**: the denominator only
   overcounted by 1807 (+55%), while the numerator was inflated even more by the far-flung vertices; the net effect is that the threshold is **too strict** (0.867 > legacy 0.5).

**Fix (`AuditProbes.cs`)**: `PokeAreaPerVertCm2` adds a `usable` filter (both numerator and denominator only include usable vertices), and positions switch to
`BodyMeshInfo.RestPos` (bind pose stable reference); the output adds `area_per_vert_pos_source` (`bind_pose`/`baked`),
and R9 rows add that column too. An offline self-check on constructed data (`tmp/cx/CxSelfCheck.cs`) proves: without filtering unusable vertices, a single far-flung vertex no. 5 can raise
the density from 2500 to 27500 (**11×**), and after filtering it returns to 2500; using baked deformed positions it drops from 2500 to 750, and switching back to bind pose makes the two
candidates exactly identical.

**Answer to "is 0.867 > 0.5 expected behavior": it is not expected; it is false strictness produced by the two basis bugs above stacking up**. After the fix, this example's
`none` density should land at the real order of magnitude of Milfy's foot mesh (`area_per_vert_pos_source:"bind_pose"`, `region_verts` dropping from
5109 to the usable count 3302), and `8 × that` is expected to be ≤ legacy 0.5 (**check on the next actual run: the adaptive threshold must be ≤ 0.5**;
if it's still > 0.5, that body's foot mesh really is sparser than Kaguya's 0.5 assumption, and it must be recalibrated by "8 connected vertices" rather than
accepting 0.867). Other readable evidence: `pairs[].region_verts` / `region_area_cm2` / `area_per_vert_pos_source`,
and the R9 row's `area_per_vert_cm2` / `area_per_vert_pos_source` / `min_patch_area_source`.
