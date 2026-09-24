> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/foot-shoe-candidates.md)

# R9 Foot-Shoe Selection candidates · Request, Execution and Output <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable`, etc. (originally `审查/README.md`) first part of §3.4. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T1 · version stamp, state read-back assertion, tier slot number, sentinel, sequence/history](state-driver-readback.md) · Next: [R9 Foot-shoe selection · new fields (CS / D2 / CW)](foot-shoe-candidates-fields.md) <!-- nav -->

### 3.4 R9 foot-shoe selection `candidates` (task BJ, B-T08a)

**Why**: when the foot-shape key hangs on only one piece (socks) while the menu can toggle another piece (shoes) independently, bare feet in shoes / socks off with shoes puts the foot back into the high-heel pose,
with the toes poking through the toe cap (MMN instance; the crossing count reports 0 on such samples, F26/B3). So R9 doesn't sort by crossing count; instead, after applying each
candidate key value it runs **T-28a static pierce patches**, and sorts by patch area/depth, for the user/declaration draft to pick a foot-shape key.

**Request** (top-level `candidates` array, independent of `probes`/`pre_probe_blendshapes`; not run by default):

```json
{
  "tool": "state", "avatar": "<头像根名>", "out": "<绝对目录>",
  "candidates_reference": true,
  "candidates_zero": ["Foot_heel_OFF_____足_ヒールオフ", "Toe_heels"],
  "candidates": [
    { "id": "none", "part": "MMN_Shoes", "mesh": "Body_b", "garment": "_Outfit/Outfit_MMN_黑/Shoes",
      "body": "Body_b", "covers": ["LeftFoot","RightFoot","LeftToes","RightToes"], "keys": {} },
    { "id": "Foot_heel_OFF=100", "part": "MMN_Shoes", "mesh": "Body_b", "garment": "_Outfit/Outfit_MMN_黑/Shoes",
      "body": "Body_b", "covers": ["LeftFoot","RightFoot","LeftToes","RightToes"],
      "keys": { "Foot_heel_OFF_____足_ヒールオフ": 100 } },
    { "id": "shoe_only_no_zero", "part": "MMN_Shoes", "mesh": "Body_b", "garment": "_Outfit/Outfit_MMN_黑/Shoes",
      "zero_keys": [], "keys": { "Foot_heel_OFF_____足_ヒールオフ": 100 } }
  ]
}
```

