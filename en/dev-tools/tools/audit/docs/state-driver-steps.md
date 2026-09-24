> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/state-driver-steps.md)

# T1 · What each state does, sanity checks, volatile blend shapes <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §3 "What each state does" / §3.0 / §3.0.1. § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous: [T1 state driver · request format](state-driver-request.md) · Next: [T1 · callback isolation, avatar resolution, GestureManager takeover](state-driver-isolation.md) <!-- nav -->

### What each state does (fixed order)

1. **Reset "user-controllable parameters"** (changed in task Q; changed again in task AD): the resettable set = parameters declared in the avatar's `VRCExpressionParameters.parameters[].name`
   **− VRChat built-in parameters** (GM's `Vrc3DefaultParams` list + official built-in names, see `AuditStateDriver.BuiltinParams`)
   **− parameters written by a `VRCAvatarParameterDriver` that the user cannot click directly** (task AD, when `reset_driver_targets=false`).
   **Reset value = the parameter's declared `defaultValue` in `VRCExpressionParameters`** (read via reflection; the field name follows the actual SDK).
   All other parameters (built-in parameters, Animator-only parameters) are never touched.
   *Why the second change (task AD, measured 2026-09-18)*: the expression parameters include a class of **internal state that is not for the user to click but is maintained by parameter drivers**.
   Instance (Project B_Milfy): the vendor parameter `Slippers_OFF` is written by the `VRCAvatarParameterDriver` on the ON/OFF states of the "shoes" part layer and on the whole-outfit switch layer;
   its declared default `0` = show slippers. The per-state reset flushed it back to `0`, and **when switching within the same outfit
   the driver does not fire again** → in 12 of 13 outfits, "socks off only" suddenly showed teddy-bear slippers (layered over that outfit's own shoes). The same sequence switched
   in real operation order with `reset:none` did not reproduce it → a pure **tool artifact**. So by default such parameters are excluded from the reset set; if a parameter
   also appears directly in an Expressions menu control (the user can click it too), it is still reset, but listed in warnings and in `states.json.driver_targets_user_clickable`.
   Scan scope and provenance: see §3.0.3.
   *Why the first change (task Q, measured 2026-09-18)*: the old implementation took the reset value as "the actual value read at the moment T1 started" (`initial_at_start`).
   When T1 was run several times in a row within the same Play session, the parameter values of the previous run's last state became the next run's "start values" — **drift across runs**:
   · one run ended at `A2_Outfit=1.0` (the full outfit with a hood; the hood-suppression layer turns the head accessory off) → in every later run the head accessory "didn't show",
   and was mistaken for a project defect and investigated for half an hour;
   · one run ended at `A2_Sok=0` → later the request `{"A2_Outfit":0.214286}` (intended: full outfit on) actually produced a "socks off" state,
   and all renders and agy conclusions were misaligned.
   Root cause: treating "leftovers from the last run" as "defaults". The declared `defaultValue` comes from the asset and is constant across runs; it is the true
   "starting point of each state".
   *Why this won't repeat the "built-in parameters written to 0" mistake*: built-in parameters (`ScaleFactorInverse`=1, `EyeHeightAsMeters`≈1.05,
   `Grounded`=1, `TrackingType`=3 …, set at runtime by GM's `InitForAvatar`) are simply **not in** the resettable set,
   so the reset never touches them; only parameters explicitly declared in the expression parameters and actually user-controllable use their declared defaults.
   *When the declared default cannot be read*: fall back to the parameter's actual value at T1 start, and **list each parameter name** in `warnings` (see also
   `states.json.reset_fallback_params`); that state records `reset_values_source=startup_value_fallback`.
   *Cost*: parameters that appear in the request but are not in the expression parameters are not automatically reset between states — either add them to the expression parameters or write them explicitly in every state.
   Each parameter in `param_defaults` carries five booleans `reset` / `builtin` / `declared_in_expression` / `driver_target` /
   `reset_excluded_driver_target` for cross-checking (the last two are from task AD).
2. **Apply this state's parameters**: prefer GM's `Vrc3Param.Set(module, float, obj)` (it fires `_onChange`, i.e. GM's simulation of
   `LayerControl` / `ParameterDriver`); fall back to `Animator.Set*` when GM does not have the parameter.
   Parameters **explicitly written** in the state are set regardless — even if they are VRChat built-in parameters (this is the only way to "capture what it looks like after a built-in parameter is toggled").
3. Wait `settle_frames` frames (counted with `Time.frameCount`, not by counting update calls).
4. Snapshot + **sanity check** (see §3.0).
5. **Readback assertion** (T-13, see §3.3): read back the actual value of every requested parameter of this state via GM/Animator and compare with the requested value using `readback_epsilon`;
   then compare `expect_visible` / `expect_hidden` against actual visibility. Mismatch → that state is `readback_failed`, and the whole batch is aborted.
6. **Sentinels** (T-13, see §3.3): run the positive/negative samples once, on the first state only; if any fails, the whole batch is aborted.
7. **Run probes** (task R, only when `probes` in the request is non-empty): first temporarily set blend shapes per `pre_probe_blendshapes` (task U),
   then run `grab_chain` / `coincident` / `containment` / `range` / `poke` / `shrink_cover` on this state; results go into the `probes` field of that state's JSON
   (§3.2); the temporary blend shapes are restored in `finally` whether probes succeed or fail. Probe failures only record a warning and never bring down T1.
   Of these, `shrink_cover` (task CS, T-33) additionally writes the full result to `<out>/shrink_cover_<stateId>.json`,
   and attaches a condensed row to the top-level `shrink_cover` field of that state's JSON (repeat passes write `.repeat.json`).
7b. **Run R9 candidates** (task BJ, only when `candidates` in the request is non-empty, see §3.4): for each candidate, apply its blend shapes → run one
   T-28a static poke (pairing replaced by the candidate's own `garment`/`covers`, `reference` forced) → restore immediately; results accumulate,
   and at the end of the batch are written per `part` to `<out>/r9_<part>.json`. Candidate failures only record a warning/inline `error`, never alter the snapshot, and never bring down T1.
8. If `volatile_probe=true`: on the first state of pass 0, after the snapshot, wait another `settle_frames` frames and take a second sample (see §3.0.1).

### 3.0 Sanity check (task G)

Validated immediately after each state is set and the frames have elapsed:

- all three components of the avatar root's `lossyScale` are within **0.5–2**;
- the world-space y of the `Head` bone is **> 0.2 m** above `Hips`.

If not satisfied → that state's `state_<id>.json` writes `sanity_failed: true` and `sanity_reasons: [...]`; after the whole batch,
`states.json` writes `sanity_failed` / `sanity_failures`, and **`status.json` is set to error** (`Tick` throws in `Phase.Done`
so the runner takes the error branch); it never silently continues. *Where the thresholds come from*: a normal avatar root scale is about 1; 0.5–2 covers ordinary body-proportion
adjustments and millimeter-level error; a Head-Hips difference of 0.2 m is far smaller than any normal humanoid skeleton (≈0.5 m+) and is only used to catch accidents of the
"skeleton collapsed to the origin" magnitude; it plays no part in aesthetic judgment.

### 3.0.1 Volatile blend shape detection (`volatile_probe`, task G)

Default `true`. On **the first state of pass 0**, take two snapshots in a row (`settle_frames` apart); blend shapes that differ between the two
(|Δ| > `blendshape_epsilon`) are marked volatile (mostly facial keys that auto-play over time, such as `AAO_Merged_Blink` / `EyeWide` / `BrowOuterUp`),
written to `states.json.volatile_blendshapes`, and excluded from

- the between-state `diffs.*.blendshape_changed`;
- the row-by-row `determinism` comparison when `repeat_check=true`.

Without this, the differences from running the same state twice would be nothing but this noise. Cost: only one extra `settle_frames`
wait on the first state. `"volatile_probe": false` turns it off.
