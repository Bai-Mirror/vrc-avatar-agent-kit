> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-poke.md)

# Probe poke (static poke-through patches) · criteria, request, and output <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) first part of §3.2.5. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe containment hit-count basis · probe range](probe-containment-crossing.md) · Next page: [Probe poke · hit count and area-threshold basis, Unity acceptance](probe-poke-area.md) <!-- nav -->

#### 3.2.5 `poke` — T-28a static poke-through patches (geometry v4 main criterion, task AA / 04 T-10)

**Why the criterion changed** (`工程C/_施工记录.md` 19:05/21:30, `03 §8.2`): the containment ratio gets dragged down by vendor Delete removing vertices
and by open styles (LUNALICE 9%/19% yet no clipping); crossing counts are **edge**-level statistics — skin-tight boots in the normal state have hundreds of grazing edges, while toes poking wholly out of the boot
give 0 (Winter negative sample: toes 199/202 edges, 0 after `Toe_heels=0`). So the main criterion became "shell signed depth × connected
patch area", with crossing counts and containment ratio demoted to **reference columns** (not judged).

- **Pairing**: only from declared `covers` (request `poke_covers:[{garment,covers:[…]}]`, or `poke_decl` pointing to
  `parts[].covers` in `decl.json`; `objects[]` accepts both strings and `{path,renderer}` objects, **one pair per object**,
  fixed in task CI). Without a declaration, it falls back to keywords in the renderer's
  GameObject name (shoe/boot/glove) and marks `pair_confidence=low`. **If the tested piece's and the region's bounding boxes don't overlap on any axis, the pairing is
  rejected** (`bbox_overlap=false`, the lesson from PixelBoot's 83×6 false hits). `foot`/`hand` expand into all specific body regions
  (`LeftFoot`/`LeftToes`…).
- **① Shell triangles**: temporary `MeshCollider`s are built only for the clothing under the active avatar root (**not** for the body or other roots), on layer `poke_layer`
  (default 30), `queriesHitBackfaces=true`. Each triangle's outward direction = "centroid − nearest point on the segment to that coverage region's anchor bone" (feet use
  `Foot→Toes`, hands use `Hand→MiddleProximal`, others parent→this bone); triangles whose winding normal is opposite to outward count as `normals_flipped`,
  and are flipped to match outward for use in pseudo-normals (mesh normal direction isn't trusted). From the centroid, offset +`origin_mm` (default 1 mm) along outward, 5 rays are cast
  (outward and a ±`cone_deg`=20° cone); if **any one** doesn't hit a clothing triangle of this root within `shell_ray_m` (default 0.5 m), it's shell.
  Linings, tops covered by a coat, and the inner walls of sleeves therefore don't count as shell — the body only poking through an inner layer without showing isn't a defect.
  (Task CI: all three of these judgments can be switched by request — `poke_shell_rule` = `any` (default) / `outward` / `majority`,
  `poke_normal_sign` = `parity` (default, from 09-20) / `anchor` / `winding`, and `poke_diag` outputs per-vertex evidence. **09-20 Claude measured and changed the default**: `anchor` misjudged both Project C's Winter boots (normal state 19.1 cm², Toe_heels=0 only 2.67) and Project A's sailor outfit (default state 82.6 cm², dose reversed); under `parity`, Winter normal state 0 / Toe_heels=0 61.3, MMN `=100` 0 / `=0` 5.63, calibration passed; the sailor outfit dropped to 33.4 cm² (2 patches, dose nearly flat, suspected self-occlusion under the same piece's bow, a known limitation); `winding` was worse on the sailor outfit (138.7). Original text: default keeps the old behavior;
  for diagnosis and fixes of false positives on tops see §3.2.5.1.)
- **② Signed depth d_v**: for each usable body vertex in a covered region (exclusion codes same as `containment`: NaN / NaNimation delete / zero weight /
  beyond 3 m), the distance to the nearest **shell** feature (classified as face/edge/vertex, nearest point via a self-built BVH), with sign = `dot(v − p, n_pseudo)`,
  where `n_pseudo` is the **angle-weighted pseudo-normal** (faces use the oriented normal, edges the sum of adjacent oriented normals, vertices the angle-weighted sum). If the nearest feature is a
  **boundary edge** (referenced by only 1 triangle: boot opening/skirt hem/cuff), it's recorded as `opening` and doesn't count as poking out; `opening` vertices with `d > 3τ` are additionally recorded as
  `opening_deep` (advisory, to avoid missing large-angle cases on sleeve walls). Initial τ: torso (Hips/Spine/Chest/UpperChest) `tau_torso_mm`=2,
  others `tau_limb_mm`=3; **measure first, then decide** — see the acceptance below.
- **③ Patches**: connected components (union-find) of `d_v > τ` on the body mesh adjacency graph; area = sum of body triangle areas within the component (cm²,
  independent of vertex density); reports `max/avg/min_depth_mm`, `region`, `sub_part`, `anchor_local_centroid`, `cams` (2 camera positions:
  `normal_back` = 0.35 m back from the centroid against the normal, `three_quarter`, fov 30). `sub_part` subdivides the foot: `LeftToes`→`toe`;
  `LeftFoot` is split by the parameter t along the `Foot→Toes` axis into `ball` (t>0.55) / `arch` / `ankle` (t<0.15); hand → `hand`.
- **⑦ Delete/NaN**: `body_excluded{nan,deleted,deleted_nanimated,deleted_zero_weight,beyond_3m,total}` counted separately.
- **Dose steps**: request `poke_doses:[100,75,50,25,0]` + `poke_perturb:{renderer,blendshape}` (or top-level
  `perturb:{renderer,blendshape,doses:[…]}`): sets the blend shape step by step, recomputes patches, and outputs `dose_response[{dose,
  total_patch_area_cm2,patch_count,opening_verts,opening_deep_verts}]` and `monotone_nondecreasing` (total area doesn't decrease with ascending dose)
  / `monotonicity`.
- **hide self-check**: after hiding `poke_hide` (renderer path or leaf name), that piece should no longer enter pairing; outputs
  `hide_selfcheck{path,found,garment_paired_after_hide,hidden_garment_patch_area_cm2,total_patch_area_cm2,ok}`.
- **Reference columns**: when `poke_reference=true` (default false, saving one heavy pass), the existing `containment`
  readings for the same pair are embedded into each pair's `reference{inside,inside_ratio,crossing_edges,crossing_ratio,max_crossing_depth_mm}`.
  When not embedded, request this probe together with `containment` (`probes:["containment","poke"]`) and let the caller merge.
  Crossings/containment ratio **don't participate in the judgment**.

Request (top-level `poke_*` or nested `poke:{}`, choose one; nested takes priority): `poke_min_patch_cm2`(0.5), `poke_tau_torso_mm`(2),
`poke_tau_limb_mm`(3), `poke_shell_ray_m`(0.5), `poke_cone_deg`(20), `poke_origin_mm`(1),
`poke_opening_deep_factor`(3), `poke_reference`(false), `poke_max_patches`(500), `poke_layer`(30),
`poke_hide`, `poke_include`/`poke_exclude` (by default excludes hair/face/eyes/head/particles, etc.), `poke_region_min_share`,
`poke_decl`, `poke_covers`, `poke_doses`, `poke_perturb`, `poke_ray_budget`(3e6).
Added in task CI: `poke_diag`(false), `poke_shell_rule`("any"/"outward"/"majority"), `poke_shell_majority_min`(3),
`poke_normal_sign`("anchor"/"winding"/"parity").
Added in task CW: `poke_min_patch_rule`("adaptive"/"legacy"), `poke_min_verts_for_patch`(8),
`poke_absolute_floor_cm2`(0.05), `poke_min_patch_area_cm2` (explicit override; the old `poke_min_patch_cm2` is still recognized).
See §3.2.5.2 and `patch_rule` below for details.

`probes.poke` fields: `method`, `thresholds{…}`, `pair_rule`, `shell_rule`, `depth_rule`, `patch_rule`,
`reference_rule`, `dose_rule`, `body`/`body_source` (body identification shared with T-05/T2 via `AuditBodyPick`: name candidates
`Body_b`/`Body_base`/`Body` pass the "foot + torso skin weight" gate, then fall back to the geometric heuristic; task AY / K19), `body_excluded{…}`,
`body_baked_vertices`,
`body_shared_vertices`, `body_region_source`, `garment_candidates[{garment,name,vertices,triangles}]`,
`rays_used`, `truncated`, `diag_rule`, `pairs[{garment,garment_name,pair_source,pair_confidence,pair_reason,bbox_overlap,
covers_regions,mesh_vertices,mesh_triangles,shell_faces,normals_flipped,normals_flipped_ratio,
shell_rule,shell_majority_min,normal_sign,shell_outward_escaped,shell_rescued_by_cone,shell_rescued_ratio,opening_verts,
opening_deep_verts,d_v_mm{p50,p95,p99,max,min,mean,count,outside},by_region[{region,coarse_part,
body_region_verts_total,excluded{…},d_v_mm{…},opening,opening_deep,patch_count,total_patch_area_cm2}],
by_sub_part[{sub_part,d_v_mm{…},opening,patch_count,total_patch_area_cm2,suspect_subthreshold,suspect_reason?}],
area_per_vert_cm2,area_per_vert_pos_source,region_verts,region_area_cm2,min_patch_area_cm2,min_patch_area_source,
dropped_components,dropped_max_area_cm2,dropped_total_area_cm2,dropped_max_depth_mm,suspect_subthreshold,
patches[{area_cm2,max_depth_mm,avg_depth_mm,min_depth_mm,verts,
region,sub_part,anchor_local_centroid{x,y,z},cams[{id,pos,look_at,dist_m,fov}],
diag[{world{x,y,z},d_v_mm,nearest_feature,nearest_feature_code,nearest_face,garment,tri_index,shell_ray,
shell_ray_kind,shell_ray_end{x,y,z},winding_dot_outward,normals_flipped,nearest_face_cone_rescued,opening,
pseudo_normal{x,y,z},inside_by_parity?,parity_agree_axes?}]（仅 poke.diag=true）}],patch_count,
total_patch_area_cm2,reference{…}}]` (`diag` only when poke.diag=true), `dose_response` (optional), `monotone_nondecreasing`/`monotonicity` (optional),
`hide_selfcheck` (optional), `shell_faces_total`, `normals_flipped_total`, `patch_count`,
`total_patch_area_cm2`, `opening_verts`, `opening_deep_verts`, `hits`.
