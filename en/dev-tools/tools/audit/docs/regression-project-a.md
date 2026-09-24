> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/regression-工程A.md)

# Project A regression acceptance basis <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §3.2.6. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe poke · two hard blockers causing false negatives and area-basis review](probe-poke-false-negative.md) · Next page: [Probe delete_coverage (MA ShapeChanger delete-region coverage)](probe-delete-coverage.md) <!-- nav -->

#### 3.2.6 Project A regression (Claude's acceptance basis on Project A)

The following values come from measurements on 2026-09-18 (`_长程任务_20260918/感知机制研究/00_当日补充_1830.md` and
the 18:20 entry of `工程A/_施工记录.md`), recorded here for comparison on the first run of this tool (**this round only did an offline compile,
Unity was not started; they need to be rerun and confirmed in the Project A project using the two groups of states below**):

1. **Shoe toe containment / crossing**: the state explicitly sets `A2_Outfit = 1.5/7` (whole-outfit step; use the exact fraction, i.e. `0.214286`, not a truncated
   decimal, otherwise the radial will land on the previous step), `A2_Sok = 0` (socks off), `A2_Sho = 1` (shoes on), and all other part parameters explicitly `1`.
   Run `probes=["containment"]`: in the **pre-fix git version** (`Foot_heel_OFF` only hung on the socks), `LeftToes`/`RightToes` in `by_region`
   have `inside_ratio` in the **single-digit percent** range (measured toes 2%); **after the fix** (the same
   ShapeChanger also hung on the shoes), toes should be **≥ 95%** (measured 100%). Sole of foot at 85–87% is normal. After task U, `inside_ratio` is only a reference;
   the criterion is crossings (next item).
   After this round's changes, `by_region` must show `LeftFoot` and `LeftToes` **separately** (hand measurement: toes about 1149 vertices, sole about
   852 vertices, for comparison); the same region's `body_region_verts_total` should be constant across the 83 states, with no more
   `LeftFoot` 2033↔3222 jumps. With `A2_Sok = 1` (socks on), the toes are deleted by MA ShapeChanger via NaNimation,
   landing in `excluded.deleted_nanimated`, and `verts` drops accordingly, even to 0 — **toe `flagged` is meaningless in that case**
   (the geometry no longer exists); containment / crossing must be tested with `A2_Sok = 0` states.
   Pairing side: in this example, automatic pairing should no longer include the screen-grab windows `windowA`…`windowE`/`final-window`; each shoe/glove should carry
   `pair_source=name_token` and `pair_matched_token` (e.g. `shoes`→`shoes`, `(B)Boots`→`boots`, `Gloves`→`gloves`).
   After task U the criterion is crossings: before the fix, in that state `LeftToes`/`RightToes` should have `crossing_edges` clearly ≥ 20 and
   `crossing_ratio` ≥ 1% (positive sample, `flag_basis=crossing`); after the fix they should return to 0 / single digits (negative sample).
   Open shoes (Silent Twilight), even with `inside_ratio` of only 3–6%, should have `crossing_edges` close to 0.
2. **Headwear screen grab**: the state explicitly sets `A2_Head = 0.5`; run `probes=["grab_chain"]`:
   in the **pre-fix git version** (our recoloring clip referenced the vendor original), `grab_point_queue` should be **2450**,
   and `hidden_materials` should include visible slots such as hair with `renderQueue ≥ 2450` (invisible through the screen-grab window);
   **after the fix** (pointing to the screen-grab copy instead), the grab point should return to **3050** (measured 28/28 states), and `hidden_materials` shrinks accordingly.
3. **Crossing-count positive sample (artificially created, task U)**: in the `A2_Sok = 0` (socks off), `A2_Sho = 1` (shoes on) state, add the request
   `"pre_probe_blendshapes": [{"renderer": "Body_b", "shape": "foot_heel_OFF", "weight": 0}]`
   (`foot_heel_OFF` fuzzy-matches the AAO-renamed `AAO_Merged_foot_heel_OFF_1`): the toes are put back into the high-heel pose and cross the toe box extensively;
   in the shoe pairing, `LeftToes`/`RightToes` `crossing_edges`/`crossing_ratio` should rise significantly, `flagged=true`;
   `pre_probe_blendshapes_applied` in `state_<id>.json` must list the items actually set (`requested_renderer` /
   `requested_shape` vs the actual `renderer` / `shape`, `weight`, `old_weight`), while `blendshapes` still holds the original snapshot values
   (the override only affects the probes and isn't written back into the snapshot). Remove this override and run again; the crossing count should fall back — this is the core of "positive / negative sample pairing".
