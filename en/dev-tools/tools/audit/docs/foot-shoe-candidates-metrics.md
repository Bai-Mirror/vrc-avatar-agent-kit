> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/foot-shoe-candidates-metrics.md)

# R9 Foot-Shoe Selection · Lessons, Insole-Surface Convention and Acceptance <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable`, etc. (originally `审查/README.md`) last part of §3.4. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [R9 Foot-shoe selection · new fields (CS / D2 / CW)](foot-shoe-candidates-fields.md) · Next: [T1 output format · `state_<id>.json`](state-driver-output.md) <!-- nav -->

**⚠ Lesson (this one must be remembered; it's the direct origin of task CS)**:
> Writing only the candidate's own listed keys with `SetBlendShapeWeight` while **leaving other keys untouched** **cannot detect** “whether this key needs to be zeroed”.
> When the outfit itself already drives the foot key to 100, candidates `none` (no keys listed), `=50`, `=100`, `current=…` all measure the **same pose** —
> the 5 rows of metrics are completely identical, the sort still picks one of them as the recommendation, and it looks “tested”, but in fact none of the candidates were really distinguished.
> Evidence: in `_长程任务_20260918/审查产出/工程B/seq_play_0920/02_r9_Set05_LopEar/r9_Set05_LopEar.json`,
> of the 5 rows only the `Foot_heels=50` row has different `si`/`tilt`; the other 4 rows have `si_p50=4.060768`, `tilt=24.106232` completely identical,
> yet a recommendation of `Foot_heels=100` was still given.
> **Rule**: R9 candidate requests must always explicitly write `candidates_zero` (listing the keys of that region that the outfit/drivers will rewrite);
> when you see `state_indistinguishable=true` in the results, look at `indistinguishable_kind` first: only for `not_zeroed` should you **not look at the recommendation**,
> and first check whether the zeroing domain is missing keys and whether the keys were really written; `candidate_equivalent` (read-backs pairwise different) means the candidates themselves are equivalent,
> `recommended` is kept, and you can pick any one.

**Why switch to the “insole surface” convention (task CF, v2)**: BZ's `sd` measured the “nearest downward-facing shell surface”, which in practice is the shoe's **outsole**;
with `Foot_heel_OFF=50` (heel half raised), the forefoot sinks into the solid sole and ends up closer to the outsole, so `|sd p50|=2.6 mm` is even smaller than the flat-foot `=100`
(`11.1 mm`), and so =50 still grabbed first place by `|sd p50|` — the B-T08b calibration failed (measured on Project A 09-19 BZ_after).
So v2 no longer treats the outsole as the insole: it directly selects shoe triangles that “have normals pointing up, lie within the foot covers bounding box, and sit above the outsole” as the
**insole surface** (inner shells count too; it doesn't have to be the outer shell), measures the signed distance `si` from downward-facing sole vertices to it, and separately computes the angle between the sole plane and the insole plane,
`tilt_deg`. In a flat shoe the foot rests on the insole ⇒ small `|si p50|`, small `tilt`; with the heel half raised the forefoot sinks into the insole ⇒ `si` much more negative, large `tilt`.
Source: 04 T-08's sort direction (area↓, depth↓) + CF's post-mortem of the B-T08b calibration failure.

**`si` / `tilt` / heel gap (v2) conventions** (also stated in `r9`'s `note` and in each pairing's `si_meta`):
- **Insole surface**: triangles in the shoe piece whose **normals point up** (**geometric normal** by winding order · world up ≥ `poke.insole_up_cos`, default `0.5`≈60°;
  note it's not `OrientedNrm` — the latter is oriented “away from the foot bones”, and an insole inside a cavity would be oriented downward),
  whose centroid falls within the **bounding box of the foot covers body vertices** (expanded by `poke.insole_bbox_margin_mm`, default 5 mm),
  and that are **above the downward-facing outer shell surface (outsole)** by `poke.insole_sole_min_mm`–`poke.insole_sole_max_mm` (default 0.5–80 mm).
  `insole_faces` is the number of faces recognized; **0 = none recognized** (e.g. a solid shoe with no upward inner shell), in which case `si`/`tilt` are null,
  and sorting falls to `|sd p50|` and then to `|d_v p50|` (better missing than guessed; don't pass off a missing metric as the best).
- **`si`**: the signed distance from **downward-facing** body vertices within the foot covers (same normal filter as `sd`) to the **nearest insole surface**,
  **positive = floating, negative = sunk into the insole**. Output `si_mm{count,p05,p50,p95,min,max,mean,negative_count}`;
  sorting reads `|p50|` and the sink-in amount `max(0,-p05)`. `si_foot_verts` is the number of downward-facing vertices when there is an insole surface.
- **`tilt_deg`**: the angle (degrees) between the least-squares plane fitted to the downward-facing sole vertices and the plane fitted to the insole face centroids;
  `foot_plane_tilt_deg` / `insole_plane_tilt_deg` (each vs. horizontal) are also output for troubleshooting.
  The fit uses world `y = a·x + b·z + c` (near-horizontal plane), **assuming the measured state is standing**.
- **Heel gap (v2)**: the `si` of `sub_part=ankle` in the same batch (Foot→Toes axial parameter `t<0.15`, the heel segment),
  output as `heel_gap_mm` (sorting reads `p50`); for the **vertex count** see `heel_vert_count` (counting only downward-facing heel vertices;
  the old v1 would pick up the back of the heel). The old convention is saved separately as `heel_gap_sole_mm` for diagnosis only.
- Taken from the pairing in each candidate's poke run with **the larger of `si_mm.count` and `sd_mm.count`** (when only one shoe/sock is measured, it's that one).
- The old v1 `sd_mm` / `sd_meta{foot_verts,sole_facing_verts}` are still output (reference columns): `sd_foot_verts` = number of foot vertices,
  `sd_vert_count` = number of “body facing down + nearest shell surface facing down” vertices; too large a difference between the two means the sole orientation is abnormal or the shoe isn't on the foot.
- Switches: `poke.insole_enabled` (default `true`), `poke.sd_enabled` (default `true`); thresholds above.
  **When the whole state is tilted, si/tilt/sd are all biased** — that's the cost of “assuming standing”; tilted states need their own convention.

**Trade-offs (hard-coded here so we don't waver again next time)**:
1. Why not use “the first hit of a ray straight down from the sole as the insole”: soles often have thickness/double shells, so the first hit isn't necessarily the insole; “upward inner shell + outsole thickness constraint” is closer to “where the foot should step”.
2. Why `insole_sole_max_mm=80`: an insole more than 8 cm above the outsole is most likely an upward face of the shoe opening/upper, not the footbed; a larger threshold only collects more, and it's better to let the `si` values expose it.
3. Why `si` ranks before `|sd p50|`: `sd` has been falsified by measurement on B-T08b (it ranked =50 first); it's kept only as a reference/fallback when `si` is missing.
4. `tilt` ranks after the sink-in amount: `si p50`/sink-in amount is “does it rest flush”, `tilt` is “is it level”; comparing it on ties is more stable.

**Metrics not computed in this version** (also stated in `r9`'s `note`/`not_implemented`): **stringing** (03b definition: baked triangles compared with the baseline,
longest-edge ratio >3 or area <1% or normal flip; triggered by excessive shrink keys) and **category constraints** — this version only marks them `not_implemented`, and they don't take part in sorting.
`si`/`tilt`/`sd`/heel gap/patches/`opening`/sub-part `d_v` and the `containment` reference columns are computed; these metrics need separate implementations and must not be substituted with existing fields.

**[Claude·Unity·Play acceptance]** (see also §3.2.5 and `审查产出/requests_r9/`):
> **Expectations after the CF revision (2026-09-19)**: new `si_p05/p50/p95`, `insole_faces`, `tilt_deg`
> (+`foot_plane_tilt_deg`/`insole_plane_tilt_deg`); the sort keys become
> `面积↑ → 深度↑ → |si p50|↑ → si 陷入量↑ → tilt↑ → |sd p50|↑ → 跟隙↑ → |d_v p50|↑` (area↑ → depth↑ → |si p50|↑ → si sink-in↑ → tilt↑ → |sd p50|↑ → heel gap↑ → |d_v p50|↑).
> **Run the offline self-check first** (doesn't occupy Play):
> `bash _长程任务_20260918/派工/tmp/cf/compile_cf.sh` (takes references per asmdef; both branches 0 error + 15 PASS,
> including a Project A BZ_after replay and the comparison “v1 would rank =50 before =100”).
> In the self-check, `si` is **injected offline** as `si = sd − H` (`H` = the `sd_p50` of `=100`, i.e. the insole's height above the outsole), and `tilt` is an assumed value;
> **Unity measurement must replace these two assumptions**; see the numbers to read below.
1. Project A MMN shoes (`A2_Outfit=0.214286`, `A2_Sok=0`, `A2_Sho=1`):
   **Precondition**: the current workspace scene already has the ShapeChanger on the shoes attached (`foot_heel_OFF=100`), so running directly will show `none`
   and `=100` tied at 0 patches. To see the “before fix” ground truth, first run
   `python3 开发工具/通用工具/审查/replay/replay.py apply mmn_foot` (removing that SC), and afterwards
   `replay.py revert mmn_foot`. **Before any `replay apply`, run `git status --porcelain` first; stop if it's non-empty**.
   For the source of key names use `审查产出/工程A/t1_full_probes/state_MMN__all.json` (post-build name
   `AAO_Merged_Foot_heel_OFF_____足_ヒールオフ_3`).
   - **After fix** (current scene, `none` reads the key as 100): `=100` and `none` should tie for the top tier (0 patches),
     **with `|si_p50_mm|` / `tilt_deg` knocking `=50` down**. Numbers to read:
     * `=100`/`none`: `si_p50_mm` near 0 (±3 mm), small `tilt_deg` (<3°), `insole_faces` >0;
     * `=50`: `si_p50_mm` clearly more negative (forefoot sunk in, e.g. −5～−15 mm), `tilt_deg` clearly larger (>5°);
     * `=0` still at the bottom (`total_patch_area_cm2 > 2`).
     **If `insole_faces=0`** → no upward inner shell was recognized, `si`/`tilt` are all null, and sorting falls back to `|sd p50|`;
       you must record `insole_faces`, `si_vert_count`, `sd_vert_count` and the state's pose and report back; don't treat it as v2 passing.
     **If `=50`'s `|si_p50|` is actually smaller** → the wrong insole surface was selected (the upper/opening was picked) or the normal filter has a problem;
       record `foot_plane_tilt_deg`/`insole_plane_tilt_deg` and this state's pose, and don't jump to conclusions.
   - **Before fix** (after applying `mmn_foot`): `=100` first, `none`/`=0` at the bottom with toe `total_patch_area_cm2 > 2`.
2. Project C Winter boots (`Outfit=0.875`, `Part_Shoes=1`, `Part_Socks=0`, request `requests_r9/project-c_winter_boots.json`):
   in the normal state (`none`) toe patches <0.5 cm², `si_p50_mm` close to 0, small `tilt_deg`, and it should rank first;
   `Toe_heels=0` >2 cm² (positive sample) with `si_p50_mm` more negative / `tilt_deg` larger, ranking last.
   **If `insole_faces=0` or positive and negative can't be separated, mark the whole table low**, state the reason, and rerun after T-31 before finalizing.
3. Two sorting runs differ by ≤1e-6 (poke is already deterministically ordered); `si_p05/p50/p95`, `tilt_deg`, `heel_gap_p50_mm` from two runs of the same state
   should also be identical digit for digit.

---
