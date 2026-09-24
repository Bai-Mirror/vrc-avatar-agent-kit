> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-poke-area.md)

# Probe poke · hit count and area-threshold basis, Unity acceptance <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) latter part of §3.2.5 (including "Claude·Unity·Play acceptance"). § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe poke (static poke-through patches) · criteria, request, and output](probe-poke.md) · Next page: [Probe poke · diag diagnostics and shell/normal fixes](probe-poke-diag.md) <!-- nav -->

**Hit count = total number of patches reaching the area threshold** (sum of the `patches` entries across pairs).

`hits`/`patch_count` are only for reference; **the main criterion = `pairs[].total_patch_area_cm2` and `patches[].area_cm2`**.
The area threshold (task CW, from 2026-09-20; basis reviewed and corrected in task CX) is **derivable** by default: `min_patch_area_cm2 = max(absolute_floor 0.05 cm²,
min_verts_for_patch 8 × area_per_vert_cm2)`, where `area_per_vert_cm2` is the per-vertex area share of **this pair's tested region**
(`pairs[].area_per_vert_cm2 / region_verts / region_area_cm2 / area_per_vert_pos_source` state the basis).
**Numeric basis (hard-coded by task CX; stop guessing)**: numerator = sum of areas (cm²) of body triangles whose three vertices are "all covered by `covers_regions` and `Usable`";
denominator = number of vertices in the same set; positions use the **bind pose stable reference** (`sharedMesh.vertices × localToWorld`, field
`area_per_vert_pos_source:"bind_pose"`), falling back to the current deformed positions of `"baked"` only when `sharedMesh` can't be read.
**Old behavior restorable in one step**: request `poke.min_patch_rule:"legacy"` still uses a fixed 0.5 cm²; request `poke.min_patch_area_cm2` (old key `min_patch_cm2`)
explicitly overrides; `min_patch_area_source` indicates `request`/`adaptive`/`legacy`.
Source of the initial value 0.5: Kaguya body vertex spacing 3–6 mm, toes out of shoe 3–8 cm².
**The sentence in the CW report "each vertex in the Milfy toe region only gets about 0.0043 cm²" is wrong**: 0.0043 came from dividing `shrink_cover`'s
`uncovered_area_cm2=11.34` by `affected_verts=2641`, i.e. **uncovered share / affected vertices**, not the per-vertex area share of the tested region;
the measured `area_per_vert_cm2` in `r9_Set05_t34.json` for the `none` candidate is **0.1083** (see the task CX review in §3.2.5.2).
**Whatever the threshold, the dropped components must be exposed**: `dropped_components` / `dropped_max_area_cm2` /
`dropped_total_area_cm2` / `dropped_max_depth_mm` (at both pair level and top level). If a `sub_part` has
`d_v_mm.outside>0` and `max>tau` but `patch_count==0`, that row is marked `suspect_subthreshold:true` with a Chinese-language
`suspect_reason` — most likely the area threshold is too high, or `opening`/NaNimation deleted points broke connectivity (see §3.2.5.2).

When T2 (`AuditFitProbe`) has `"poke": true` or `"poke": {…}` in its request, it embeds the same `poke` block in `geo_<state_id>.json`
within the same Play session (since v4, the T2 output file name changed from `fit_<state>.json` to `geo_<state>.json`).

**[Claude·Unity·Play acceptance] (offline only a csc compile was done; the following must run in Unity; with the T-08 day-6 Play session)**:
1. **Measure the Winter normal-state distribution (I5, measure first, then decide)**: Project C Winter boots in the normal state; print the p50/p95/p99/max of `by_region[].d_v_mm`
   for the toe/ball-of-foot regions, and record `shell_faces`/`mesh_triangles` (to estimate the number of boot wall layers). Use these to confirm/correct `tau_*`; v2's
   "grazing ≤1 mm" had no measured basis and is not used.
2. **Winter positive/negative separation**: normal-state toe patches `total_patch_area_cm2 < 0.5`; after `pre_probe_blendshapes` sets
   `Toe_heels=0`, toe patches `> 2 cm²` (positive sample) — the kind that today's crossing count reports as 0.
3. **LUNALICE normal state** (including the vertices remaining after Delete) has no `≥0.5 cm²` patch.
4. **MMN pre-fix patch** (`pre_probe_blendshapes` releases `foot_heel_OFF`) toe patches `>2 cm²`, after fix `0`
   (merged into the T-16 re-verification).
5. **Dose monotonicity**: `sailor_shrink` / Itazura `Shrink_Knees` (vendor value 100) with `poke_doses:[100,75,50,25,0]`;
   `dose_response[].total_patch_area_cm2` does not decrease as the dose rises (`monotone_nondecreasing=true`).
6. **hide self-check**: after `poke_hide` points to that shoe/top, `hide_selfcheck.ok=true` and the total patch area is 0 (if it's the only covering piece).
7. **Determinism**: same state, same request, twice; `pairs[].d_v_mm` and `patches` differ item by item ≤1e-6 (BVH construction is already ordered by `(质心,面序号)` (centroid, face index)).
8. **Project C's two active roots**: `garment_candidates`/`shell` only see the tested root; the other root does not participate in rays and its triangles are not treated as occluders.
9. Render 2 images each for the positive and negative samples above; only after agy + user confirmation are the τ/area thresholds promoted from advisory to a gate (`thresholds.yaml`).
