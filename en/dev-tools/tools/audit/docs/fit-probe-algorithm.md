> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/fit-probe-algorithm.md)

# T2 Fit Probe · Algorithm and Criteria (1–6) <!-- nav -->

> Formerly: T2 (originally `审查/README_T2.md`) first half of §4. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T2 Fit probe AuditFitProbe · deployment, dispatch, requests](fit-probe.md) · Next: [T2 Fit probe · algorithm and criteria (7–10), v2 exclusions and rejections](fit-probe-algorithm-2.md) <!-- nav -->

## 4. Algorithm and criteria (why it judges this way)

1. **Determine the body** (`body=auto`; since v4 it goes through the shared criterion `AuditBodyPick`, task AY):
   - First build the humanoid bone set `{ GetBoneTransform(全部 HumanBodyBones) }` (the basis for the region mapping in item 1.5).
   - Among the **name candidates** (case-insensitive: `Body_b` / `Body_base` / `Body`), prefer the one whose **skinning weights cover both feet and torso**:
     map each of the candidate's bones to a humanoid region; the foot share and the torso share must each be ≥ 0.1% (`GetBonesPerVertex`/`GetAllBoneWeights`,
     falling back to `Mesh.boneWeights`); if several qualify, take the one with the most vertices.
   - If no name candidate qualifies (mesh not readable, etc.), fall back to a geometric heuristic: the candidate's `bones[]` region set contains **both** `LeftFoot` or
     `LeftLowerLeg`, and `Chest` or `Spine`; take the one with the most vertices.
   - All visible candidates (including unqualified ones), together with `regions` / `vertex_count` / `has_foot` / `has_torso` / `selected`,
     are written into the output `body_candidates` for checking; if the wrong one is chosen, specify it explicitly with `body`.
   - *Why it changed again*: v2, going only by “region set + most vertices”, would on the Kipfel base avatar take the face mesh `Body` (which has even more vertices than the real body
     `Body_Base`, with all its weights on Head/eyes) as the body. T-05 part inventory, T-10 poke, and T2 now all share
     `AuditBodyPick.FindBodySmr` instead of each fixing their own (K20 left over from AM lesson 1).
   - *Why v2 already didn't match bone Transforms exactly*: in Play mode MA/AAO insert `Head_Const` and merge bones into
     `Foot_L$Toe_L$85`, so `SMR.bones` often doesn't contain a Transform identical to `GetBoneTransform`.
1.5. **Region mapping** (v2): for each bone Transform, walk up the parent chain; the name of the **first** humanoid bone encountered
   (in the `HumanBodyBones` set) is that vertex's region; if you reach the avatar root without finding one, record `Other`; without a Humanoid
   Animator, it degrades to the raw bone name (staying usable). Results are cached per Transform. The output `region_bone_examples`
   lists up to 3 raw bone names per region, for checking the mapping. *Why*: the parent chains of intermediate bones like `Foot_L$Toe_L$85` and `Head_Const`
   eventually trace up to `Foot_L` / `Head`, so toe vertices are correctly assigned to `LeftFoot/LeftToes`,
   and the foot-specific checks no longer report “covered=0”.
2. **Clothing candidates**: all `activeInHierarchy && enabled` SMRs / MeshRenderers under the avatar, excluding the body itself and
   those whose names match `exclude_name_regex`; v2 additionally uses `include_only` (if non-empty) to keep only matches. **Collect first, then apply
   `hide`**, so hidden clothing still appears in the results with value 0, facilitating the self-check “covered must be 0 after hiding”.
3. **Bake the current pose**: SMRs use `BakeMesh(mesh, true)`, then `renderer.transform.localToWorldMatrix`
   to transform vertices/normals to world space; MeshRenderers use `MeshFilter.sharedMesh` + the same matrix.
   *Why multiply by `localToWorldMatrix` even with `useScale=true`*: the official documentation (2023.2, English) states that `useScale`
   is “compensate for the SMR Transform scale”; position/rotation are always compensated into local space; so the bake result is
   **local coordinates with the SMR scale already removed**, and multiplying by the full `localToWorldMatrix` gives exactly the world coordinates, without double scaling.
