> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-poke-diag.md)

# Probe poke · diag diagnostics and shell/normal fixes <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §3.2.5.1. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe poke · hit count and area-threshold basis, Unity acceptance](probe-poke-area.md) · Next page: [Probe poke · two hard blockers causing false negatives and area-basis review](probe-poke-false-negative.md) <!-- nav -->

##### 3.2.5.1 Task CI: `poke.diag` diagnostics + optional shell/normal fixes (false positives on tops)

**Symptom (Claude 2026-09-19, Project A `kaguya__Coat_off`, base avatar sailor outfit)**: `poke_covers=[{garment:"kaguya_cloth/sailor",
covers:["Chest","UpperChest","Spine"]}]` produced 17 patches / 82.6 cm² / deepest 29.9 mm, `shell_faces=14042/27570`;
but four-direction Chest renders in the same state (`seq_BT10_sailor_view/`, and `seq_BT10_sailor_only/` rendering only Body_b+sailor) **show no skin**;
and with the dose `AAO_Merged_sailor_shrink_1` (on `Body_b`, shrinking the body) going 0→100, the area actually rose 73.2→82.6 cm² (physically it should decrease).
Two runs of the same state were bit-for-bit identical (82.59626), and the hide self-check was ok — it's not a random/pairing problem; the geometric judgment is wrong.

**Enabling diagnostics**: add `poke.diag:true` to the request (or top-level `poke_diag:true`). Output:
- Each patch's `patches[].diag`: ≤20 sample vertices (evenly sampled along the body mesh, deterministic), each giving
  `world`, `d_v_mm`, `nearest_feature` (face/edge/vertex) + `nearest_face` + `tri_index` + `garment`,
  `shell_ray` (0 = outward / 1..4 = the k-th cone ray; `shell_ray_kind` is synonymous), `shell_ray_end`,
  `winding_dot_outward` (winding normal · computed outward; <0 means that face was judged `normals_flipped`), `nearest_face_cone_rescued`,
  `opening`, `pseudo_normal`; with `normal_sign=parity`, also `inside_by_parity` / `parity_agree_axes`.
- Per pair: `shell_outward_escaped` (number of faces whose outward ray escaped by itself) / `shell_rescued_by_cone` (number of faces whose outward ray was blocked and were rescued by a cone ray) /
  `shell_rescued_ratio`, plus the `shell_rule` / `shell_majority_min` / `normal_sign` in effect for this run.

**Hypothesis list and criteria** (first confirm/refute with diag numbers, then choose a fix; don't just believe them):

| # | Hypothesis | Confirmed by diag | Refuted by diag |
|---|---|---|---|
| **H1** | `any` (shell if any ray escapes) is too loose: **outer surfaces or lining faces** under the collar/bow/cuffs have their outward ray blocked, but a ±20° cone ray slips around the edge of the occluder → treated as shell | Most of the patch samples' nearest shell faces have `shell_ray_kind∈{cone1..cone4}` and `nearest_face_cone_rescued=true`; the pair's `shell_rescued_by_cone` is high and `shell_rescued_ratio` large | Most samples' nearest faces have `shell_ray_kind=outward` → the shell itself faces outward, H1 is not the main cause |
| **H2** | **Inner-layer faces** of a double-layer (lined) mesh are treated as shell, and `normals_flipped` flips the pseudo-normal the wrong way | Patch samples' nearest faces have `winding_dot_outward<0` (`normals_flipped=true`) and `shell_ray_kind∈{cone}` (inner layer blocked by the outer layer, cone ray escapes through a gap) → H1 + H2 both hold | Nearest faces have `winding_dot_outward≥0` (winding consistent with outward) → sign not flipped, H2 doesn't hold |
| **H3** | The anchor-bone-segment outward direction is wrong at the chest (large bust) for upper-chest/side-chest directions, so the pseudo-normal sign is reversed → when the body shrinks away from the clothes, `d_v` actually grows (explains "more shrink, more area") | Samples have `d_v_mm>0` (reported as poking out) but under `normal_sign=parity` `inside_by_parity=true` (the body vertex is actually **inside** the clothes) → sign reversed; rerun with `normal_sign=parity` or `winding`: **patch area collapses to 0/small**, and with dose it **decreases** as shrink increases | `inside_by_parity=false` (the vertex really is outside the clothes; the poke-through is real); or the area doesn't change after changing the sign → H3 doesn't hold, back to H1 |

**Optional fixes (all made into request parameters so they can be compared without recompiling; default is still the old behavior) and their costs**:

1. `poke_shell_rule:"outward"` — only counts as shell if **the outward ray escapes by itself** (anything blocked by anything doesn't count).
   Fits the README's original intent best: "things covered by a coat/bow don't count as exposed". Cost: thin edges that are skin-tight but genuinely exposed may be misjudged because the 1 mm ray origin hugs the surface (
   can be combined with `poke_origin_mm`); fewer rays than `any` (stops once outward is blocked), **faster**. In the self-check it rescues both the occluder-flap and double-layer cases from false positives.
2. `poke_shell_rule:"majority"` + `poke_shell_majority_min:3` — only counts if ≥3 of the 5 rays escape.
   Cost: **can't fix small occluding flaps** (next to a 5 cm tall small flap, 4 rays of the 20° cone all escape and it's still judged shell; see the `escapes=4` item in the self-check);
   and all 5 rays must be cast, the slowest.
