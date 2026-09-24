> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/state-driver-readback.md)

# T1 · Version Stamp, State Readback Assertions, Gear Slot Numbers, Sentinels, sequence/history <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §3.3 (in the original it follows §3.2.8 without its own heading; §2 cites it as “§3.3”). § numbers follow the original text; for cross-page § references see the [document index](../README.md). <!-- nav -->
> Previous: [Probe shrink_cover · output, diagnostics, self-check and calibration](probe-shrink-cover-output.md) · Next: [R9 foot/shoe selection candidates · request, execution and output](foot-shoe-candidates.md) <!-- nav -->

**Version stamp (refuse to run on mismatch)**: before running, compute the deterministic sha256 of the `Assets/AvatarAudit/` deployment tree (byte-for-byte the same method as `source_hash()` in `perception/sync_audit.py`
: sort by relative posix path, feed `path\0bytes\0` in order; exclude `VERSION` / `*.meta` /
`.DS_Store` / `__pycache__`), then compare with `hash` in `Assets/AvatarAudit/VERSION`. Mismatch (or missing directory / VERSION)
→ `Begin` throws, `status=error`, **the scene is not touched**. `"version_check": false` in the request skips it (offline / debugging), and that batch
must be marked “version stamp not passed”. Output header `states.json.tool_version`:
`{source_hash, deployed_files, compile_time_utc, version_file, version_file_hash, version_file_time_utc, version_check, match, note?}`;
`compile_time_utc` is the mtime of this tool's assembly `dll` (`Library/ScriptAssemblies/AvatarAudit.Editor.dll`).

*Why*: Unity does not recompile when the remote connection drops (02:07 record), so what runs may not be that source; writing the hash into the output lets T-14 and after-the-fact checks
tell “which tool version produced this batch of data”. **Cost**: if anyone hand-edits a single character in `Assets/AvatarAudit/`, the hash changes and T1 refuses to run
— this is the intended behavior (tool changes must go through `sync_audit.py` to re-sync).

**State readback assertions (per state)**: each parameter in `params` has its actual value read back through GM / Animator and compared with the requested value within `readback_epsilon`
(default 1e-3); `expect_visible` / `expect_hidden` (request-level default ∪ state-level, appended) are compared with the actual visibility
`visible = activeInHierarchy && enabled`. Any mismatch → that state gets `readback_failed=true`, details go into
`states.json.readback_failures`, and the whole batch gets `status=aborted`. `id_canonical` is also written: a canonical tuple built from **actual values**
(radial `param@slot/gears`, others `param=value`, sorted by parameter name).

**Parameters clamped / legitimately rewritten by a driver (task BJ, B-补-19)**: this kind of “readback ≠ requested value” is not a defect and should not void the whole batch.
Two ways to let it through; on a hit, `overridden` is recorded in that state's JSON:

1. **Explicit `expect_override`** (request-level + state-level, state-level takes precedence): `{param name: expected readback value or "any"}`.
   Readback equals the expected value (same tolerance as above) or `"any"` is written → let through. Example (Project B_Milfy, `t1_sto_bust` state 5):
   with stockings on, the `Clamp_Breast` layer holds `BreastSize` at 0.5, so requesting 1.0 reads back 0.5; after adding
   `"expect_override": { "BreastSize": 0.5 }` (or `"any"`) that state is no longer aborted.
2. **Automatic pass for driver Set (clamp mode)** (`readback_driver_override:true`, default): only when the readback value equals the **Set constant value** of some
   `VRCAvatarParameterDriver`, **and the state holding that Driver was entered because the same parameter went out of range
   (the entry transition condition does a `>` / `<` clamp comparison on that parameter)**, is it automatically judged a legitimate rewrite.
   Example: Project B `Clamp_Breast` layer; the condition for entering the `Clamp` state is `BreastSize > 0.5`, and the Driver in that state Sets
   `BreastSize` back to 0.5 — requesting 1.0 and reading back 0.5 is let through. The same example runs to completion without adding any request field.
   To restore the old strict behavior write `"readback_driver_override": false`.
   *Why it was narrowed*: the old implementation only compared “equals any Set constant in the whole graph”; for a Bool parameter, as soon as two Drivers Set 0/1 respectively,
   any readback value could be “explained”, making the readback assertion meaningless (cases like Project A `APS_FixBody`). A Bool entry transition is an
   `If`/`IfNot` equality check, not a clamp, so it is no longer let through; the same goes for `Equals`/`NotEqual`.

Pass details: top-level `overridden: [param names…]` in `state_<id>.json` (empty array if none); in `readback.params.<name>`,
`requested` / `actual` / `matched_requested` / `overridden` / `override_source`
(`expect_override_value` / `expect_override_any` / `driver_set`) / `override_expected` / `ok` (`true` after passing).
`states.json` additionally has `readback_overrides: [{state,param,requested,actual,override_expected,override_source}]`
and `readback_override_count`. **Note**: passing only affects the `readback_failed` verdict; `actual` is still the real readback value,
and `id_canonical` is still built from actual values.

**Gear slot numbers (i/n intervals)**: `gear_slots` gives the gear count explicitly; if omitted it is inferred from the values seen in this batch (only radials whose values “all lie in [0,1)
and all fall on the i/n grid (error ≤1e-3)” are recognized; 0/1 toggles get no slot number). Slot number = `round(v*n)` clamped to `[0,n-1]`
— `0.2857` is closer to `2/7` than to `1/7`, so it gets gear 2, avoiding “`0.2857 < 2/7` falls into the previous gear” (00 #5; `A2_Outfit` inferred as 14 gears).
If it cannot be inferred, no slot number is given (better missing than guessed); each entry in `states.json.gear_slots` carries `n` and `source` (`request` / `inferred_from_batch`).

**Sentinels (request-level, run only once on the first state, restored immediately afterwards, leaving no trace)**:

- **Positive sample** `{renderer, shape, weight}`: the renderer is resolved by name / hierarchy path (then substring, case-insensitive), the blend shape by exact →
  AAO-rename-restored matching; after the perturb it is read back, and it passes only if `|readback - weight| ≤ readback_epsilon`. Also supported:
  `{renderer, material_queue}`: changes `renderQueue` on a material **instance copy**, without modifying the shared asset.
- **Negative sample** `{renderer, hide:true}`: hides the matched renderers and immediately reads `visible`; passes only if all are false.
- Any failure (including configuration errors in `sentinels` entries) → `sentinel_failed=true`, whole batch `status=aborted`; details are written to
  `states.json.sentinel_results`.

*Why the whole batch is aborted rather than error*: the tool did not crash; it is “this batch of data cannot be trusted”. `state_*.json` / `states.json` are all kept,
`abort_reason` states the cause (sentinel not passed / how many readback mismatches), and T-14 voids the whole batch on that basis; `error` is reserved for initialization failure / timeout /
sanity collapse. Hence the `state` in `status.json` has three terminal states: `done` / `error` / **`aborted`**.

**sequence / history**: `reset:"none"` (or explicit `"sequence": true`) marks a sequence that “switches in real operation order”,
echoed in `states.json.sequence`. Every state gets `history` = the list of state ids before it in the request (present in both `state_<id>.json` and
`state_specs[]`), so T-14 can reconstruct the switching context.
