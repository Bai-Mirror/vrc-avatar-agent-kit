> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-containment-crossing.md)

# Probe containment hit-count basis · probe range <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) second half of §3.2.3 / §3.2.4. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe containment (containment ratio)](probe-containment.md) · Next page: [Probe poke (static poke-through patches) · criteria, request, and output](probe-poke.md) <!-- nav -->

**Hit count = the number of `flagged` region entries in which `crossing_edges ≥ min_crossings` and `crossing_ratio ≥ min_crossing_ratio`**
(`flag_basis` writes `crossing` / `crossing_below_threshold` / `no_crossing`). Reference values under the old basis are still viewable:
Project A MMN shoe toes `inside_ratio` 2% (defect) → 100% (after fix), sole of foot 85–87% (ankle above the shoe opening is outside, normal).
Tunable via `containment_pairs` (`[{garment, body?, region?}]`, where `region` can be `foot`/`hand` or a specific `HumanBodyBones` name such as `LeftToes`;
without `region`, it is inferred from that renderer's GameObject name), `containment_min_crossings`,
`containment_min_crossing_ratio`, `containment_min_ratio` (used only for the reference field),
`containment_min_region_verts`, `containment_layer` (default 30),
`containment_max_iter`, `containment_ray_budget` (default 3,000,000; exceeding it records `truncated=true`).
Cost: the containment ratio is still "hundreds to thousands of vertices per region × 6 directions × up to 30 rays per direction", and crossing counting adds on top
"about several thousand edges per region × 2", making it the heaviest of the two probe branches.
Automatic pairing is a **name heuristic**: if an accessory's own GameObject name contains a standalone shoe/boot/glove token (e.g. `PixelBoot`), it will still be
paired; to exclude it, use explicit `containment_pairs`.

The token matching logic has offline verification (without starting Unity): `AuditProbes.cs` compiled into `audit_T.dll`, with a small mono reflection test
(`_长程任务_20260918/派工/tmp/t_token_test.cs`) running 13 items, `ALL PASS` — `windowA`/`final-window` don't hit,
`shoes`/`Shoes`/`(B)Boots`/`loafer` hit feet, `Gloves` hits hands and not feet, `鞋`/`手袋` hit, and `PixelBoot`
hits because camel-case splitting yields `boot` (already stated above as a known cost of the heuristic).

#### 3.2.4 `range` — blend shape weights out of bounds

The VRChat client clamps blend shape weights to 0–100, while the editor preview doesn't, leading to "looks right in the editor, wrong after upload".
Iterates over the non-zero blend shapes of visible SMRs (`|w| > blendshape_epsilon`) and lists entries with `w < 0` or `w > 100`.
`probes.range` fields: `blendshape_epsilon`, `out_of_range[{renderer,shape,weight}]`, `hits`, `note`.
**Hit count = number of `out_of_range` entries**.
