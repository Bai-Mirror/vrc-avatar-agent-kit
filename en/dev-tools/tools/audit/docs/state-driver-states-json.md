> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/state-driver-states-json.md)

# T1 output format · states.json summary <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §4 "states.json", first part. § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous: [T1 output format · `state_<id>.json`](state-driver-output.md) · Next: [T1 output format · states.json field semantics](state-driver-states-fields.md) <!-- nav -->

### `states.json` (summary)

```json
{
  "tool": "state", "avatar": "...", "out": "...",
  "gm_controlled": true, "gm_note": "took_over", "gm_created_by_audit": false, "driver": "gesture_manager",
  "settle_frames": 30, "blendshape_epsilon": 0.0001,
  "volatile_probe": true,
  "tool_version": { "source_hash": "<64-char sha256>", "deployed_files": 12,
                    "compile_time_utc": "2026-09-19T01:20:00Z",
                    "version_file": "Assets/AvatarAudit/VERSION",
                    "version_file_hash": "<same as above>", "version_file_time_utc": "2026-09-19T01:19:00Z",
                    "version_check": true, "match": true },
  "version_check": true, "sequence": false,
  "gear_slots": { "A2_Outfit": { "n": 14, "source": "inferred_from_batch" } },
  "readback_eps": 0.001, "readback_failed": false, "readback_failures": [],
  "sentinel_results": {
    "evaluated_on_state": "default", "any_failed": false, "config_errors": [],
    "positive": [ { "kind": "positive", "renderer": "Body", "shape": "sailor_shrink",
                    "expected_weight": 0, "observed_weight": 0, "pass": true } ],
    "negative": [ { "kind": "negative", "renderers": [ { "renderer": "outer", "visible_after_hide": false } ],
                    "pass": true } ]
  },
  "sentinel_failed": false, "aborted": false, "abort_reason": null,
  "state_canonicals": { "default": "(empty)", "headacc_on": "A2_HeadAcc@1/2" },
  "default_state": "default", "param_count": 750, "reset_param_count": 320,
  "reset_mode": "declared", "reset_values_source": "declared_default", "reset_fallback_params": [],
  "reset_driver_targets": false,
  "reset_excluded_driver_targets": ["Slippers_OFF"],
  "driver_targets_user_clickable": [],
  "driver_targets": {
    "Slippers_OFF": [ { "controller": "FX_Milfy", "layer": "Slippers_ON/OFF", "layer_type": "FX",
                        "state_machine": "Slippers_ON/OFF", "state": "Slippers_OFF", "change_type": "Set" } ]
  },
  "driver_targets_scan": { "controllers": ["FX_Milfy [baseAnimationLayers FX]"], "states_scanned": 512, "warnings": [] },
  "state_files": ["state_default.json", "state_headacc_on.json"],
  "probes_requested": ["grab_chain", "containment"],
  "probe_hits": { "grab_chain": { "default": 0, "headacc_on": 2 }, "containment": { "default": 0, "headacc_on": 1 } },
  "probe_hit_totals": { "grab_chain": 2, "containment": 1 },
  "states": ["default", "headacc_on"],
  "state_specs": [ { "id": "default", "pose": null, "params": {}, "history": [] },
                   { "id": "headacc_on", "pose": null, "params": { "A2_HeadAcc": 1 }, "history": ["default"] } ],
  "param_defaults": { "A2_HeadAcc": { "value": 0, "source": "declared_default", "initial_at_start": 0.35,
                                     "reset": true, "builtin": false, "declared_in_expression": true,
                                     "driver_target": false, "reset_excluded_driver_target": false } },
  "defaults_snapshot": { "A2_HeadAcc": 0, "A2_Outfit": 1, "A2_Sok": 1 },
  "volatile_blendshapes": [ { "path": "Body", "shape": "AAO_Merged_Blink.L", "first": 0.12, "second": 0.35 } ],
  "diffs": {
    "headacc_on": {
      "renderer_visibility_changed": [ { "path": "Hair/Acc", "from": false, "to": true, "detail": "..." } ],
      "renderer_enabled_changed": [],
      "material_changed": [],
      "blendshape_changed": [ { "path": "Body", "shape": "HeadAcc", "from": 0, "to": 1 } ],
      "bone_changed": [],
      "any_change": true
    }
  },
  "param_sources": { "headacc_on": { "A2_HeadAcc": "gesture_manager" } },
  "no_effect_params": [ { "state": "...", "param": "...", "reason": "..." } ],
  "params_missing":  [ { "state": "...", "param": "...", "reason": "..." } ],
  "params_equal_default": [ { "state": "...", "param": "...", "reason": "..." } ],
  "determinism": { "default": { "identical": true, "first_difference": null } },
  "sanity_failed": false,
  "sanity_failures": [],
  "warnings": []
}
```
