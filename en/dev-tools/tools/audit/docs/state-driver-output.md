> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/state-driver-output.md)

# T1 Output Format · `state_<id>.json` <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §4. § numbers follow the original text; for cross-page § references see the [document index](../README.md). <!-- nav -->
> Previous: [R9 foot/shoe selection · lessons, insole-surface convention and acceptance](foot-shoe-candidates-metrics.md) · Next: [T1 output format · states.json summary](state-driver-states-json.md) <!-- nav -->

## 4. T1 Output Format

### `state_<id>.json` (one per state; the second pass of `repeat_check` writes `state_<id>.repeat.json`)

```json
{
  "id": "headacc_on",
  "driver": "gesture_manager",
  "params_applied": { "A2_HeadAcc": 1 },
  "param_sources": { "A2_HeadAcc": "gesture_manager" },
  "missing_params": [],
  "warnings": [],
  "reset_values_source": "declared_default",
  "reset_count": 318,
  "history": ["default"],
  "renderers": [
    { "path": "Body", "key": "Body", "type": "SkinnedMeshRenderer",
      "active_in_hierarchy": true, "enabled": true, "visible": true,
      "materials": [ { "slot": 0, "null": false, "name": "Body",
                       "shader": "lilToon", "render_queue": 2000,
                       "v3": { "value": "visible", "hidden": false,
                               "reason": "lilToon 规则表内未命中任何不可见条件" } } ] }
  ],
  "blendshapes": { "Body": { "Eye_Blink": 0.35 } },
  "keys_all": {
    "Body": { "built_name": "Body", "built_path": "Body", "mesh": "Body",
              "source_name": "Body", "source_name_origin": "mesh_name_plain", "blendshape_count": 2,
              "keys": [ { "index": 0, "name": "Eye_Blink", "weight": 0.35 },
                        { "index": 1, "name": "HeadAcc", "weight": 1 } ],
              "v4": { "vertex_count": 12000, "buckets": { "non_finite": 0, "nanimated": 0, "zero_weight": 0 },
                      "excluded_total": 0, "kept": 12000, "kept_ratio": 1,
                      "source": "bind_pose_bone_weights",
                      "note": "用绑定姿态顶点 + 蒙皮主骨骼判三桶；未逐状态 BakeMesh，姿势引起的删除差异需 T-14/T2 复核" } }
  },
  "visibility": {
    "Body": { "V1_active_in_hierarchy": true, "V2_enabled": true, "visible": true,
              "V3_alpha_mask": "visible", "V3_hidden": false,
              "V4_kept_ratio": 1, "V4_buckets": { "non_finite": 0, "nanimated": 0, "zero_weight": 0 } }
  },
  "readback": {
    "params": { "A2_HeadAcc": { "requested": 1, "actual": 1, "delta": 0, "matched_requested": true,
                                "overridden": false, "ok": true,
                                "source": "gesture_manager", "gear_n": 2, "gear_slot": 1 } },
    "visibility": {},
    "id_canonical": "A2_HeadAcc@1/2",
    "ok": true
  },
  "readback_failed": false,
  "overridden": [],
  "id_canonical": "A2_HeadAcc@1/2",
  "bones_world": { "Hips": [0, 0.9, 0], "Head": [0, 1.5, 0.02] },
  "bones_missing": [],
  "avatar_position": [0, 0, 0],
  "avatar_rotation_euler": [0, 180, 0],
  "sanity_failed": false,
  "sanity_reasons": [],
  "probes": {
    "grab_chain": { "grab_point_queue": 3050, "hidden_materials": [], "grab_point_lt_3000": false, "hits": 0 },
    "range": { "out_of_range": [], "hits": 0 }
  }
}
```

- **`keys_all` (added in T-13)**: all blend shapes (including those at 0) of **every SMR** after the build; keys use the same
  convention as `renderers` / `blendshapes` (SMR path, `#2` appended on duplicate names). Each entry is `{built_name, built_path, mesh, source_name, source_name_origin,
  blendshape_count, keys:[{index,name,weight}], v4}`. `source_name` is a best-effort trace back to the **pre-build** object name/path:
  mesh name `AAO_Merged_<original>_<n>` → original name; otherwise the plain mesh name; otherwise the prefix of a path segment containing `$` (AAO merge naming
  `<original>$<mesh name>$<index>`); otherwise the object name assuming it was not renamed; if it cannot be traced, write `null` with `source_name_origin="unresolved"`
  (better missing than guessed). `source_name_origin` values: `mesh_name_aao_merged` / `mesh_name_plain` / `path_dollar_prefix`
  / `object_name_assumed_unchanged` / `unresolved`. Used by T-14 / AM for the “source name ↔ built name” mapping.