3. `poke_normal_sign:"winding"` — the pseudo-normal uses the mesh winding normal directly, not trusting the anchor-bone outward direction.
   Cost: relies on correct model winding (vendor meshes may have flipped faces); `normals_flipped` is still counted as before for comparison.
4. `poke_normal_sign:"parity"` — winding normals set the orientation, and each body vertex uses a parity vote of three `RaycastAll` rays along +X/+Y/+Z
   (`PokeParityFromHitCounts`, 3-axis majority; **only counts hits on this piece's collider**, avoiding undefined inside/outside when multiple pieces are layered)
   to judge "is it inside the clothes" and set the sign: negative if inside, positive if outside.
   Cost: 3 extra rays per covered vertex (large mesh × 3, may be significantly slower; watch `poke_ray_budget`); for non-closed/self-intersecting meshes
   the vote may be unreliable (parity is undefined at openings anyway), in which case it falls back to `winding` and annotates. **Suggest first using `winding` to see whether the sign is reversed overall,
   then decide whether to go to `parity`.**

**Offline self-check** (`_长程任务_20260918/派工/tmp/ci/CIPokeSelfCheck.cs --selftest`, compiled together with this tool's source;
from task CW onward the lighter `_长程任务_20260918/派工/tmp/cw/compile_cw.sh` can be used — it only compiles 12 offline-compilable files + this self-check,
without depending on the MA/AAO assemblies):

```
bash _长程任务_20260918/派工/tmp/ci/compile_ci.sh          # full (including MA/AAO)
bash _长程任务_20260918/派工/tmp/cw/compile_cw.sh          # lightweight (12 files, 0 error/0 warning)
```
Covers: decl parsing (string / object / part-level garment / one pair per object / no pairing without covers / the real Project A decl's
`kaguya_cloth/sailor`) + synthetic meshes **flat plate positive/negative, occluder flap positive/negative, double layer positive/negative**, rule boundaries
+ parity vote aggregation + **task CW: area-threshold derivation (adaptive/legacy/request), per-vertex area share, the "vertices over threshold but
patch_count=0" self-check, low-confidence states suppressing four columns to null + `patch_verdict=undecidable`, diagnostic columns still readable when suppressed**.
Currently **52 PASS / 0 FAIL**.

**Declaration parsing fix (the same bug)**: `parts[].objects` in `decl.json` are `{path,renderer}` objects, but the old
`PokeReadDeclCovers` did `objs[0] as string` → always null → every request with `poke.decl` fell back to keyword pairing.
F13's `audit.log` actually showed only `请求没有声明 covers，退回关键词配对 1 件` (request declared no covers, fell back to keyword pairing for 1 piece) (only `kaguya_cloth/loafer` was paired;
sailor wasn't tested at all). It now uses `PokeParseDeclCovers`: objects take `path` (compatible with `garment/mesh/object/name`),
strings are used directly as the piece name, **one pair is generated per object**; `AuditBuildPasses.AuditDecl.Load` is likewise compatible with string objects.
**When re-verifying in Unity, you should see `pair_source=decl_covers`, `covers_regions=["Chest","Spine"]` (`UpperChest` is not a body
region and still WARNs as before), `garment=kaguya_cloth/sailor`, not a fallback to `name_token`.**

**Claude's re-verification steps in Unity (same Play session; must actually run)**:

1. **Reproduce the false positive + enable diagnostics**: use `kaguya__Coat_off` with the same parameters, `probes:["poke"]`, sailor covers as before,
   and add `poke.diag:true` to the request. Record the base `total_patch_area_cm2` (should still be ≈82.6) and, per pair,
   `shell_rescued_by_cone`/`shell_rescued_ratio`, and each patch's `diag[].shell_ray_kind`,
   `winding_dot_outward`, `d_v_mm`.
   - High `shell_rescued_ratio` + samples mostly `cone*` → **H1 holds**;
   - Many samples with `winding_dot_outward<0` → **H2 holds**.
2. **Test H3 (dose)**: same request plus `poke.doses:[100,75,50,25,0]` (`perturb` as before, on `Body_b`),
   `poke.diag:true`. Look at `dose_response`: the old `anchor` rule should reproduce "dose ↑ area ↑";
   then run once each with `poke_normal_sign:"winding"` and `"parity"`: **if the area decreases/collapses as shrink increases** → H3 holds, the sign really was reversed.
3. **Test the fixes**: run `poke_shell_rule:"outward"` and `"majority"` (against H1) and
   `poke_normal_sign:"winding"`/`"parity"` (against H2/H3) separately, recording `total_patch_area_cm2`,
   `shell_faces`, `normals_flipped`. Expectation: `outward` significantly suppresses the false-positive area and **no longer reports poke-through in regions fully covered in the renders**;
   if it goes to 0 but also suppresses real poke-through, that piece really does have an opening that should show, and you need to look at the `escapes=...` distribution before setting thresholds.
4. **decl re-verification**: rerun with the F13 request (`poke.decl` pointing to `工程A/_感知/decl.json`),
   confirm `pair_source=decl_covers`, each piece's `covers_regions` matches decl, all 28 parts with covers in `garment_candidates`
   enter pairing; `audit.log` **no longer** shows `请求没有声明 covers，退回关键词配对`.
5. Two runs bit-for-bit: run the same request with the same parameters twice; `patches[].diag` and `shell_rescued_by_cone` agree item by item ≤1e-6.
6. Any visual/load-bearing conclusion still goes through agy falsification before being adopted, as before.
