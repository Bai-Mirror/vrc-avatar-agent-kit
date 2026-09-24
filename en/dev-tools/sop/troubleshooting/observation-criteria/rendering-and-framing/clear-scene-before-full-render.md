> 🌐 English translation · [中文原文](../../../../../../开发工具/SOP/问题定位/观测口径/渲染与取景/整机出图前先清场.md)

> ← [Rendering and framing](../rendering-and-framing.md) · [00 · Master table](../../../00-overview.md)

# Clear the scene before a full-avatar render (showcase shot): three kinds of things that shouldn't be in frame

> Trigger moment: before using `Camera.Render()` to render **the whole avatar** (showcase shots, hairstyle/outfit comparison images, delivery images).
> Pitfalls for part close-ups (eyes, accessories) are in [Taking photos of a part in the Editor](photographing-parts-in-editor.md), which covers stale skinning and isolation; this page covers "things that are already extra in the scene".

## 1 · A scene often has more than one avatar root, and they are **at exactly the same position**

### Trigger
The project has both the source avatar and a face-tracking version / backup root / Quest version, and `Camera.Render()` captures both bodies at once.

### What the symptom looks like
**It doesn't look like "two people"; it looks like clipping.** Measured in Project B on 2026-09-21: large amounts of cream-colored hair showed through under the pink hairstyle;
the third-party reviewer (agy) identified it as "the base model's hairstyle wasn't hidden when the pink hair was enabled; two hairstyles overlapping and clipping; blocker; reshoot" —
**right location, completely wrong cause**. That cream hair belonged to the face-tracking root; on the source avatar `Hair_Front/Head/Side/Twintails` were all off.

### Criterion (no human viewing needed)
Before rendering, count how many **roots with renderers** are in `scene.GetRootGameObjects()`. If >1, they must be blocked.
Write the name of each blocked root in the log, so the image can say clearly whom it shows.

### How to do it
Use `Renderer.forceRenderingOff = true`: it's a runtime flag, **not serialized, doesn't dirty the scene**,
safer than `SetActive(false)` (which goes into scene changes and, once saved, really modifies the project). Set each back to false in `finally`.
> Don't "turn off someone else's renderer.enabled" — that's a serialized field. The `cullingMask` isolation recommended for part close-ups
> doesn't work well here: the two roots are usually on the same layer.

## 2 · A plugin's "placement preview pieces" are real renderers, deleted only at build time

Measured 2026-09-21: PCS (Penetration Contact System) has real `MeshRenderer`s under `Target Objects/Placement Icons (Auto Remove)/…`
(a red-circle target with `GUI/Text Shader` + the word "Insert" + arrow + small sphere),
covering the whole chest in the showcase shot. PCS deletes them itself at build time, so **the final product is fine; only editor renders capture them**.

- **Don't blame gizmos first**: VRCFury's SPS socket icons go through `Handles` (`[DrawGizmo]`) and are only drawn in the Scene view;
  `Camera.Render()` to a RenderTexture can't capture them. First render one with `cam.cullingMask = 0`:
  non-background pixels = 0 means everything in the frame is **a real renderer**, not a gizmo — stop investigating in the gizmo direction.
- **How to find them**: back-project the suspicious location to world coordinates and list renderers whose bounds center is nearby and whose extents are small.
  Grepping by name (socket/orifice/sps/marker/gizmo) comes up **completely empty** on PCS — its keywords are `Placement Icons` and `Auto Remove`.
- **Keep matching narrow**: only accept strings the author explicitly marked as "will be auto-deleted" (`Placement Icons (Auto Remove)` / `will be auto removed`);
  don't fuzzy-match words like preview/icon, or you'll hit accessories the client actually wants.

## 3 · Don't `SetActive` tiers by hand; evaluate the controller from parameters

### Trigger
When rendering comparison images "one per hairstyle / one per outfit", taking the shortcut of writing `_Hair.GetChild(i).SetActive(true)`.

### Why it's wrong
A tier's clip **both turns things on and turns things off**. In Project B's Hair layer on 2026-09-21, each purchased-hairstyle tier, besides turning on `_Hair/x`,
also turned off the base avatar's own `Hair_Front / Hair_Head / Hair_Side / Hair_Twintails / Ribbon_Hair / Hairpin / BandAid_Hair`,
and a separate `Sup_HairEar` layer turned off `Kumachan_Ear` (only for two of the tiers). Turning on without turning off = shooting two sets of hair stacked.

### How to do it
Read the parameter asset's `defaultValue` → override the one parameter being swept → evaluate and apply with `State70.Evaluate/Apply` (with snapshot restore).
Derive tier values **from the conditions on that layer's AnyState** (`Greater lo` / `Less hi`, take the interval midpoint); don't hand-write `i/(N-1)`:
MA/VRCFury tiers use a `1/N` bandwidth, and a slightly off hand calculation lands in the adjacent tier.

### Side note
Write one line per tier in the log listing "which head parts are on in this tier"; next time an error like double hairstyles can be spotted without looking at the image.

## 4 · The "outfit hit" assertion compares `activeSelf`, not `activeInHierarchy`

SOP [70 regression](../../../70-regression-testing.md) requires showcase shots to name the delivered outfit and assert "named N items, N items on".
Implementations easily end up using `activeInHierarchy` — **which fails falsely**: when the parent `_Outfit/some set` is off,
its children's `activeSelf` is still 1 (animations write `activeSelf`), but `activeInHierarchy` is 0.
Measured 2026-09-21 comparing this way: "172 should be on, 25 actually on, 147 missing" — all false.

- **Criterion**: compare `activeSelf == evaluated result` item by item; it counts as a hit only if 0 mismatch; dangling bindings (object not found in the scene) are counted separately and excluded from the denominator.
- **Also log one line for humans**: the list of top-level parts actually rendering in frame (iterate `GetComponentsInChildren<Renderer>(false)` and walk up to the top-level parent). This line is "what's worn in the image".
- **Conversely**: when the question is "is it visible in game" (e.g., after switching to a full set, does an original part leak through), the criterion is `activeInHierarchy && Renderer.enabled && material non-null`; comparing only `activeSelf` gives false reports — on 09-23, Project A A-21 read `activeSelf` and reported 18 cases of "original parts in non-base tiers written back to 1 by part toggles"; in fact the full-set clip turned off the parent object `kaguya_cloth`, and only A-21b, additionally reading `activeInHierarchy` + byte-identical renders, overturned it. **Checkable question**: am I answering "whom the menu selected" (`activeSelf`) or "whether it's on screen" (`activeInHierarchy` + renderer)? Read both before reporting a defect.

## 5 · Record face sculpting values again **after applying**

After the controller's default state is applied to the scene, its blendShape curves may overwrite the face sculpting already baked on the SMR.
The log should record the non-zero blend shapes "at the moment the shot was actually taken", not those at function entry.
Measured 2026-09-21: 3 entries at function entry, 4 after applying — the extra `extra_shy_1=100` was blush from `RJ_EyeBlush` defaulting to 1,
meaning **the client version has blush on by default**; this is only visible by reading again after applying.
