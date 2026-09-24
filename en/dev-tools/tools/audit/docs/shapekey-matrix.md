> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/shapekey-matrix.md)

# T5 blend shape dependency matrix t5_shapekey_matrix.py · pipeline and subcommands <!-- nav -->

> Formerly: T5 (original `审查/README_T5.md`) page top / §1–§4. § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Next: [T5 blend shape dependency matrix · analyze, classification and candidate criteria](shapekey-matrix-analyze.md) <!-- nav -->

# T5 · Blend shape dependency matrix `t5_shapekey_matrix.py` — generate T1 requests, merge radial intervals, analyze dependencies

> Goal: turn "which toggle moves which blend shape, who should shrink but didn't, whether the foot-shape keys are bound correctly" from **eyeball comparison** into **data**.
> Depends on: T1 `AuditStateDriver` (runs states, reads visible renderers and blend shapes), T4 `AuditMenuDump` (exports `params.json`).
> This tool is a **pure Python 3 standard-library** script: it does not launch Unity, call MCP, or touch the project; it only reads inputs and only writes `--out`.
> Design basis: task P in `_长程任务_20260918/派工/`; hand-verified samples in
> `_长程任务_20260918/审查产出/工程A/t1_sweep_outfit_parts/`.

---

## 1. Deliverables and typical pipeline

| File | Role |
|---|---|
| `开发工具/通用工具/审查/t5_shapekey_matrix.py` | This tool (the only code file) |
| `README_T5.md` | This page |

Typical pipeline (for avatars like Project A with "multiple outfits + per-part toggles"):

```bash
T5=开发工具/通用工具/审查/t5_shapekey_matrix.py
# ① Fine radial scan: 65 points over 0..1 for each Float radial, write a T1 request
python3 $T5 slots --params <工程>/t4_menu/params.json --avatar "<头像根名>" \
        --out <run>/slots_scan --step 1/64
#    → copy <run>/slots_scan/t1_request_slots.json to
#      <工程>/Library/AvatarAudit/request.json and run T1 in Play
# ② Merge radial intervals
python3 $T5 slots-reduce --t1 <run>/slots_scan --out <run>/slots.json
# ③ Generate the toggle sweep request (full set × single-off × all-off + other toggles)
python3 $T5 sweep --params <工程>/t4_menu/params.json --slots <run>/slots.json \
        --avatar "<头像根名>" --out <run>/sweep
#    → copy <run>/sweep/t1_request_sweep.json to request.json and run T1 again
# ④ Analyze
python3 $T5 analyze --t1 <run>/sweep --sweep <run>/sweep/t1_request_sweep.json \
        --out <run>/matrix
#    → <run>/matrix/matrix.json + <run>/matrix/matrix.md
```

> T1 deployment/request fields: see `README.md`; `params.json` fields: see `README_T4.md`.
> This tool copies no files into the project; moving `request.json` is up to the caller (see the comments between steps).

Four subcommands:

| Subcommand | In one sentence | Key inputs | Key outputs |
|---|---|---|---|
| `slots` | Fine 0→1 scan of each Float radial | `params.json` | `t1_request_slots.json`, `slots_plan.json` |
| `slots-reduce` | Compress fine-scan results into intervals by signature | T1 output dir (+ `slots_plan.json`) | `slots.json` |
| `sweep` | Full set × single-off × all-off + other toggles | `params.json`, `slots.json`, optional `groups.json` | `t1_request_sweep.json`, `groups_used.json` |
| `analyze` | T1 output → dependency matrix | T1 output dir, sweep request | `matrix.json`, `matrix.md` |

---

## 2. `slots`: fine radial scan

```
slots --params <t4 params.json> --avatar <name> --out <dir> [--step 1/64]
      [--only regex] [--exclude regex] [--settle-frames 30]
```

- Parameter selection: `value_type_name == "Float"` and `menu_value_kinds` contains `radial` (“radial”). Float parameters whose type T4 did not export
  are not selected; `--only/--exclude` (regex on parameter names) can narrow further, e.g. for face tracking use
  `--exclude '^FT/'` to exclude.
- Values: evenly spaced from **0 to 1**, **including 0 and 1**. `--step 1/64` → 65 points; decimals (e.g. `0.05`) are also accepted.
- One state per value; other parameters are not written (T1 resets "user-controllable parameters" to their startup defaults, see README.md §3).
- The request fixes `volatile_probe=false`: a fine scan wants determinism, and auto-playing face keys would only pollute the signatures.

