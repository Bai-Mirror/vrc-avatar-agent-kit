> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/fit-probe-selfcheck.md)

# T2 Fit Probe · Self-Check 2/3: Restore Table, Runtime Self-Checks A/B <!-- nav -->

> Formerly: T2 (originally `审查/README_T2.md`) §8 / §9 / self-check A / self-check B. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T2 Fit probe · self-check 1: API signatures](fit-probe-selfcheck-api.md) · Next: [T2 Fit probe · self-check C and v3 regression checklist](fit-probe-selfcheck-2.md) <!-- nav -->

## 8. Self-check 2: temporary changes → restore table

| # | Temporary change | Where registered | Restore action | Restore location |
|---|---|---|---|---|
| 1 | `Physics.queriesHitBackfaces = true` (main probe turns on back faces globally) | `Probe.Run` local `savedBackfaces` | Write back `savedBackfaces` | `finally` of `Probe.Run` |
| 2 | In `Calibrate`, first `queriesHitBackfaces=false` then `=true` | `Calibrate` local `saved` | Write back `saved` | `finally` of `Calibrate` |
| 3 | In the non-Play fallback, `queriesHitBackfaces=hitBackfaces` | `RayShooter.Shoot` local `saved` | Write back `saved` | `finally` of `Shoot` |
| 4 | `renderer.enabled = false` (`hide` self-check) | `_restores` (closure stores the old value) | Write back the old `enabled` | `Cleanup()` (reverse order) |
| 5 | `SetBlendShapeWeight(idx, weight)` (`perturb` self-check) | `_restores` (closure stores the old weight) | `SetBlendShapeWeight(idx, old)` | `Cleanup()` (reverse order) |
| 6 | One temporary GameObject per clothing piece (layer 30) | `Garment.colliderGo` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 7 | World-space collider Mesh per clothing piece | `Garment.colliderMesh` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 8 | Baked body Mesh (`BakeMesh` output) | `_bodyBaked` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 8b | **Temporary body GameObject (v2, layer 29)** | `_bodyColliderGo` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 8c | **Body collider Mesh (v2, world-space mesh after excluding vertices)** | `_bodyColliderMesh` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 9 | Temporary baked Mesh of clothing SMRs | local `baked` | `DestroyImmediate` | `finally` of `TryGetWorldMesh` |
| 10 | Mesh copy used for recalculating normals | local `cp` | `DestroyImmediate` (immediately after use) | inline in `TryGetWorldMesh` |
| 11 | Calibration quad GameObject + Mesh | local `cgo` / `cm` | `DestroyImmediate` | `finally` of `Calibrate` |
| 12 | `collider.enabled = true` while probing each clothing piece | local flow | `collider.enabled = false` (destroyed as a whole afterwards) | end of each clothing loop iteration |
| 13 | `hideFlags = HideAndDontSave` on temporary objects | — | Destroyed with the object, no separate restore needed | `DestroyTrash()` |
| 14 | **Body collider `enabled = true` for the whole round (v2)** | — | Destroyed with the object, no separate restore needed | `DestroyTrash()` |

**Idempotent**: `Cleanup()` has a `_cleaned` guard; both the `finally` of `Probe.Run` and
`IAuditTool.Cleanup()` at the end of AuditIO call it, so there's no double restore/double destroy.

**No changes to persistent scene data**: no `EditorSceneManager.MarkSceneDirty`, no `SaveScene`, no asset changes.

---

## 9. Self-check 3: how to run the three runtime self-checks

> Precondition: T1 has set the state and stays in Play mode. `<工程>` in the commands below means the root directory of the project being audited.
> Before each request, write the JSON into `<工程>/Library/AvatarAudit/request.json`, then execute
> `Tools/AvatarAudit/Run Request`. Replace `<out>` with the actual output directory.

### Self-check A — two runs in the same state give identical values (determinism / negative sample)

1. Using the **same state** and the same `state_id`, output to two directories `out_a` and `out_b` (neither with `perturb`/`hide`),
   run once each, getting `out_a/geo_default.json` and `out_b/geo_default.json`.
2. Compare (**excluding `timings_ms`**, since timings naturally vary):
   ```bash
   OUT_A=out_a OUT_B=out_b python3 - <<'PY'
   import json, os
   a=json.load(open(os.path.join(os.environ["OUT_A"],"geo_default.json")))
   b=json.load(open(os.path.join(os.environ["OUT_B"],"geo_default.json")))
   a.pop("timings_ms"); b.pop("timings_ms")
   print("IDENTICAL" if a==b else "DIFF")
   assert a==b, "两次运行结果不一致，工具不确定（先查 markers 并列深度 / warnings）"
   PY
   ```
3. **Pass criterion**: `IDENTICAL`. If it fails, first look at `markers` (the order of ties at the same depth), then check whether the two runs' `warnings`
   differ (e.g. the `RaycastCommand` fallback only triggered on the second run).

### Self-check B — after hiding the clothing under test, that clothing has `covered = 0` (guards against “deleting the object under test makes the metric better”)

1. Run the baseline, pick a clothing piece with `total.coverage > 0` from `geo_default.json`, and note its `path` (e.g. `Outfit/Skirt`).
2. Add `"hide": "<该 path>"` to the request, **everything else unchanged**, and run again with `state_id="hidecheck"`.
3. Check:
   ```bash
   OUT_A=out python3 - <<'PY'
   import json, os
   d=os.environ["OUT_A"]
   base=json.load(open(os.path.join(d,"geo_default.json")))
   hid =json.load(open(os.path.join(d,"geo_hidecheck.json")))
   target="Outfit/Skirt"          # ← replace with the path noted in step 1
   g=[x for x in hid["garments"] if x["path"]==target][0]
   print("skipped=",g["skipped"],"reason=",g["skip_reason"],
         "covered=",g["total"]["covered"],"pierced=",g["total"]["pierced"])
   assert g["total"]["covered"]==0 and g["total"]["pierced"]==0, "被隐藏的衣物仍有覆盖，hide 未生效"
   PY
   ```
4. **Pass criterion**: the hidden clothing has `total.covered == 0` and `total.pierced == 0` (and `skipped=true`);
   the other clothing's `total` should be **identical field by field** to the baseline (if the whole clothing piece were deleted outright, other pieces' values would change, which would also expose it).
