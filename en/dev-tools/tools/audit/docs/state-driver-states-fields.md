> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/state-driver-states-fields.md)

# T1 Output Format · states.json Field Conventions <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) latter part of §4 “states.json”. § numbers follow the original text; for cross-page § references see the [document index](../README.md). <!-- nav -->
> Previous: [T1 output format · states.json summary](state-driver-states-json.md) · Next: [T3 turntable render · request and output](turntable.md) <!-- nav -->

**`tool_version` / `version_check` / `aborted` / `abort_reason` (task AN = added in T-13)**: `tool_version` is the runtime
version stamp (structure in §3.3): when `match=false` and `version_check=true`, T1 does not run at all (`status=error`), so in a normal batch this
is always `match=true`; batches with `version_check=false` must be annotated manually. `aborted=true` means this batch of data was voided by sentinels / readback assertions
(`status.json.state="aborted"`), and `abort_reason` is a summary of the cause; in that case `state_*.json` / `states.json` still exist, but the conclusions are unusable.

**`gear_slots` / `readback_*` / `sentinel_*` / `state_canonicals` / `state_specs[].history` (task AN = added in T-13)**:
`gear_slots` is the gear table (`n` + `source`); `readback_failed` / `readback_failures` summarize the readback assertions;
`sentinel_results` see §3.3 (`config_errors` listed separately); `state_canonicals` = state id → canonical tuple of actual values;
`state_specs[].history` is the preceding state ids of that state (sequence-switch context). `sequence` echoes whether the request is a sequence.

**`probes_requested` / `probe_hits` / `probe_hit_totals` (added in task R)**: `probes_requested` is the probe names actually executed in this batch
(deduplicated, with unknown names filtered out); `probe_hits` is `probe name → {state id → hit count}`; `probe_hit_totals` is each probe's
total hit count in this batch (first pass, same convention as `diffs`). The definition of a hit differs per probe (see §3.2): `grab_chain` = number of visible material slots
invisible through the grab-pass window; `coincident` = number of coincident pairs; `containment` = number of body parts with penetration `flagged`
(task U; up to task T it was “number of parts with low containment ratio”); `range` = number of blend shapes with out-of-range weights. When no probes are requested these three are empty
(`[]` / `{}`), and old readers are unaffected.

**`param_defaults` (changed in task Q)**: `value` is this batch's **reset value** — resettable parameters take the declared `defaultValue` of the expression parameter
(`source=declared_default`; if the declared default cannot be read, it falls back to `initial_at_start` with `source=startup_value_fallback`,
and the parameter name goes into `warnings` and `reset_fallback_params`); non-resettable parameters (built-in / Animator-only) keep the startup actual value,
`source=initial_at_start`. `initial_at_start` is always the actual value at the moment T1 starts (for reference and troubleshooting only). Each entry also carries
five booleans: `reset` (whether it belongs to the “user-controllable, reset per state” set), `builtin` (whether it is a VRChat built-in parameter),
`declared_in_expression` (whether it is declared in the avatar's expression parameters), `driver_target` (whether it is written by `VRCAvatarParameterDriver`
, task AD), and `reset_excluded_driver_target` (whether it was excluded from the reset set for being “driven and not directly clickable by the user”, task AD).

**`reset_mode` / `reset_values_source` / `reset_count` / `reset_fallback_params` / `defaults_snapshot`
(added in task Q; extended in task AD)**: `reset_mode` is the mode in the request (see §3.0.3); `reset_values_source` is this batch's main source of reset values
(`declared_default` / `startup_value_fallback` / `none`); `reset_count` is the number of parameters actually reset successfully per state
(the same-named field in `state_<id>.json` is that state's value; after task AD the excluded driver parameters are dropped by default, so this number shrinks accordingly);
`reset_fallback_params` lists parameters whose “declared default could not be read and fell back to the startup actual value”; `defaults_snapshot` = `param name → reset value`
(only the set that actually participated in the reset in this batch; excluded driver parameters are not included). To check across Play sessions “where exactly this batch reset from,
and whether it is the same set of defaults as last time”, look at `defaults_snapshot`, to avoid again “last run's residue being taken as the default value”.
To check “whether built-in parameters were wrongly reset”, look for `sanity_failed=false`, with built-in parameters having `reset=false` and not in `defaults_snapshot`.

**`reset_driver_targets` / `reset_excluded_driver_targets` / `driver_targets` / `driver_targets_user_clickable` /
`driver_targets_scan` (added in task AD)**: `reset_driver_targets` echoes the request field (`false` = default, exclude driven parameters).
`driver_targets` = `param name → [locations writing it]`, each entry `{controller, layer, layer_type, state_machine, state,
change_type, source?}` (`source` appears only when `change_type=Copy`); collected from the written parameter names of `VRCAvatarParameterDriver` on all states and sub-state machines
of each post-build playable-layer controller (including the built-in default-layer controllers GM actually uses).
`reset_excluded_driver_targets` = parameters excluded from the reset set for this reason (these parameters are no longer reset, and `state_*.json.reset_count`
shrinks accordingly); `driver_targets_user_clickable` = driven parameters that also appear directly in Expressions menu controls and are therefore still reset but flagged
(each also appears as a single entry in `warnings`); `driver_targets_scan` = verifiable information about the scan itself `{controllers, states_scanned,
warnings}` (e.g. reflection failing to get default-layer controllers leaves traces only here and in `warnings`, not affecting the T1 core).

**Attribution convention of `no_effect_params` (important — don't read it as “per-parameter”)**:

- If the state, compared with `default`, has **no change at all in renderer visibility / enabled / materials / blend shapes** → **all** parameters set by this state are listed;
- A parameter that exists in neither `GM.Params` nor `Animator.parameters` → listed separately in `params_missing` and also counted as no_effect;
- `params_equal_default`: the applied value equals the reset default (the value in `defaults_snapshot`), so it naturally produces no change (most likely a mistake in the request).
- When multiple parameters are applied at once, changes **cannot** be split onto individual parameters; for per-parameter attribution put only one parameter per state (T4's single-parameter sweep).

`determinism` appears only when the request has `"repeat_check": true`: the same batch of states is run twice, and the serialized text of the two
`state_<id>.json` files is compared line by line — only a match shows the snapshot is deterministic. With `volatile_probe` on,
volatile blend shapes are excluded before comparison (otherwise two passes of the same state would inevitably differ).

---
