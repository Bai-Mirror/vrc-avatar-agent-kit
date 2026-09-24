> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probes.md)

# T1 pure-data probe overview · grab_chain / coincident <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §3.2 / §3.2.1 / §3.2.2. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [T1 · reset mode and switch-residue tests](state-driver-reset.md) · Next page: [Probe containment (containment ratio)](probe-containment.md) <!-- nav -->

### 3.2 Pure-data probes (task R, request `probes`)

On 2026-09-18 in Project A, three defects the user "saw after turning around twice" were all located through **data**, while the renders actually produced illusions
(headwear screen grab, coat double-layer overlap, MMN shoe toes poking out). These probes solidify the measurement methods Claude wrote by hand in `execute_code` at the time:
they run alongside each state snapshot, write their results into that state's `probes` field, and `states.json` aggregates the hit counts.
Their common basis: **measure on the same state with parameters already applied**, all completing synchronously; temporary GameObjects / Meshes /
`Physics.queriesHitBackfaces` are all restored in `finally`, with no `MarkSceneDirty` and no scene saving.
Fields and hit-count definitions are as follows (hit counts are written into `states.json`, see §4).

#### 3.2.1 `grab_chain` — screen-grab chain

A screen-grab (GrabPass `_lilBackgroundTexture`) shader first grabs an image of the screen; **visible objects after the grab point, later in the queue,
won't appear in that image**, so they "disappear" when viewed through the screen-grab window. Criteria:

- Iterate over each material slot of visible renderers (`activeInHierarchy && enabled`); those whose `shader.name` matches the regex
  `grab_shader_regex` (default `lilToonGem|lilToonRefraction|lilToonMultiGem|lilToonMultiRefraction|LilBugShader/Refraction`) count as "screen-grab materials";
- **Grab point = the smallest `renderQueue` among screen-grab materials**;
- **`hidden_materials`** = material slots that are visible, not screen-grab, with `renderQueue ≥ grab point` and `< 4000` — these can't be seen through the screen-grab window;
- **`grab_point_lt_3000`**: flag for grab point < 3000 (a common danger signal; Project A's headwear was 2450).

`probes.grab_chain` fields: `grab_shader_regex`, `grab_materials[{renderer,slot,material,shader,render_queue}]`,
`grab_point_queue`, `grab_point_materials[]`, `hidden_materials[]`, `grab_point_lt_3000`, `hits`, `note`.
**Hit count = number of `hidden_materials` entries**. When there are no screen-grab materials, `grab_point_queue=null`, `hits=0`.
`renderQueue` is the queue in effect for the material (the override if there is one, otherwise the shader queue), the same basis as T3's transparency detection.

#### 3.2.2 `coincident` — two visible meshes that almost coincide

When the generator copies the vendor's ON clip verbatim, it also pulls the default-off alternative pieces into the toggle group, so the coat and its alternative are active at the same time, with 70% of vertices
within ≤0.5 mm of each other. Criteria:

- Only **visible SkinnedMeshRenderers** are compared pairwise; they first pass two gates: bounding boxes intersect, vertex count ratio within 0.5–2;
- The body mesh is excluded (request `body` or auto-identified, see the §3 table), so "the body and skin-tight clothing are naturally close" isn't counted;
- After `BakeMesh(mesh, true)` on both and converting to world coordinates, for each vertex of A a **`coincident_grid_mm` (default 2 mm)**
  grid hash looks up B's nearest vertex within the 27 neighboring cells, and the proportion with nearest distance ≤ `coincident_near_mm` (default 0.5 mm) is computed
  (the larger of A→B and B→A); **≥ `coincident_ratio` (default 0.5) records a hit**.

`probes.coincident` fields: `coincident_ratio_threshold`, `grid_mm`, `near_mm`, `body`, `body_source`,
`candidate_meshes`, `pairs_considered`, `pairs_evaluated`, `truncated`, `hits`,
`coincident_pairs[{a,b,vertices_a,vertices_b,a_to_b_0.5mm,b_to_a_0.5mm,ratio_0.5mm,ratio_1mm,ratio_2mm}]`, `note`.
**Hit count = number of `coincident_pairs` entries**. All three distance steps, 0.5 / 1 / 2 mm, are given, to show how tightly they overlap.
Tunable via `coincident_ratio` / `coincident_grid_mm` / `coincident_near_mm` / `coincident_max_pairs` (default 400;
exceeding it records `truncated=true`) / `coincident_exclude_regex`.
