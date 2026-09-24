> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/part-inventory-key-follow.md)

# T-05 part inventory · same-name key follow key_follow and known limitations <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §11.3 / §11.4. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [T-05 part inventory · output skeleton](part-inventory-output.md) · Next page: [T-12 Build-time capture and zero residue · principle and output](build-capture.md) <!-- nav -->

### 11.3 Same-name key follow `key_follow`

> Trigger: a part (clothing/shoes/accessory) carries a blend shape with the **same name** as the body, but has no MA BlendshapeSync, no clip curve of its own,
> and no MA ShapeChanger driving it; when the body's key moves, the part stays at a fixed value and clipping results (Project E's Re-Poppin bust keys and
> the shoes' `Foot_heel_OFF` are both of this kind). Procedure: `SOP/50_服装发型装配/胸型跟随_同名键无人同步.md`.

`key_follow` computes, for each SMR other than the **body SMR**, "piece key names ∩ body-written keys"; a hit with no writer on the piece → `candidates`
(**listed only, not judged right or wrong**: a fixed-value piece may be intentional, such as Project E's `(B)Cat`).

- **Body identification**: shared with T-10 poke / T2 `body=auto` via `AuditBodyPick.FindBodySmr` (task AY): first, among known body names
  `Body_b` / `Body_base` / `Body` (case-insensitive, covering Kaguya/Rurune, Kipfel, Milfy) whose **skin weights cover both
  feet and torso** (each share ≥ 0.1%), take the one with the most vertices; failing that, fall back to the original geometric heuristic (feet + torso regions, most vertices).
  *Why*: Kipfel's face mesh `Body` has more vertices than the real body `Body_Base`, so going only by name + vertex count picks the wrong one (AM lesson 1).
- **Body-written keys**: converges three sources —
  1. `blendShape.<键>` clip curves whose `path` = body (the descriptor's base/special animator layers + all
     MA MergeAnimators under the avatar, with path prefixes handled per Relative/Absolute; BlendTree child motions explicitly expanded as a fallback);
  2. `ModularAvatarShapeChanger` in the scene/prefab targeting the body (both Set and Delete are collected);
  3. **Body source keys declared by a piece's MA BlendshapeSync** (`ReferenceMesh` points to the body, and the body mesh really has that key).
     Item 3 is deliberate: some body keys (e.g. Rurune's `Breast_Big_____胸_大(mizuki)`) have no clip driving them,
     but a piece uses them as a sync source; only by counting them as body-written keys will the fixed piece `(B)Cat` be listed as a candidate for review.
- **Writers on the piece**: the `Bindings[]` of a `ModularAvatarBlendshapeSync` on the same object (`LocalBlendshape`, or
  `Blendshape` if empty) binds that key; or some clip curve has `path` = the piece and key = it; or a `ModularAvatarShapeChanger`
  targets the piece and writes it. Has a writer → goes into `synced` (with `piece_writers`); no writer → goes into `candidates`.
- **Fields**: `body` (body path), `body_written_keys[{key, writers[]}]`, `candidates[]` / `synced[]`
  (`renderer` / `key` / `piece_current_weight` / `body_writers[]` / `piece_writers[]`),
  `candidates_by_class` (rough split by key name: `bust`=`breast|chest|胸|bust`, `foot`=`foot|heel|toe|足|ヒール`,
  the rest `other`).
- **Geometric weighting (task AY, B-补-07)**: each `candidates[]` entry gets an extra `geom` object (`synced[]` doesn't), **fields are only added,
  original fields unchanged**, so that the verdict can downgrade candidates with "numeric mismatch but unchanged geometry" to benign/advisory:
  - `body_key_disp_mm`: when the body key goes 0→100, the displacement distribution of body vertices **within the piece's coverage area** `{p50,p95,max,count}` (mm,
    world space). The piece's coverage area is the body's main-region vertices corresponding to the piece's `covers` (dominant-bone vertex share ≥2%); omitted when there is no coverage area / the body lacks the key.
  - `piece_key_disp_mm`: the piece's own vertex displacement distribution when its key goes 0→100 `{p50,p95,max,count}` (mm).
  - `body_piece_dist_mm`: distribution of the distance from each piece vertex to the **body surface** (BVH nearest point), with the body key at 0 and at 100 respectively:
    `{at0:{p50,p95,max,count}, at100:{…}, p50_delta_mm}`. Small p50 difference between `at100` and `at0` → geometry unchanged.
    When there are more than 20,000 vertices, sampling is evenly spaced, and `count` is the actual sample count.
  - `available` / `body_delta_available` / `body_key` / `body_covered_verts` / `geometry_source`: availability and context;
    when the body snapshot fails, `available=false` and a warning is written.
  - **Snapshot basis (BF rework)**: both body and piece **uniformly use `BakeMesh`**, with the current blend shape weights and current pose; `geometry_source`
    writes `body=bake;piece=bake`; it no longer does "read `sharedMesh` if the mesh is readable (bind pose, no blend shapes)", which avoided the body/piece
    each taking a different path with inconsistent spaces. Multi-frame blend shapes take the **last frame** (full-weight frame), not frame 0.
  - Criterion: on numeric mismatch, look at `body_piece_dist_mm.p50_delta_mm` and `piece_key_disp_mm.max`; both < 1 mm →
    `benign_geometry`; either ≥ 1 mm → `mismatch`; missing `geom` → keep the original verdict and mark `no_geometry`.
    Project D's nipple covers before the fix went p50 5.74→14.95 mm, meaning the geometry really moves, judged mismatch; Project D's coat A `harness` had a constant p50, so benign
    (`对照:33-36`). The 1 mm threshold was set from measurements (`key_follow_verdict.GEOM_BENIGN_MM`) and is left for human review.
- **Read-only**: consistent with the rest of the inventory; no MarkSceneDirty, no asset changes, no temporary objects. The BVH used for geometric weighting is a pure in-memory structure.

### 11.4 Known limitations

- `closed` only looks at the mesh's own topology and does not judge "whether it wraps the foot"; shoe openings/sock openings both have boundary loops, distinguished by the 10% threshold. To find "shoe vs sock",
  use `shoe_like` (sole height difference); both are written out; don't substitute one for the other.
- When the mesh has no Read/Write enabled and `BakeMesh` also fails, `boundary_edge_ratio`/`closed` are `null` and `sole_*` are `null`;
  no guessing; weights fall back to `nearest_bone` (visible in `region_source`).
- **MR regions/closedness are approximations**: `covers` only assigns vertices by nearest bone, without skin weights (which don't exist anyway), so region boundaries are coarser than for SMR;
  when the mesh has no Read/Write enabled it falls back to `nearest_bone_object` (one object counts as only one region), and `boundary_edge_ratio`/`closed` are
  `null`. An MR's `sole_thickness_mm` only has a value when its approximate region includes the feet.
- **`part_like` only looks at names**: renaming an object / adding an ancestor name changes the judgment; it does not replace human review; `true` may still include tool objects (e.g. plugin meshes not
  in the exclusion table), and `false` may also wrongly hit real parts whose names collide.
- `body_keys` is all keys of the **body SMR mesh**; a wrong body identification (`FindBodySmr` picked the face mesh) writes the wrong key table. Identification is already done via
  `AuditBodyPick` (name candidates + foot/torso skin weights), but still check `body_path` and `body_key_count`; the key table does not include other pieces'
  (clothing/shoes) own keys. Imported armatures that the name fallback can't recognize still land on `Other`, in which case the piece's `covers`/sole may be inaccurate.
- `switch` path matching is an exact match between "avatar-root-relative path" and "Animator-root-relative path" (no fuzzy suffix);
  with nested Animators (Animator not at the avatar root), clip paths relative to that child Animator will be missed.
- When an MA ObjectToggle target can't be resolved under the avatar, only a warning is logged and it doesn't enter `toggle_targets`; MenuItem control is only judged by "same piece or ancestor".
- `key_follow`'s `candidates` include inactive hidden pieces, and do not judge "whether the piece sits outside the body"; fixed-value pieces are all listed; decide after looking at images/weights.
  The `blendshape_sync` in body writers means "the piece declares it reads this key from the body", not the driving curve itself. The geometric data in `candidates[].geom`
  is computed with `BakeMesh` under the current edit-time weights/pose (body key 100 uses the current snapshot + that key's full-step displacement), and may still differ from the pose measured in Play;
  it is only used to grade "numeric mismatches" and does not replace T1/T2 measurements.
- This file only did an offline csc compile; runtime behavior (BakeMesh coordinates, MR mesh readability, `animationClips` coverage, path matching)
  is pending Claude's measurement in Project A.
