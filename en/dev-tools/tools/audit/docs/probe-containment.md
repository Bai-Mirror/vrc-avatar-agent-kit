> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-containment.md)

# Probe containment (containment ratio) <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) first half of §3.2.3. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [T1 pure-data probe overview · grab_chain / coincident](probes.md) · Next page: [Probe containment hit-count basis · probe range](probe-containment-crossing.md) <!-- nav -->

#### 3.2.3 `containment` — does a closed piece wrap the body region / does the body cross the clothing surface

Corresponds to the defect where the vendor hangs `Foot_heel_OFF` only on the socks, yet lets the foot return to the high-heel pose when socks are off in shoes, so the whole toe section pokes out of a closed-toe shoe.
T2's "body vertex searches along the normal for the clothing surface" has a structural blind spot (the toes are some distance from the shoe surface), so it initially switched to a **containment test**;
on 2026-09-18 a Project C measurement found that the containment ratio gets dragged down by two situations unrelated to clipping — "the vendor Deletes the vertices inside the shoe" and "open / non-watertight meshes" —
so task U switched the criterion again to **surface crossing counts** (see below), and the containment ratio was demoted to a reference field.

- **Pairing**: request `containment_pairs`; by default it automatically takes visible renderers, **looking only at the name of the GameObject the renderer is on**, whose tokens hit
  shoe/glove keywords. Matching rules align with `match_any` in `t5_shapekey_matrix.py`: names are split into tokens by "camel case / underscore /
  space / brackets", ASCII keywords match whole tokens (length ≥4 allows a token to have the keyword as prefix: `Shoes`→`shoe`,
  `Boots`→`boot`, `Gloves`→`glove`), and CJK (`靴`/`鞋`/`手袋`) matches by substring. **The hierarchy path is deliberately not used**: ancestor names in the path would
  mis-pair child objects (in Project A, the screen-grab windows of the hair accessory `Acc_发饰_PixelBoot/.../multi-window/windowA` were once taken for boots: `windowA`–`E`
  at 83 states each and `final-window` at 56 states, each state falsely hitting the two regions LeftFoot/RightFoot, pushing the total hits up to 1160).
  A hit on a glove keyword goes to `hand`, otherwise to `foot`. Each pair outputs
  `pair_source` (`request`|`name_token`), `pair_matched_token` (the word hit), and `pair_region_source`; for explicit
  `containment_pairs` without `region`, the renderer's GameObject name is also used to infer it by the same rule, and it is skipped only if it can't be inferred.
- **Regions**: for each vertex of the body mesh (`body` or auto-identified), its **dominant skin-weight bone** is traced up the parent chain to the nearest humanoid region;
  **weights are read from `sharedMesh`, not from the `BakeMesh` output** (the baked mesh is a static snapshot and isn't guaranteed to have usable bone weights; reading empty
  weights silently degrades to "find the nearest bone by world position", making regions drift with the pose; this basis matches T2). Feet are split into **`Foot` (Foot bone)
  and `Toes` (Toe bone and its children), counted separately**; hands into `Hand` and the `Thumb/Index/Middle/Ring/Little` finger joints. Each region
  outputs the bone names it used, `region_bones` (dominant-bone Transform names after merging along the parent chain, deduplicated and ascending).
- **Vertex counts vary with state**: `body_region_verts_total` = the **raw total vertex count** of the region in the body mesh, determined only by the body mesh and
  skin weights, **not varying with state**; `verts` = the number actually participating in the ray test; `excluded` = the parts removed and why
  (`nan` non-finite coordinates; `deleted` = weight 0, or the dominant bone or its parent chain contains `NaNimat`; `beyond_3m` = more than 3 m from Hips).
  Relationship: `verts = body_region_verts_total - excluded.total`. The top level also has `body_excluded` (breakdown for the whole body),
  `body_region_source` (`bone_weights`|`bone_weights_legacy`|`nearest_bone`), `body_shared_vertices` /
  `body_baked_vertices`.
  **Why this is a separate item**: Project A's `Body_b` uses MA ShapeChanger, by sock state (visible in the project:
  `Property Overlay controlled by socks VertexFilterByShape: toe_/toe_short_/foot_/ankle_`, bone
  `.../Foot_L/NaNimation buffer/NaNimatedBone for Body_b (...).deletedShape.toe_`), to move foot/toe vertices away with
  NaNimation; when socks are on, the toes are deleted. The old version only treated "finite coordinates" as usable, and **silently discarded** the rest without reporting, so the same foot
  `LeftFoot` jumped between 3222 (socks off) and 2033 (socks on). Now the total is constant and the difference goes into `excluded.deleted_nanimated`.
- **Locating outside vertices**: each region additionally gives `outside_centroid_local` (mean of outside vertices converted into the local frame of **that region's anchor bone**, in meters;
  `null` when there are no outside vertices) and `outside_extent` (bounding box size of the outside points), used to tell whether it's the toe tip, heel, or instep that sticks out.
  The anchor bone is the `HumanBodyBones` corresponding to the region (`LeftToes` takes the Toe bone); if unavailable, it falls back to the avatar/body root; when a bone has non-unit scale,
  the local coordinates are not strictly meters.
