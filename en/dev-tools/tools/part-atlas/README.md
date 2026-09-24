> 🌐 English translation · [中文原文](../../../../开发工具/通用工具/部件图鉴/README.md)

# Part Atlas · Per-Part Photo Tool (PartAtlasCapture)

**Purpose**: for **every Renderer** of an outfit, produce images showing “what it looks like / where it sits / how prominent it is within the whole set”, and write a
`部件清单.json`. The tool **only produces images and numbers; it does not judge “what part this is”**; for a new order, only change the project's `_交付/部件图鉴_配置.json`.

## Files
- Common source `PartAtlasCapture.cs` + overlay `part_atlas_overlay.py` (PIL stamps product name/path/view/tris/mats in the top-left corner);
  the project copy lives in `Assets/Editor/PartAtlas/`, and **the two copies must be byte-for-byte identical**.
- Per project: `_交付/部件图鉴_配置.json` (input) and `_交付/部件图鉴_拍摄报告.md` (readings; last line `DONE`/`FAIL`).
- Output: `开发工具/素材包说明/<商品名>/部件图/` + `部件清单.json`.

## How to run
1. Unity menu `Tools/PartAtlas/Capture` (**invoke only once per session**).
2. All heavy work is hung on `EditorApplication.delayCall`; the menu returns immediately and doesn't block MCP.
3. Single-flight lock `_dsh_tmp_mergeqa/lock`: refuse if it already exists; must be deleted after the run (including on exceptions).
4. Zero scene changes: shoot on a clone, destroy it afterwards, don't save; the report records “hierarchy md5 identical / isDirty / scene md5 unchanged”.

