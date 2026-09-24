> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-shrink-cover.md)

# Probe shrink_cover (shrink-key occlusion consistency) · request and parameters <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) first part of §3.2.8. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe delete_coverage (MA ShapeChanger delete-region coverage)](probe-delete-coverage.md) · Next page: [Probe shrink_cover · criterion revision history (CU / CX / CT)](probe-shrink-cover-rule.md) <!-- nav -->

### 3.2.8 `shrink_cover` — shrink-key occlusion consistency (T-33, task CS; list and self-check fixed in CT; criterion changed to outward rays in CU; verdict shape changed to "or" in CX / B-T33b)

**Why**: `poke` only answers "does the body poke out of the clothes"; it **does not answer** "the clothes are gone — is the body's shrink key still on?".
The issue the user reported on 2026-09-20, "Project B Milfy: with socks off / shoes and socks off / shoes off, the foot's tuck-in blend shape is still =100, collapsed ankle", is exactly the latter:
the vertices affected by the shrink key are not covered by any visible clothing. This probe turns "which shrink key is exposed, and by how much" into structured numbers.

**Request** (add `"shrink_cover"` to `probes`; parameters go in the top-level object of the same name, or can be overridden with flat `shrink_cover_<key>`):

```json
{
  "probes": ["shrink_cover"],
  "shrink_cover": {
    "body": "Body",
    "keys": ["auto_nonzero"],
    "min_weight": 1,
    "keys_exclude_regex": "(?i)^(vrc\\.|eye|mouth|brow|blink|tongue|face|extra_)",
    "eps_delta_mm": 0.5,
    "cover_rule": "outward_ray",
    "ray_vote": "any",
    "cover_ray_mm": 50.0,
    "cone_deg": 20.0,
    "origin_mm": 0.0,
    "cover_dist_mm": 3.0,
    "ratio_thr": 0.60,
    "area_thr": 1.0,
    "verdict_rule": "or",
    "min_verts": 20,
    "shell_rule": "any",
    "inside_check": true,
    "garments_exclude": "(?i)^(hair|nail|lash|eye|face|tooth|tongue|head|halo|particle|avatarhight|tail|ear)$"
  },
  "states": [ { "id": "sok_off", "params": { "Socks": false, "Shoes": false } } ]
}
```

| Field | Default | Description |
|---|---|---|
| `body` | top-level `body` / auto | Body SMR (matching rules same as `pre_probe_blendshapes`: exact path/name/leaf name, then substring). If omitted, `PickBodyPath` identifies it automatically |
| `keys` | `["auto_nonzero"]` | String array. `auto_nonzero` = all keys on the body mesh whose current weight > `min_weight`, then facial-expression keys are removed via `keys_exclude_regex`; explicit keys are always included (unaffected by the exclusion regex) |
| `min_weight` | `1` | The "non-zero" threshold for `auto_nonzero` (weight units 0–100) |
| `keys_exclude_regex` | `(?i)^(vrc\.\|eye\|mouth\|brow\|blink\|tongue\|face\|extra_)` | Removes facial-expression keys; an invalid regex logs a warning and the filter is ignored |
| `eps_delta_mm` | `0.5` | Affected-vertex threshold: only vertices with world displacement ≥ this value (mm) at blendshape 100% count toward A(K) |
| `cover_rule` | `outward_ray` | **Criterion choice from task CU**: `outward_ray` (outward rays, default) / `distance` (old basis: inside the shell or nearest distance ≤ `cover_dist_mm`) / `either` (either one). Aliases `any`/`majority` = `outward_ray` + the corresponding `ray_vote` |
| `ray_vote` | `any` | Outward ray vote: `any` (covered if any ray hits) / `majority` (≥3 of 5 rays hit) |
| `cover_ray_mm` | `50.0` | Outward ray length (mm). Actual-run acceptance requires the conclusion not to flip between 30–80 mm |
| `cone_deg` | `20.0` | Angle (°) of the 4 cone rays relative to the central axis; tangent-axis basis same as poke's `PokeBasis` |
| `origin_mm` | `0.0` | Offset (mm) of the ray origin along the outward normal: rays start from `v + n*origin_mm` |
| `cover_dist_mm` | `3.0` | **Old basis**: nearest distance to a visible clothing surface ≤ this value counts as occluded (used by `cover_rule=distance`/`either` or the reference column `covered_near_ratio`) |
| `ratio_thr` | `0.60` | `uncovered_ratio` threshold; whether it is used to judge `uncovered` is determined by `verdict_rule` |
| `area_thr` | `1.0` | `uncovered_area_cm2` threshold (cm²); whether it is used to judge `uncovered` is determined by `verdict_rule`. **The initial value replaced in task CX / B-T33b** (the old 2.0 had no derivation); for the derivation and "pending calibration" status see the dedicated item below |
| `verdict_rule` | `or` | **Task CX / B-T33b**: the shape of the `uncovered` criterion. `or` (default, ratio **or** area, either one meets its threshold) / `and` (old behavior, both required) / `ratio_only` / `area_only`. The effective value is stated in `thresholds.verdict_rule`, top-level `verdict_rule`, and each row's `verdict_rule` |
| `min_verts` | `20` | Usable vertices in A(K) fewer than this → `too_few_verts` (not judged) |
| `shell_rule` | `any` | This probe only accepts `any` (all visible clothing triangles are occlusion candidates); `outward`/`majority` are poke's shell classification bases, and passing them falls back to `any` |
| `inside_check` | `true` | The old basis's "falls inside the shell" judgment (six-direction ray parity); only run with `cover_rule=distance`/`either` (skipped under the default `outward_ray`) |
| `garments_exclude` | `(?i)^(hair\|nail\|lash\|eye\|face\|tooth\|tongue\|head\|halo\|particle\|avatarhight\|tail\|ear)$` | **Task CT basis**: only takes the **leaf GameObject name**, and it counts as a hit only if "the whole name matches fully **or** some word split out by separators (`_ . -`, space, etc.) matches fully". Whole-segment matching is enforced by `ShrinkCoverRules.ExcludeHit` (even old unanchored strings won't hit as substrings) |
| `max_keys` | `512` | Upper limit on the number of auto keys (exceeding it records `keys_truncated=true`) |
| `diag` | `false` | **Task CV diagnostics switch**. When `true`, the top level gains `diagnostics` (read-only evidence; doesn't participate in verdict or change default thresholds); when `false`, output is byte-for-byte identical to the old version |
| `diag_keys` | `[]` | Array of key names to diagnose; empty = this run's `keys_resolved` (subject to the `diag_max_keys` limit; exceeding it records `diagnostics.keys_truncated=true`). Keys removed by `keys_exclude_regex` can be specified explicitly |
| `diag_samples` | `50` | Upper limit on sampled vertices per key (1–500), taken evenly by vertex index over A(K) |
| `diag_max_keys` | `4` | Upper limit on the number of diagnosed keys (the fallback when `diag_keys` is empty, to avoid `auto_nonzero` dumping per-vertex evidence for all keys at once) |
| `diag_eps_mm` | `[0.5,0.2,0.1,0.05]` | eps scan steps; only outputs the A(K) count for each step, **does not change** the `eps_delta_mm` default |
| `diag_ray_budget` | `500000` | Separate budget for diagnostic rays, counted separately from the main pipeline's `ray_budget` (records `rays_truncated` when exhausted) |
| `max_iter` / `inside_votes_threshold` / `layer` / `ray_budget` | `30` / `4` / `30` / `2000000` | Same ray parameters as `containment` (`ray_budget` also governs outward rays) |