4. **Ray targets**: one temporary GameObject per clothing piece (layer 30), one temporary GameObject for the body (layer 29),
   each with a non-convex `MeshCollider`, `HideFlags.HideAndDontSave`, and `sharedMesh` being the world-space mesh (the temporary object itself has an
   identity transform). After `Physics.SyncTransforms()`, clothing pieces are enabled one at a time; the body collider stays enabled for the whole round. The two queries each use a mask:
   clothing queries `1<<30`, body queries `1<<29`.
   *Why dedicated layers*: to avoid hitting things like PhysBone Colliders in the scene; if the avatar itself already has colliders on layer 29/30,
   the output `warnings` will note it.
5. **Per body vertex** (`v`, `n`, in meters; results in millimeters): first exclude three kinds of invalid vertices (see 4.5), and cast rays only for the kept vertices.
   - Outward: from `v + n*0.5mm` along `n`, length `cover_mm`. A hit on the **back face of clothing** → `covered_inside` (body inside the clothing).
   - Inward: from `v - n*0.5mm` along `-n`, length `pierce_mm`. A hit on the **front face of clothing** → `pierced` (the clothing surface is inside the vertex,
     i.e. the vertex has poked through), depth `= hit distance + 0.5mm` (adding back the origin offset, measured from the body vertex); `< min_depth_mm` isn't counted.
   - v2's two rejections (see 4.5): in either direction, **hitting the body before the clothing hit** → that cast doesn't count, recorded as `rejected_through_body`;
     an inward hit on a front face but with the clothing normal **opposite** to the body vertex normal → doesn't count, recorded as `rejected_opposite_normal`.
   - **v3 coverage scope filter (applied before coverage-area statistics)**: per the “clothing's set of covered regions” obtained in §4.6, hits on body vertices whose region isn't in the set
     aren't counted in `covered`/`pierced`/`rejected_*`, but recorded as `out_of_scope` instead (output both per piece in `total` and per region).
   - **Coverage area = covered_inside ∪ pierced**; only vertices within the coverage area are counted. `covered` = count of covered_inside,
     `coverage` = count of the union, `pierce_ratio = pierced / coverage`; rejection counts aren't included in `coverage` and are output separately.
   - `pierced` depths go into `max_depth_mm` and `p95_depth_mm` (linearly interpolated quantile); when `p95_depth_mm >= 0.9*pierce_mm`,
     that region is flagged `depth_saturated:true` (see item 3 of 4.5).
   - Regions use the parent-chain mapping of 1.5. Weights prefer `GetBonesPerVertex/GetAllBoneWeights` (each vertex already sorted by weight descending),
     falling back to `Mesh.boneWeights`; when neither is readable (mesh has Read/Write off), the **nearest bone** is used as an approximation, with
     `weights_source` marked `nearest_bone` and an explanation in `warnings`.
6. **How front/back faces are judged**: preferably by the sign of `dot(ray direction, hit.normal)` (consistent with the task brief). But with
   `queriesHitBackfaces=true`, whether Unity flips `hit.normal` toward the ray, and how cross-product winding corresponds to the front face, aren't guaranteed across versions;
   once the sign is reversed you get a silent “all 0” error. So a **calibration** (`Calibrate`) is done up front: build a quad,
   first turn off back-face hits to determine which side of the cross-product normal the front face is on (setting `winding_sign`), then turn on back-face hits to see whether `hit.normal` points to the front face
   (setting `hit_normal_usable`). Only if calibration fails does it fall back to the task brief default. The result is written into the output's `calibration`.
   The “same-direction normal” criterion in 4.5 also uses this calibrated outward normal.
