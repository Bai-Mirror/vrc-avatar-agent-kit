> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/state-driver-reset.md)

# T1 · reset Modes and Switch-Residue Testing <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §3.0.3. § numbers follow the original text; for cross-page § references see the [document index](../README.md). <!-- nav -->
> Previous: [T1 · callback isolation, avatar resolution, GestureManager takeover](state-driver-isolation.md) · Next: [T1 pure-data probe overview · grab_chain / coincident](probes.md) <!-- nav -->

### 3.0.3 `reset` Modes and Switch-Residue Testing (task Q)

| `reset` | Behavior | Typical use |
|---|---|---|
| `declared` (default) | Before each state, resettable parameters are set back to `VRCExpressionParameters.defaultValue`; only if that cannot be read does it fall back to the startup actual value, with one warning per parameter | Routine multi-state comparison (state differences are attributed only to that state's own parameters) |
| `startup` | Set back to the actual values at the moment T1 starts (value source is the old behavior; driver exclusion still applies, see task AD) | Reproducing historical batches / aligning with old conclusions |
| `none` | No reset at all; states accumulate from the previous state | **Switch-residue testing** (deliberately carrying the previous gear's residue into the next gear) |

**When doing switch-residue testing**: you must use `"reset": "none"` and **list the sequence explicitly** in the request (each state writes only the parameters toggled for that gear;
array order is the actual toggle order). Otherwise the observed “residue” is left over from the previous run, not caused by this sequence, and the conclusion is untrustworthy.
In this case `reset_values_source` in `state_*.json` will be `none` and `reset_count=0`; `states.json.defaults_snapshot`
is still the declared defaults (for reference, not used for reset). Example:

```json
{ "tool": "state", "reset": "none", "avatar": "...", "out": "/abs/path",
  "states": [
    { "id": "s1_hood_on",   "params": { "A2_Outfit": 1.0 } },
    { "id": "s2_then_sok0", "params": { "A2_Sok": 0 } },
    { "id": "s3_only_hood","params": { "A2_Outfit": 0.214286 } }
  ] }
```

In `s3_only_hood`, `A2_Sok` stays at 0 from `s2` — exactly the “switch residue” phenomenon to observe. Run the same sequence again with
`"reset": "declared"` and compare, and you can separate “the gear was not cleaned up” from “the gear itself has no effect”.

**Task AD: why the default also skips “internal parameters maintained by parameter drivers”** (a different pitfall from the “default-value drift” above; don't mix them up):

- **Symptom**: `reset: declared` resets all of “expression parameters − VRChat built-ins” to their declared defaults before each state. Among them is a class of parameters
  that are not for the user to click but are internal state maintained by `VRCAvatarParameterDriver`. Measured on Project B_Milfy: the vendor parameter `Slippers_OFF`
  is written by the drivers in the ON/OFF states of the “shoes” part layer and in the whole-outfit switch layer; its declared default `0` = slippers shown; the reset writes it back to `0`, and
  **when switching within the same outfit the driver does not fire again** → in 12 of 13 outfits, “socks off only” showed the teddy-bear slippers (layered with that outfit's own shoes).
  Switching the same batch of states in real operation order with `reset: none`, the slippers do not appear → **a tool artifact**, not a project defect.
  Evidence: `_长程任务_20260918/审查产出/工程B/t1_sweep/` (artifact), `t1_slipper_seq/` (real order).
- **Why**: the semantics of the reset set is “the starting point of user-controllable parameters”, but driver internal state got mixed into the expression parameters — they are written by animator layers
  on switching, and there is no such thing as a “user starting point” for them. Resetting them unilaterally rewrites state without the driver re-firing.
- **Difference from “default-value drift”**: drift (task Q) is **taking the reset value from the wrong source** (using last run's residue as the default), drifting between two runs;
  this pitfall is **parameters that should not be reset got mixed into the reset set**, happening within the same run on every state. Both show up as “gear switch results are
  untrustworthy”, but the fixes differ: the former corrects the default-value source, the latter removes driven parameters from the reset set.
- **Fix**: in Play mode, scan the avatar's **post-build** playable-layer controllers (`descriptor.baseAnimationLayers` +
  `animatorController` of `specialAnimationLayers`; for `isDefault` layers, GM's
  `ModuleVrc3Styles.Data.ControllerOf(type)` gets the built-in controller GM actually uses; plus `Animator.runtimeAnimatorController`),
  collecting `VRCAvatarParameterDriver` on all states and sub-state machines and the parameter names they write (`name` of `Set`/`Add`/`Random`/`Copy`).
  The reset set for `reset:declared` (and `startup`) then subtracts the parameters that are “written and not directly clickable by the user”;
  if a parameter also appears directly in an Expressions menu control (the user can click it too) it is still reset, but listed in warnings and
  `states.json.driver_targets_user_clickable`. `reset_driver_targets: true` turns this exclusion off (old behavior).
  The scan only reads assets and does not modify the scene; if reflection cannot get GM's built-in controllers it only logs a warning, without affecting drivers in custom layer controllers.
- **Recommendation for whole-outfit / part combination sweeps**: **arrange the states within the same outfit in real operation order and use `reset: none`** — that way
  drivers re-fire on switching just as in VRChat, and what you observe is the real dress/undress result; or rely on this fix (`reset: declared`
  already skips driven parameters by default). Either one is enough, but **do not sweep combinations within the same outfit by “resetting every state from declared defaults”**
  — that is exactly the trigger condition of this pitfall.
