> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-delete-coverage.md)

# Probe delete_coverage (MA ShapeChanger delete-region coverage) <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §3.2.7. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Project A regression acceptance basis](regression-project-a.md) · Next page: [Probe shrink_cover (shrink-key occlusion consistency) · request and parameters](probe-shrink-cover.md) <!-- nav -->

#### 3.2.7 `delete_coverage` — is the MA ShapeChanger delete region covered by the host piece (task BQ, B-补-20)

`ModularAvatarShapeChanger` with `ChangeType=Delete` processes a blend shape of the target mesh (usually the body `Body_base`)
at build time: constant (constant active) uses `RemoveVertices` to delete primitives, toggleable uses NaNimation. If the primitives moved by this blend shape
(= the **delete region**) are not covered by **the writer's own piece** in the new state, a gap is exposed. On 2026-09-19 Project B step 6 Snowflake
Romance was exactly this type: the footless stockings `Socks` deleted the body's `Ankle_L/R`, while the ankles were actually covered by the boots; with "shoes off, socks on" the ankles were deleted with nothing covering them
(`审查产出/工程B/seq_snowflake_delete/09_*`); the fix was to move the Delete to `Boots`. This probe turns that into a number.

**Measurement basis (task BV rework)**: **measured only in edit mode**, menu `Tools/AvatarAudit/Delete Coverage (Edit Mode)`.
In Play / after the build, MA's Delete has already taken effect — constant Delete uses `RemoveVertices` to delete vertices, toggleable Delete uses NaNimation
(bone scale=NaN); the original mesh no longer exists and vertex indices no longer line up; so the T1 probe name `delete_coverage` is kept, but when
called in Play it directly returns `{ "undecidable": "MA 已处理网格", ... }` (MA has already processed the mesh) and does no geometric measurement. In edit mode the original mesh and
the MA `ModularAvatarShapeChanger` components are still there, and combinations of the writer hosts' `activeSelf` simulate "piece on / piece off", with no need to enter Play.

Request file (optional) `<工程>/Library/AvatarAudit/delete_coverage_request.json`; the menu reads it automatically, writes output to
`<工程>/Library/AvatarAudit/delete_coverage_edit.json`, and prints to the Console:

```json
{"tool":"delete_coverage",
 "delete_coverage_threshold_mm":15, "delete_coverage_min_ratio":0.2,
 "states":[{"id":"s6_sok_on_sho_off","params":{"Socks":true,"Boots":false}}]}
```

`states[].params` (alias `hosts`) matches "writer hosts" by relative path / leaf name / substring to on/off (bool or 0/1);
hosts not named keep their current value in the edit scene; without `states`, only one "current edit state" is run.

**Criterion (aligned with MA 1.18 Delete semantics, no longer made up by us)**: delete region = using the writer's `ModularAvatarShapeChanger.m_threshold`
(field read via reflection; default `0.01`, **in mesh local units**) as the threshold, take vertices whose raw delta length² of the target blend shape > `m_threshold²`,
then by primitive-level selection (`VertexFilterByShape` default AnyVertex: if any vertex of a primitive hits, the whole primitive counts) include **all vertices** of the hit primitives;
positions are the world coordinates at **weight 0** of that key (where the gap is). Delta is read preferably from
`Mesh.GetBlendShapeFrameVertices` (same source as MA); when the mesh isn't readable, it falls back to the local difference of `BakeMesh(m,true)` at 0/100
(`region_source` records `*_fallback`). Host = all Renderers (SMR / MeshRenderer) in **the writer GameObject and its subtree**
— only the writer's own piece counts; boots don't count as the socks' host; `uncovered_ratio` = the share of delete-region vertices whose nearest distance to the host surface (vertex to triangle,
30 mm spatial hash + brute-force fallback) exceeds `threshold_mm`; also gives `p50_mm` / `p95_mm` / `max_mm` / the world coordinates of the first 5 uncovered
vertices `sample_uncovered`. When the writer is on a **mesh-less container**, it still outputs a row, marked `host_has_no_mesh:true`, not skipped.
When the host is invisible (`activeInHierarchy && enabled` all false), it's still computed, marked `host_visible:false` (MA reactive: when the host
is hidden the delete doesn't take effect anyway; that row is for reference only).