Output:

- `t1_request_slots.json`: a standard T1 request (`tool=state`, `out` points to the same directory).
- `slots_plan.json`: `values` (all values) + for each radial its `state_ids` (`slot__<参数>__<序号>`),
  `labels`/`label_count`, `menu_paths`. `slots-reduce` uses it to map state files back to values.

> Number of states = number of radials × number of values. Project A has 20 Float radials, so `1/64` means 1300 states; above 2000 a
> warning is written. For a first run, `--step 1/4` is recommended to prove the flow, then do the fine scan for real.

---

## 3. `slots-reduce`: compress the fine scan into intervals

```
slots-reduce --t1 <T1 output dir> --out slots.json [--params <params.json>] [--step 1/64]
```

- Signature = **set of visible renderers + set of non-zero blend shapes** (keys as `(renderer path, blend shape name)`).
  In `state_<id>.json`, `visible = activeInHierarchy && enabled`; non-zero keys only include `|value| > blendshape_epsilon`
  (taken from `states.json.blendshape_epsilon`, default 1e-4).
- **Adjacent** values with identical signatures → merged into one interval, outputting `[lo, hi]`, `recommended` (interval midpoint),
  `value_count`, `visible_count`, `nonzero_key_count`, `appeared`/`disappeared` (relative to the previous interval),
  and the full signature of the last sample within the interval.
- `narrow`: flagged when interval width `hi-lo < 2×step` (single-point and two-point intervals both count) — such intervals are likely transition frames or
  noise, and should be confirmed when T1 is rerun.
- `label_mismatch`: written when the interval count differs from the number of menu `radial_labels`. When T4's `radial_labels` is empty,
  the field is `null` (Project A's is empty, so there is nothing to compare).
- When the state file for a value is missing, merging **breaks** at that point instead of spanning it, and a warning is written.

`slots.json` structure (excerpt):

```json
{ "tool": "t5_shapekey_matrix.slots-reduce", "step": 0.25,
  "slots": { "A2_Hair": {
      "interval_count": 3, "label_count": null, "label_mismatch": null,
      "intervals": [
        { "lo": 0.0, "hi": 0.0, "recommended": 0.0, "narrow": true,
          "value_count": 1, "visible_count": 1, "nonzero_key_count": 1,
          "appeared": ["Hair"], "disappeared": [],
          "signature": { "visible": ["Hair"], "nonzero_keys": ["Body_b.hair_shrink"] } } ] } } }
```

---

## 4. `sweep`: full set × single-off × all-off

```
sweep --params <params.json> --slots <slots.json> --avatar <name> --out <dir> [--groups groups.json]
```

Composition of the state set:

1. For each interval's recommended value of the **full-set/outfit radials** (e.g. `A2_Outfit`):
   - `setN__all`: that radial = recommended value, **all clothing-part Bools = 1** (all on);
   - `setN__<Bool>_off`: on top of all-on, set one clothing-part Bool to 0 (single-off);
   - `setN__naked`: all off (all clothing-part Bools = 0).
2. **Other Bool toggles**: `bool__<名>__on|off`, each flipped alone from the default state (`on`/`off`: the flip direction is determined by the
   `default_value` in `params.json`).
3. **Other radials**: `radial__<名>__<序号>`, taking each interval's recommended value from `slots.json` in the default state.
4. Plus one `default` base state with empty parameters.

Grouping (which parameters count as "full-set radial / clothing part"):

- If `--groups groups.json` is given, the file is used and `source` records the file path;
- otherwise **inferred from menu-path keywords** (see §6), and the inference together with its **evidence** is written to `groups_used.json` for human confirmation.
- Inference has two known blind spots, for which the program writes `notes`: no "full-set" radial found, no "clothing part" Bool found.

`groups.json` format (field names accept Chinese/English aliases):

```json
{ "outfit_radials": ["A2_Outfit"],
  "clothing_bools": ["A2_Coat", "A2_Top", "A2_Btm", "A2_Und", "A2_Sok", "A2_Sho"],
  "defaults": {},
  "notes": ["人工指定"] }
```

Aliases: `outfit_sets` / `整套`, `clothing_parts` / `服装部位`, `default_params` / `defaults`.

Besides the final groups, `groups_used.json` also writes `all_radials` / `all_bools` (to see what was missed/over-selected),
the match evidence for each parameter, `state_count`, `state_ids`, and each full set's `recommended`.

---