| Field | Default | Description |
|---|---|---|
| `id` | Built from `keys` (empty keys → `none`) | Candidate label, goes into the `candidate` field of the ranking table |
| `part` | `part<序号>` | Group name / output file name `r9_<part>.json` (the file name is sanitized via `SafeFileName`) |
| `mesh` | — | **Blend shape application target** (renderer name/hierarchy path/leaf name, matching rules same as `pre_probe_blendshapes`); at least one of `garment` and `mesh` is required |
| `garment` | Same as `mesh` | **poke pairing clothing** (shoes/socks); `mesh`=body, `garment`=shoes is the common combination |
| `body` | Request top-level `body` / automatic | Body mesh; **recommended to write explicitly**, ensuring the body the keys are applied to is the same one poke measures (`PickBodyPath` reads the top-level `body`, not `poke_body`) |
| `covers` | Inherits the request's `poke_covers` | poke coverage regions; if not written and there are no request-level covers, falls back to keyword pairing (`pair_confidence=low`) |
| `states` | All states | Only run this candidate on these state ids (Project B's 6 shoe tiers can each have one or share one) |
| `keys` | Required (may be an empty object) | `{形态键名: 权重}` (blend shape name: weight); order-independent, applied one by one after sorting by name |
| `zero_keys` | Inherits `candidates_zero` | Candidate-level zeroing domain, overrides the request level; writing `[]` = this candidate doesn't zero. See `candidates_zero` |
| `hard` | Omitted | `{max_total_patch_area_cm2?, min_opening_verts?}`: hard constraints given explicitly by the request; if not met, the row gets `hard_ok=false` and is ranked last |
| `candidates_reference` | `true` | Whether to embed the `containment` reference columns for the same pairing (crossing/containment ratio, written into the table only, not sorted) |

**Execution semantics**: after each state snapshot and probes, for each candidate: first write 0 to every key in the zeroing domain (`zero_keys` overrides `candidates_zero`)
that matches on that candidate's `mesh` (all same-name multiple frames are written, old values go into `zero_applied`, restored together with the restore stack),
then set the candidate's own keys per `keys` (for same names, the later write wins) → read back into `applied_readback` → run `AuditProbes.RunPoke` once with that candidate's
`garment`/`covers`/`body` (removing dosage/perturb/hide from the request, forcing `reference`)
→ `finally` restores all blend shapes written by the zeroing domain and candidate keys. Keys in the zeroing domain that didn't match are written into `zero_missing`, **not counted as a hard failure**.
A single failure only records a warning and doesn't change the snapshot.

**Output `<out>/r9_<part>.json`**:
```json
{ "tool": "r9", "part": "MMN_Shoes", "file": "r9_MMN_Shoes.json",
  "sort_rule": "…", "crossing_counts_used_in_sort": false, "reference_enabled": true,
  "zero_rule": "…", "not_implemented": { "stringing": "not_implemented", "stringing_definition": "…", "category_constraint": "not_implemented" },
  "warnings": ["状态 'MMN_all'：候选 none、Foot_heel_OFF=100 的度量完全一致（…），多半是没清零或键没写进去，推荐不可信。"],
  "states": [ { "state": "MMN_all", "candidate_count": 2, "low_confidence": false,
    "top2_gap_ratio": 1.0, "state_indistinguishable": false, "recommended": "Foot_heel_OFF=100",
    "rows": [ { "candidate": "Foot_heel_OFF=100", "rank": 1, "hard_ok": true, "hard_reasons": [],
      "keys": {...}, "zero_applied": { "Foot_heel_OFF_...": 100 }, "applied_readback": { "Foot_heel_OFF_...": 100 },
      "zero_missing": [], "garment": "…/Shoes", "pair_confidence": "high",
      "patch_count": 0, "total_patch_area_cm2": 0, "max_patch_area_cm2": 0, "max_depth_mm": 0,
      "d_v_p50_mm": -9.5,
      "sd_p05_mm": 0.2, "sd_p50_mm": 0.4, "sd_p95_mm": 1.1, "sd_vert_count": 480, "sd_foot_verts": 812,
      "si_p05_mm": -1.2, "si_p50_mm": 0.35, "si_p95_mm": 2.0, "si_vert_count": 480, "insole_faces": 96,
      "tilt_deg": 1.8, "foot_plane_tilt_deg": 2.1, "insole_plane_tilt_deg": 0.6,
      "heel_gap_p50_mm": 0.3, "heel_vert_count": 96, "heel_gap_sole_p50_mm": 11.0,
      "opening_verts": 12, "opening_deep_verts": 0, "truncated": false,
      "by_sub_part": [...], "reference": {...}, "body_excluded": {...} } ] } ],
  "recommended": { "MMN_all": "Foot_heel_OFF=100" } }
```
The order of `rows` = the ranking: **hard constraints first** (`keys` all resolved, poke with no `error`/`truncated`, request `hard` thresholds);
those that pass are sorted by **`total_patch_area_cm2` ↑ → `max_depth_mm` ↑ → `|si_p50_mm|` ↑ → si sink-in amount `max(0,-si_p05_mm)` ↑
→ `tilt_deg` ↑ → `|sd_p50_mm|` ↑ → `heel_gap_p50_mm` ↑ → `|d_v_p50_mm|` ↑**
(↑ = ascending; smaller values rank higher); those that fail/error are ranked last with `rank=0`.
When the **total area** of the top two in a state differs by <10%, that state gets `low_confidence=true` (`top2_gap_ratio` records the area difference, not including the new keys).
**Task CW (2026-09-20): when the state has `low_confidence=true`, or `top2_gap_ratio=0`, or
`state_indistinguishable=true`, each row's `patch_count / total_patch_area_cm2 / max_patch_area_cm2 /
max_depth_mm` are all output as `null`** (internal sorting still uses the original values), the row gets `patch_verdict:"undecidable"`, and the state gets
`patch_columns_suppressed:true` and a Chinese `patch_columns_suppressed_reason`.
Reason: under these three conditions the patch metrics can't distinguish the candidates, and reading 0 would be mistaken for “no piercing” (the direct lesson of Project B tier 5's `none` false negative);
to see the geometry, check the row's `si/sd/tilt/d_v_p50` or the raw poke output's `pairs[].by_sub_part[].suspect_subthreshold`/`dropped_*`.
The existing logic of `recommended` is unchanged.
**Crossing counts / containment ratio (`reference`) are reference columns only and don't take part in sorting**.
When a metric is missing (`si_p50_mm=null`, e.g. a solid shoe where the insole surface wasn't recognized, or a non-foot part), that item ranks after those with values for the same item, then falls through to the next key.