## Config fields
| Field | Meaning |
|---|---|
| `avatarRoot` | Name of the avatar root GameObject in the scene (used when an outfit doesn't specify `avatarRoot`) |
| `outputRoot` | Output root directory (absolute path) |
| `commonClipDirs` | Additional asset directories to scan for animation clips |
| `bodyRoots` | Node names where the base avatar's body meshes live, default `["Body","Body_b"]`; **must be specified when changing base avatar** (Milfy is `["Body","Body_base"]`: `Body` = face/head mesh, `Body_base` = torso and limbs) |
| `outfits[]` | Per set: `root` the outfit root name in the clone (**if it contains `/`, it's resolved as a path relative to the avatar root**, for colliding names like `_Outfit/1`), `avatarRoot` (optional, the avatar root this set belongs to; defaults to the top-level `avatarRoot`), `product` product name (= output directory name), `vendorImageDir`, `vendorPrefab` (vendor prefab asset path; if empty, looked up backwards from the scene) |
| `maxRenderersPerOutfit` | Debug sample: >0 shoots only the first N pieces per set; 0 for production |
| `onlyParts` | Only shoot Renderers whose `gameObject.name` matches these names (empty = shoot all); **numbering still follows the full list**, so the `NN_` in file names/manifest doesn't change. Used for partial reshoots after upstream fixes (H-03); a set with no matches is skipped entirely |
| `cloneBlendshapeSync` | When true, on the clone, drive `LocalBlendshape` per `ModularAvatarBlendshapeSync` to the reference mesh's current value (build-time semantics). In edit mode it's uncertain whether the NDMF preview has run or finished running, so the photo clone must first settle into the “after build-time sync” blend shapes; you can't trust edit-time readings of the scene instance |
| `mergeExistingManifest` | When shooting only a subset, merge the new readings of the matching entries back into the existing `部件清单.json` as a block, keeping the rest of the set's entries and set-level fields (otherwise the whole manifest would be left with only the matching few) |
| `partFrameExpand` | Expansion factor for per-part framing of the full set, default 2.5 (<=0 uses the default) |
| `partFrameMinRatio` | Minimum fraction of the frame the part's projection must occupy for per-part framing of the full set, default 0.05 |

**One config can span multiple avatar roots** (since 2026-09-22 H-05): grouped by each set's `avatarRoot`; each group is cloned once, shot, and destroyed before the next group;
`场景外泄核对` (scene leak check) / `素体顶点索引` (base avatar vertex index) are recorded per group. The clone is still moved as a whole to x=+10.

## Output image list and naming
`NN_<Renderer名>_<视图>.png` (768², 1-based numbering in outfit-root traversal order):
- **On body — front/side/back** (`在身上-正面/侧面/背面`): only that part + base avatar `Body`/`Body_b` enabled; **all other
  Renderers/ParticleSystems in the scene outside the clone are also turned off**.
- **Part only — front** (`仅部件-正面`): the body is turned off too.
- **Full set with/without — front** (`整套-有/无-正面`; an extra `-背面` back view when the part's centroid leans toward the back): the full set uses the vendor's default toggles;
  **framed by the part's bounding box** (expanded to ≥2.5× + merged with adjacent body regions); with/without share the same camera position.
- **Full set full-body with/without — front** (`整套全身-有/无-正面`; back view as above): the original full-body framing (renamed from `整套-*` since H-02b).
Each image has `商品名 / 路径末两级 / 视图 / tris= / mats=` (product name / last two path levels / view / tris= / mats=) stamped in the top-left corner.

## Data conventions (written into the manifest's `口径` field)
- **front**: read the Head bone's horizontal forward; `正视夹角=0°` (front-view angle) = face pointing straight at the camera.
- **Three-level bounding box fallback** (`包围盒世界.口径`): ① mesh readable → skinned, computed per vertex as
  `Σ w·(bone.localToWorld·bindpose)·v`; ② mesh not readable (vendor FBX has Read/Write off;
  all 9 pieces of The Velour hit this) → `renderer.bounds`; ③ `renderer.bounds` degenerates to 2×2×2 → union of bones.
- **Dominant bone**: if `boneWeights` is readable, use the real weights; if not, fall back to “bone-to-bounding-box distance”; the manifest marks the convention per entry,
  treat it as weak evidence only, and rely on the images for which body areas are covered.
- Framing **does not trust** `Renderer.bounds` (in edit time it often falsely reports 2×2×2 for inactive skinned meshes).

## Pitfalls (trigger moment + how to avoid)
### The 4 caught in H-02
1. **`Renderer.bounds` false reports**: when shooting skinned pieces and reading the bounding box/framing, you get 2×2×2. → Compute vertices yourself from bone weights;
   fall back only if not readable, and write the convention into the manifest.
2. **Vendor FBX has Read/Write off**: when you want vertices/weights, `mesh.isReadable=false` (9 Velour pieces).
   → Fall back to `renderer.bounds`/bone-distance conventions and annotate each entry; real weights require enabling Read/Write and reimporting (which changes project assets; discuss separately).
3. **Vendor prefab can't be found by reverse lookup**: `kaguya_cloth` is a hand-made node in the scene, and reverse lookup returns the whole base avatar prefab;
   reverse lookup from the clone returns null outright. → Name `vendorPrefab` in the config; reverse lookup is only a fallback and must be done from the **original scene object**.
4. **Running heavy work in the menu callback blocks MCP**: the whole shoot takes far more than 20 s. → The menu only hooks `delayCall` + single-flight lock, and deletes the lock when done.

### These 2 framing pitfalls in H-02b
5. **A white bear sneaks into “On body — side”**: when a view shoots orthographically along ±x, the original avatar (or even another avatar being edited)
   is standing right behind the clone, and the camera's `cullingMask=~0` captures them too; front/back views go along z and are offset 10 units sideways so they don't hit it, which is why only the side view
   has the problem — **turning off only the clone's accessories isn't enough**. → Before shooting, `SceneHide`: turn off all Renderers
   (including ParticleSystemRenderer) and ParticleSystems in the scene outside the clone, restore them afterwards; the report records “turned off N / restored N”.
6. **“Full set with/without” is too small**: small parts (nipple pasties/collar/bag buckle) are only a few pixels in the full-body image. → The two comparison images are now framed by the part's bounding box
   (≥2.5× + adjacent body regions; if the part's projected bounding rectangle is <5% of the frame, zoom in, but never crop the piece); the two full-body images are kept and renamed
   `整套全身-*`. Note: the nipple pasties' “with/without” looking identical is because they're fully covered by the tube top in the full set (a visibility-condition issue), not because the image is small.

### These 4 in H-05 (multiple avatar roots / changing base avatar / vendor bone names / unassigned references)
7. **Multiple avatar roots in one project**: Milfy is split into outfit roots A/B, but a config only `Instantiate`s one `avatarRoot`,
   so the second root's outfit root simply can't be found in the clone. → `PacOutfit.avatarRoot` (optional, defaults to the top level) + grouping by root:
   clone once per group, shoot, destroy, then the next group; `场景外泄核对`/`素体顶点索引` are recorded per group, and the wrap-up reports cross-group totals.
8. **Base avatar meshes aren't always called `Body`/`Body_b`**: Milfy is `Body` (face/head, with viseme blend shapes) + `Body_base` (torso and limbs).
   Hitting only one of them → the body-region index has only 5 regions (missing upper arms/hands/legs/feet), and full-set framing has no leg/foot context. → Name them in the `bodyRoots` config.
9. **Vendor-supplied armature names carry a part suffix**: the four 00capettiya sets use `Hand.L(KemoHandMB)` (Modular Avatar merges back into the base avatar by
   `骨名(部件名)` (bone name(part name))); the old table matched bone names exactly, so they all fell into “other”. → `BoneRegions.RegisterHumanoid` fills in using
   the Animator humanoid bone mapping, and `RegionOf` retries once after stripping the trailing parenthesized suffix.
10. **Unassigned serialized references**: `FieldsOf` reading `.name` on a fake-null `UnityEngine.Object` throws
    `UnassignedReferenceException` (MA `ModularAvatarMenuItem.menuSource_otherObjectChildren`),
    so the whole set throws and yields 0 images. → Use Unity's overloaded `uo == null` to null-check before reading the name (`Str()` is also wrapped in try/catch).

### These 2 in H-03 (edit-time blend shapes / copy drift)
11. **The effective value of MA `BlendshapeSync` in edit mode can't be relied on**: after the reference key is set, the NDMF editor preview may, some frames later,
    change the clothing key from the vendor prefab default to match the body's value, or it may not have run yet; the same scene
    instance reads different values at different moments. → Partial reshoots always enable `cloneBlendshapeSync`, explicitly set values on the clone per the bindings, and write
    the three readings “vendor prefab default / scene instance current / clone after sync” into the report.
12. **Project copies drift from the common source**: H-05 only synced Milfy's copy, and Project A's copy lagged by a whole section (missing
    `bodyRoots`/multiple avatar roots). → Before touching the tool, `diff -q` the common source against the target project's copy; after changing, sync both together,
    and compile only once `diff -q` reports SAME.

## How to use it in other projects
1. Copy `PartAtlasCapture.cs` into the target project's `Assets/Editor/PartAtlas/` (`part_atlas_overlay.py` stays in the common directory).
2. Write `_交付/部件图鉴_配置.json` in the target project: at least `avatarRoot`, `outputRoot`, `outfits[].root/product`.
3. Refresh and compile in Unity → menu `Tools/PartAtlas/Capture`.
4. Check that the last line of `_交付/部件图鉴_拍摄报告.md` is `DONE`, and verify the three wrap-up readings (md5 identical / isDirty=False /
   scene file md5 unchanged).

## Lookup script (check_parts_doc.py)
Before dispatch, check whether a product **has a part atlas** (for the judgment rules see section 1 of SOP 50); read-only.
```
python3 开发工具/通用工具/部件图鉴/check_parts_doc.py --item <商品号> [--avatar Kaguya]
python3 … --name "The Velour"   # directory name / prefab name / scene root name
python3 … --selftest
```
- Checks `<素材库>/*-<号>` (directory names may contain square brackets; filter the suffix with `listdir`),
  `素材包说明/*/部件图鉴.md` (grep for the number or name), and `<商品名>/部件清单.json` and `部件图/`.
- Four states: has atlas (covers / lacks this base avatar) / only manifest and images / none; with hit paths attached; `--json` for structured output.
- Exit codes 0/10/20/30 correspond to the four states (with multiple queries, the least complete state wins); 2 on its own error.
- When `dsh_task.js` matches `装配|菜单|部件图鉴|换装|服装` (fitting|menu|part atlas|outfit change|clothing), it runs this automatically, appends the result to the end of the task brief, and prints it to
  stderr (failure only warns; `--no-parts-check` turns it off, `--dry-run` only prints the assembled task brief).

## Known limitations
- When the mesh isn't readable, bounding box/dominant bone use fallback conventions; don't treat them as weight conclusions.
- The area convention mathematically can't reach 5% for extremely flat parts (e.g. the fingernails of both hands, 46:1): the tool keeps the whole piece visible, with the longest-edge convention ≥ ~22%.
- “Full set with/without” gives two identical images when the part is fully covered by an outer layer (judging visibility conditions requires combining with vendor toggles/blend shapes; see SOP).
