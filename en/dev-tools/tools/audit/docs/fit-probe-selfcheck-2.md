> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/fit-probe-selfcheck-2.md)

# T2 Fit Probe · Self-Check C and v3 Regression Checklist <!-- nav -->

> Formerly: T2 (originally `审查/README_T2.md`) self-check C / §9.5. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T2 Fit probe · self-check 2/3: restore table, runtime self-checks A/B](fit-probe-selfcheck.md) · Next: [T2 Fit probe · known limitations and first-run checks](fit-probe-limits.md) <!-- nav -->

### Self-check C — after pulling a shrink key fully in reverse, `pierced` rises clearly (positive sample)

1. Run the baseline and note the sum of `total.pierced` over all clothing.
2. Pick a “shrink/slim” blend shape on the **body**: its name usually contains `shrink`/`縮`/`细`/`body` or similar;
   you can also first look at the **non-zero** blend shapes on the body mesh in T1's `state_<id>.json` and pick one whose meaning is “make the body thinner”.
   Use `perturb` to set it to the **full reverse value** (inflating the body → the body pokes out through the clothing more easily):
   ```json
   "perturb": {"renderer":"Body", "blendshape":"<收缩键名>", "weight":-100}
   ```
   (If that key's positive direction is “enlarge”, use `100`; the principle is **pull it fully in the direction opposite to its currently effective direction**.)
   **Concrete sample from Project A** (used for the §9.5 regression): `{"renderer":"Body_b","blendshape":"AAO_Merged_sailor_shrink_1","weight":0}`
   — this key's baseline = 100 (AAO slimming the body for the sailor top); setting it to 0 cancels the slimming → the torso inflates.
3. Run again in the same state with `state_id="perturbcheck"`, compare the total `pierced`, and look separately at the `Chest` region of `sailor`:
   ```bash
   OUT_A=out python3 - <<'PY'
   import json, os
   d=os.environ["OUT_A"]
   base=json.load(open(os.path.join(d,"geo_default.json")))
   per =json.load(open(os.path.join(d,"geo_perturbcheck.json")))
   bs=sum(g["total"]["pierced"] for g in base["garments"])
   ps=sum(g["total"]["pierced"] for g in per["garments"])
   print("baseline pierced=",bs," perturbed pierced=",ps)
   assert ps > bs, "反向拉满收缩键后穿出数没上升：要么键选错，要么射线/判据有问题"
   def chest(doc, path):
       g=[x for x in doc["garments"] if x["path"]==path][0]
       return [r for r in g["regions"] if r["region"]=="Chest"][0]["pierced"]
   path="kaguya_cloth/sailor"   # ← Project A; for other projects, change to the corresponding top
   print("sailor/Chest pierced:", chest(base,path), "->", chest(per,path))
   assert chest(per,path) > chest(base,path), "Chest 穿出没上升"
   PY
   ```
4. **Pass criterion**: `ps > bs` and visible to the eye (recommended > baseline + a number of vertices; if the baseline is 0, it must be significantly greater than 0 after pulling fully);
   Project A's `sailor/Chest` should also rise clearly (2026-09-18 v2 measurement: 248 → 422).
   If unchanged, investigate in order: ① does that blend shape really act on this body mesh in this state (first look at its weight in the T1 snapshot);
   ② is `weights_source` `nearest_bone` (misassigned regions make statistics coarser, but total pierced should still rise);
   ③ are `calibration.hit_normal_usable` / `winding_sign` as expected.

> Only when all three pass is the tool considered “usable” on the target project. If any one fails, conclusions are uniformly downgraded to “unverified”.

### 9.5 v3 regression checklist (done by Claude in Unity, rerunning Project A in the same state)

> Precondition: T1 sets the state to `boot_off_hair2` (`A2_Boot=0`, `A2_Hair=0.3333`) and stays in Play;
> the request reuses `_长程任务_20260918/审查产出/requests_工程A/t2_a.json` (`body=Body_b`), outputting to a **new directory**
> (don't overwrite the archived `t2v2_a/`). Check item by item:

| # | Check | Expected | What to look at first if it fails |
|---|---|---|---|
| 1 | `class` of `kaguya_cloth/loafer` in `feet[]` | `footwear`; `class_source` expected `geometry` (`name` also acceptable), `thickness_p50_mm` should be several millimeters or more | whether `thickness_count` is 0 (if the sole isn't a closed surface, only the name fallback works); whether `coverage_regions` includes `LeftFoot`/`RightFoot` |
| 2 | `class` of `kaguya_cloth/stocking` in `feet[]` | `legwear`; `class_source` expected `geometry`, `thickness_p50_mm` < 2 | If `other`: thickness falls within `[2, sole_min_mm)` and the name regex didn't match (`stocking` should match, so this shouldn't happen) |
| 3 | Number of `feet[]` entries | ≥ 2 each for left/right (one each for loafer and stocking); “only one piece reported per foot” no longer occurs | A piece wasn't counted as covering that foot → look at its `coverage_regions` |
| 4 | `sailor`'s `RightHand` / `RightThumb*` | `covered`/`pierced` should be 0, with these vertices going into `out_of_scope` (`total.out_of_scope` ≥ roughly the old 169, also visible per region) | If still counted, sailor's skinning really does cover the hands (the earlier “cuff false hit” judgment must be rewritten) |
| 5 | `sailor`'s `Chest` | `pierced` on the same order as the v2 baseline (248); must not be zeroed by scope | whether `sailor`'s `coverage_regions` includes `Chest`, and whether `region_source` degraded |
| 6 | perturb self-check (self-check C above) | after `AAO_Merged_sailor_shrink_1: 100→0`, `sailor/Chest` pierced rises clearly (v2 measured 248→422), and total pierced rises | Same investigation order as self-check C |
| 7 | Determinism (self-check A above) | Two runs in the same state (excluding `timings_ms`) are byte-for-byte identical | The new `coverage_regions`/`feet[]` are output in a fixed order; if inconsistent, compare the two runs' `warnings` first |

> Items 1~3 are the core acceptance of the foot fix, and item 4 is the core of the coverage scope fix; items 5 and 6 prove the fix didn't cut away the positive samples along with it.
> If any fails, post the corresponding clothing's `coverage_regions` / `region_source` / `thickness_*` before drawing conclusions.

---