- **`visibility` (added in T-13)**: the four visibility components of each renderer. `V1_active_in_hierarchy` / `V2_enabled` /
  `visible` follow the same convention as `renderers`; `V3_alpha_mask` is `visible` / `hidden` / `unknown` (shader rule table below),
  and `V3_hidden` is its boolean projection (`null` for unknown); `V4_kept_ratio` / `V4_buckets` exist only for SMRs (same values as `keys_all[].v4`).
- **V3 shader rule table (covers only lilToon's “whole-part invisible” cases)**: `_Cutoff ≥ 1` → hidden; `_Color.a ≈ 0` → hidden;
  `_AlphaMaskMode ≠ 0` and the scale+offset of `_AlphaMask_ST` pushes the entire sampled UV range out of `[0,1]` → hidden;
  mask on but UV not pushed out → **unknown** (whether the whole part is invisible depends on the mask texture content, which the rule table cannot judge); non-lilToon → unknown.
  Each material slot's verdict and reason are written directly into `renderers[].materials[].v3`; the part-level `V3_alpha_mask` is a per-slot aggregate
  (any visible → visible, all hidden → hidden, otherwise unknown).
- **V4 (bake-exclusion bucket ratio / vertex kept ratio)**: `kept_ratio = (total − three buckets)/total`, the three buckets being `non_finite` (bind-pose
  vertex coordinates NaN/Inf), `nanimated` (the main skinning bone's parent chain contains `NaNimat`, i.e. MA ShapeChanger Delete), and `zero_weight`
  (skin weight sum is 0), with priority non_finite > nanimated > zero_weight (same convention as the probes). **Convention note**: determined statically from the bind pose
  + skeleton structure (computed only once per mesh per run), **no per-state BakeMesh**; when the mesh does not have Read/Write enabled,
  `kept_ratio=null`, `source="mesh_not_readable"` (cannot judge, so no guess). A Delete-type ShapeChanger can only be seen through V4
  (T1 weights cannot see Delete).
- **`readback` (added in T-13 / extended by task BJ)**: each entry in `params` is `{requested, actual, delta, matched_requested, overridden, ok,
  source, gear_n?, gear_slot?, override_source?, override_expected?}`; `visibility` is the comparison result against the expected sets;
  `id_canonical` is the canonical tuple of actual values. When `readback_failed=true` the whole batch is aborted. Parameters let through as legitimately rewritten by `expect_override` or a driver Set
  have `overridden=true`, `ok=true`, and are also collected in the top-level `overridden: [param names…]` (see §3.3).
- **`history` (added in T-13)**: the list of state ids that come before this state in the request (sequence-switch context).
- The `probes` field exists only when `probes` in the request is non-empty; when no probes are requested the output is byte-for-byte identical to the old version (does not affect existing diff/determinism comparisons).
- `pre_probe_blendshapes_applied` (task U) appears only when `pre_probe_blendshapes` was requested and at least one entry was set;
  each entry: `{requested_renderer, renderer, renderer_name, requested_shape, shape, weight, old_weight}`.
  `renderer` / `shape` are the actually matched path and the real name in the mesh (AAO-renamed pieces may yield multiple entries), and `old_weight` is the value before overriding.
  Entries that fail to match are not listed here but are written one by one in `warnings`.
- The keys of `probes` are the probe names listed in the request, and the values are each probe's output object, format per §3.2. If requested but failed, the key holds
  `{"error": "..."}`, and one entry is also left in `warnings`.
- `visible = activeInHierarchy && enabled` (audit convention); both components are kept as well, to locate which kind of invisibility it is.
- `blendshapes` only records keys with `|weight| > blendshape_epsilon` (default 1e-4) — **why not down to 0**:
  after animation curves stop, 1e-6-level floating-point noise often remains; bit-exact non-zero checks would fill the diff with noise.
- `path` is the hierarchy path relative to the avatar root; a renderer on the root is recorded as `.`; for identical name and path (one object carrying two Renderers), `#2` is appended.