- The clothing's baked mesh is converted to world coordinates and a **temporary MeshCollider** is built (temporary layer, `Physics.queriesHitBackfaces=true`, restored and destroyed at the end);
- **Crossing count (task U, the criterion)**: take the usable triangle edges of the region (both ends `ExOk`, same region, shared edges counted once),
  and for each edge cast **one segment ray A→B and one B→A** (`Physics.Raycast` limited to the edge length, `queriesHitBackfaces=true`);
  a hit on the clothing in either direction records one **crossing edge**. Region criterion = **`crossing_edges ≥ containment_min_crossings` (default 20)
  and `crossing_ratio ≥ containment_min_crossing_ratio` (default 0.01)**.
- Each region outputs `edges` (total testable edges), `crossing_edges`, `crossing_ratio`;
  `crossing_midpoint_local` (mean of crossing-edge midpoints converted into the region anchor bone's local frame, in meters) and `crossing_extent` (bounding box size of the midpoints)
  locate whether the crossing happens at the toe tip / heel / instep; `max_crossing_depth_mm` is the **poke-out depth** (mm): among crossing edges, the distance from the endpoint judged outside
  to the hit point on the fabric; when both ends are judged outside, take the smaller of the two (skin-tight grazing); when both ends are judged inside, record 0.
- Containment ratio (**reference field, no longer participates in flagged**): from each target body vertex, cast **iterative rays in six directions ±X ±Y ±Z and count intersections**;
  after a hit, advance `1e-4 m` along the direction from the hit point and cast again, up to 30 times per direction; an odd number of intersections in one direction counts as 1 vote, **≥4 votes means inside**;
  outputs `verts / inside / inside_ratio`. It is still an intuitive reading of "how many body vertices in this region are inside the clothing", just no longer used as the clipping criterion.
- **Why the criterion was switched from containment ratio to crossings** (2026-09-18 Project C measurement): after the vendor's MA ShapeChanger uses NaNimation to **Delete**
  the foot vertices inside the shoe, the remaining body vertices are all outside the shoe, so `inside_ratio` is naturally only single digits (LUNALICE 9%/19%,
  and both human and agy image review judged no clipping); open styles (low-cut / open-toe / strappy) and non-watertight shoe meshes are likewise naturally low
  (Silent Twilight shoes 3–6%, no clipping in images). Real clipping (Project A MMN bare foot in shoes, toes breaking through a closed toe box) is
  **the body surface intersecting the shoe surface**, which will certainly make the region's triangle edges hit the shoe surface.
- **Threshold trade-off (why 20 edges + 1%)**: the two gates complement each other — `20 edges` blocks scattered / single-triangle-level grazing errors
  (numerical coplanarity, a vertex sitting exactly on the line can cause 2–4 edge hits); `1%` blocks a small amount of grazing in a large region being amplified by the absolute count
  (a foot region has about 3000–6000 edges; 1% ≈ 30–60 edges, the same order of magnitude as 20). **Grazing error on skin-tight pieces (socks, bodysuits)**
  shows up as single digits to a dozen or so crossing edges, below 20 and not flagged; **open pieces are unaffected**: the body passes through the mesh's **opening**,
  where there are no faces, so segments don't intersect the fabric and `crossing_edges` is usually 0; it only counts when the body presses into the solid fabric at the opening's edge.
- **`open_mesh_suspect` = share of boundary edges (referenced by only 1 triangle) in the clothing mesh**, `nonmanifold_edge_ratio` =
  share of edges referenced by >2 triangles. These two numbers are still output, but only as a hint of "is this pair of shoes an open piece", not part of the judgment.

`probes.containment` fields: `method`, `pair_rule`, `region_rule`, `crossing_rule`, `flag_rule`,
`inside_votes_threshold`(4), `ray_iter_max`(30), `ray_advance_m`, `min_region_verts`, `min_ratio`(0.5, reference),
`min_crossings`(20), `min_crossing_ratio`(0.01), `ray_budget`, `body`, `body_source`, `body_shared_vertices`,
`body_baked_vertices`, `body_region_source`, `body_max_distance_m`, `body_excluded{nan,deleted,
deleted_nanimated,deleted_zero_weight,beyond_3m,total}`, `rays_used`, `truncated`,
`pairs[{garment,garment_name,body,region_filter,pair_source,pair_matched_token,pair_region_source,mesh_vertices,
mesh_triangles,open_mesh_suspect,nonmanifold_edge_ratio,verts,inside,inside_ratio,edges,crossing_edges,
crossing_ratio,by_region[{region,region_bones,body_region_verts_total,excluded{nan,deleted,deleted_nanimated,
deleted_zero_weight,beyond_3m,total},verts,inside,inside_ratio,edges,crossing_edges,crossing_ratio,
max_crossing_depth_mm,crossing_midpoint_local,crossing_extent,flagged,flag_basis,outside_centroid_local,
outside_extent}],hits,note?}]`, `hits`.