Edit-mode output fields: `tool`, `mode:"edit"`, `avatar`, `scene`, `threshold_mm`, `min_ratio`, `region_rule`,
`writer_count`, `state_count`, `host_has_no_mesh`, `hits`, `states[{id,hosts,writer_count,host_has_no_mesh,hits,
writers[...]}]`; each writer row contains
`writer_path,host_path,host_visible,host_renderers,host_has_no_mesh,target,key,threshold_local,threshold_mm,
deleted_vertices,primitive_count,region_source,uncovered_vertices,uncovered_ratio,p50_mm,p95_mm,max_mm,
sample_uncovered,error?`. `hits` = number of rows where **host_visible and deleted_vertices>0 and uncovered_ratio ≥ min_ratio**.
In Play the T1 probe returns `{undecidable:"MA 已处理网格", writers:[], hits:0}` (the probe doesn't blow up T1).

Request sample (read by the edit-mode menu, **no longer enters Play**; thresholds optional):

```json
{"tool":"delete_coverage",
 "delete_coverage_threshold_mm":15, "delete_coverage_min_ratio":0.2,
 "states":[{"id":"s6_sok_on_sho_off","params":{"Socks":true,"Boots":false}},
           {"id":"s6_all_on","params":{"Socks":true,"Boots":true}}]}
```

**[Claude·Unity·edit-mode acceptance · Project B step 6 (Snowflake Romance) — safe version, overwrites no tracked files]**:

> Hard prerequisite: before every command, run `git status --porcelain`; as soon as you see
> `工程B/Assets/_Work/工程B_Milfy.unity` modified, stop immediately; don't overwrite it with `git checkout`.
> The steps below only create **untracked** files and write to `Library/` and output directories.

1. `python3 开发工具/通用工具/审查/perception/sync_audit.py 工程B` (syncs `审查/unity/`, which contains this probe,
   into the project; if another DSH is currently modifying `审查/unity`, wait for it to deliver first). Unity refresh + compile,
   confirm **0 errors**.
2. **Fixed version (Boots deletes Ankle)**: open `工程B/Assets/_Work/工程B_Milfy.unity` in Unity,
   create the untracked request file `工程B/Library/AvatarAudit/delete_coverage_request.json`:
   ```json
   {"tool":"delete_coverage","delete_coverage_threshold_mm":15,"delete_coverage_min_ratio":0.2,
    "states":[{"id":"s6_sok_on_sho_off","params":{"Socks":true,"Boots":false}}]}
   ```
   Run the menu `Tools/AvatarAudit/Delete Coverage (Edit Mode)`. Expectation: in `states[0].writers`, the row whose
   `writer_path` contains `Boots` with `key=Ankle_L/Ankle_R` has `host_visible=true` and **low `uncovered_ratio`**;
   `region_source` should be `asset_delta_primitive` (or `*_fallback_primitive`), `threshold_local=0.01`.
3. **Pre-fix version (Socks still deletes Ankle) comparison**: **use read-only `git show` to export an untracked copy of the project/scene** (see below),
   and run the same request in the copy. **Don't touch the real project files**.
   - Export only the scene (sufficient; the MA components are in the scene):
     ```bash
     git show 7bec31a5^:工程B/Assets/_Work/工程B_Milfy.unity \
       > 工程B/Assets/_Work/_BV_parent_check.unity
     ```
     Then open `_BV_parent_check.unity` in Unity (note: when Unity opens another scene it asks whether to save the current scene — **cancel / don't save**),
     and run the same menu. Expectation: the row whose `writer_path` contains `Socks` with `key=Ankle_L/Ankle_R` has **high `uncovered_ratio`**
     (footless stockings can't cover the ankles; boots don't count as the host).
   - If exporting only the scene isn't enough (HB references/dependencies), fall back to a **copy project**: `cp -al` the whole project to `_scratch`, then `git show` over that scene,
     and open Unity in the copy (delete the copy when done).
4. After verifying, delete `_BV_parent_check.unity` (untracked). Just compare the `uncovered_ratio` of the two batches' `states[0].writers`.
   **Offline, a full csc compile of both branches with 0 errors + pure-function self-check 20 PASS / 0 FAIL have been done; edit-mode runtime readings are pending evidence from the steps above.**
