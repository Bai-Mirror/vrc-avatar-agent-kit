> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/state-driver-request.md)

# T1 State Driver · Request Format <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §3. § numbers follow the original text; for cross-page § references see the [document index](../README.md). <!-- nav -->
> Previous: [Deployment (sync_audit.py) and invocation](deploy.md) · Next: [T1 · what each state does, sanity checks, volatile blend shapes](state-driver-steps.md) <!-- nav -->

## 3. T1 Request Format

```json
{
  "tool": "state",
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "out": "/abs/path",
  "settle_frames": 30,
  "reset": "declared",
  "reset_driver_targets": false,
  "version_check": true,
  "gear_slots": { "A2_Outfit": 14 },
  "sentinels": {
    "positive": [ { "renderer": "Body", "shape": "sailor_shrink", "weight": 0 } ],
    "negative": [ { "renderer": "outer", "hide": true } ]
  },
  "probes": ["grab_chain", "coincident", "containment", "range"],
  "pre_probe_blendshapes": [ { "renderer": "Body_b", "shape": "foot_heel_OFF", "weight": 0 } ],
  "track_bones": ["Hips", "LeftFoot", "RightFoot", "LeftToes", "RightToes", "Head"],
  "states": [
    { "id": "default",     "params": {} },
    { "id": "headacc_on",  "params": { "A2_HeadAcc": 1 }, "expect_hidden": ["Hair/Acc"] }
  ]
}
```

| Field | Default | Description |
|---|---|---|
| `tool` | — | Required, `"state"` |
| `avatar` | — | Required, the name of the GameObject in the scene (exact match) |
| `out` | — | Required, absolute path of the output directory |
| `settle_frames` | 30 | How many frames to wait after applying parameters before taking the snapshot |
| `track_bones` | Hips / LeftFoot / RightFoot / LeftToes / RightToes / Head | Resolved by `HumanBodyBones` enum name |
| `states` | — | Required; `params` is `{param name: number}` (bools may be written as `0/1` or `true/false`) |
| `reset` | `declared` | How the “user-controllable parameters” are reset before each state (declared expression parameters − VRChat built-ins − parameters maintained by drivers that the user cannot click directly, see `reset_driver_targets`): `declared`=per `VRCExpressionParameters.defaultValue`; `startup`=per the actual values at the moment T1 starts (value source is the old behavior; driver exclusion still applies and can be turned off with `reset_driver_targets:true`); `none`=no reset (accumulates from the previous state). Invalid values log a warning and fall back to `declared`. Details in §3.0.3 |
| `reset_driver_targets` | `false` | Optional, boolean. `false` (default) = additionally subtract from the reset set the parameters “written by `VRCAvatarParameterDriver` and not directly clickable by the user” (task AD, see §3.0.3); `true` = do not exclude these parameters (back to the old behavior, for reproducing historical batches). If a parameter also appears directly in an Expressions menu control it is considered user-clickable, is still reset, but is listed in `warnings` and `states.json.driver_targets_user_clickable` |
| `probes` | omitted | Optional, array; after each state's snapshot, the listed pure-data probes run in order, and results are written to that state JSON's `probes` field. Known names: `grab_chain` / `coincident` / `containment` / `range` / `poke` / `shrink_cover` (task CS, T-33) / `delete_coverage` (§3.2); unknown names log a warning and are skipped. **Not run by default; output identical to the old version** |
| `pre_probe_blendshapes` | omitted | Optional, array `[{renderer, shape, weight}]` (task U); for each state, these blend shapes are temporarily set **after the snapshot and before the probes**, and restored immediately after the probes finish. Purpose: artificially create positive clipping samples (e.g. in the `A2_Sok=0` socks-off state set `foot_heel_OFF` to 0, and the toes should massively poke through the shoe tip). `renderer` is matched exactly by GameObject name / hierarchy path, then by substring fuzzy match (case-insensitive) if no match; `shape` is matched exactly first, then after restoring the AAO rename (stripping the `AAO_Merged_` prefix and trailing `_<n>`), and all pieces of the same original name are set. `weight` defaults to 0 (off) if omitted. Only affects probe readings; `blendshapes` in the snapshot remain the original values; what was actually set is written to the state JSON's `pre_probe_blendshapes_applied`. **No effect without `probes`** (logs a warning) |
| `body` | omitted | Optional, body mesh path (relative to the avatar root, or leaf name), used by `coincident` / `containment` for exclusion/pairing; if omitted it is auto-detected (the visible SMR containing both foot and torso humanoid parts, with the most vertices) |
| `pose` | omitted | Optional, only `tpose` / `ikpose` / `idle` are supported (other values log a warning and are ignored) |
| `version_check` | `true` | Optional, boolean (T-13). `true` = before running, compare “the deterministic hash of the deployment tree `Assets/AvatarAudit/`” with `hash` in `Assets/AvatarAudit/VERSION`, and **refuse to run** on mismatch (`status=error`, scene untouched); `false` = skip the comparison (offline/debugging), and the batch must be marked “version stamp not passed” in the conclusions. See §3.3 |
| `sequence` | `reset=="none"` | Optional, boolean (T-13). Whether the request is a sequence that “switches in real operation order”; only affects the echo in `states.json.sequence` and each state's `history` (`history` is written either way). See §3.3 |
| `gear_slots` | auto-inferred | Optional `{param name: gear count}` (T-13). Slot table for radial parameters; if omitted, inferred from values seen in this batch (only parameters whose values “all lie in [0,1) and all fall on the i/n grid (error ≤1e-3)” are recognized; 0/1 toggles get no slot number). The slot number is the nearest i/n grid point (`0.2857` is closer to `2/7` than to `1/7` → gear 2, avoiding “0.2857 falls into the previous gear”). See §3.3 |
| `readback_epsilon` | `0.001` | Optional, tolerance for parameter readback consistency (T-13) |
| `expect_override` | omitted | Optional `{param name: expected readback value or "any"}` (task BJ, B-补-19). Request-level default; each `states[]` entry may also have its own (state-level takes precedence). When a parameter clamped/legitimately rewritten by a driver (e.g. Project B `BreastSize` clamped to 0.5 by the `Clamp_Breast` layer when stockings are on) reads back unequal to the requested value, a hit here means `readback_failed` is not set; instead `overridden` and `readback.params[].overridden/override_source` are recorded in that state's JSON. No value or `"any"` = any readback value is accepted. See §3.3 |
| `readback_driver_override` | `true` | Optional, boolean (task BJ, narrowed by BR). `true` = when the actual readback value equals the **Set constant value** of some `VRCAvatarParameterDriver`, **and the entry transition condition of the state holding that Driver does a `>`/`<` clamp comparison on the same parameter**, it is automatically judged “legitimately rewritten by a driver” and `overridden` is recorded (the whole batch is no longer aborted); `false` = back to strict mode, only explicit `expect_override` lets it through. Bool `If`/`IfNot` equality checks do not count as clamps and are not let through. See §3.3 |
| `candidates` | omitted | Optional, array (task BJ, B-T08a, R9 foot/shoe selection). Each entry `{id?, part, mesh, garment?, body?, covers?, states?, keys:{blend shape: weight}, zero_keys?, hard?}`: for each state and each candidate, **apply keys → run one T-28a static poke → restore**; at the end of the batch, a ranking table `<out>/r9_<part>.json` is written per `part`. Ranking uses patch area / max depth / \|si p50\| / si sink amount / tilt / `|sd p50|` / heel gap / `|d_v p50|` (v2, see §3.4); **penetration count and containment rate do not participate in ranking**. See §3.4 |
| `candidates_zero` | omitted | Optional, string array (task CS, R9 gap fix). Before applying a candidate, first write 0 to every key these match on **that candidate's mesh**, then write the candidate's own `keys`; the old values before zeroing go into the row's `zero_applied`, the post-write readback goes into `applied_readback`, and unmatched keys go into `zero_missing` (not a hard failure). A candidate-level `zero_keys` overrides it (an empty array = that candidate does not zero). **Omitted = old behavior** (only the candidate's own keys are written, which may overlap with the pose already driven by the outfit; see the lesson in §3.4) |
| `candidates_reference` | `true` | Optional, boolean (task BJ). Whether the candidate poke embeds the `containment` reference columns (penetration count / containment rate) for the same pairing; `false` saves one heavy run. Reference columns are only written into `r9_*.json` and do not participate in ranking |
| `sentinels` | omitted | Optional `{positive:[{renderer,shape,weight} or {renderer,material_queue}], negative:[{renderer,hide}]}` (T-13). Each runs once on the first state: positive samples inject a known defect and read back, negative samples hide the tested part and read V1/V2; **any failure (including configuration errors) sets the whole batch to `status=aborted`**. See §3.3 |
| `expect_visible` / `expect_hidden` | omitted | Optional, arrays of renderer names/paths (T-13), as request-level defaults; each `states[]` entry may also have its own, appended after the defaults. Compared with the actual `visible = activeInHierarchy && enabled`; mismatch → that state is `readback_failed`, and the whole batch is aborted. See §3.3 |
| Tuning parameters besides `settle_frames` | | `blendshape_epsilon`(1e-4), `warmup_frames`(10), `repeat_check`(false), `volatile_probe`(true), `ensure_gm`(true), `auto_play`(false), `timeout_seconds`(1800) |
