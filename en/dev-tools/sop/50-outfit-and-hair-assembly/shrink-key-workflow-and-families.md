> 🌐 English translation · [中文原文](../../../../开发工具/SOP/50_服装发型装配/收缩键流程与两族.md)

# 50 · Shrink keys: execution workflow and the trade-off between the two families

> A subpage split out of [`50-outfit-and-hair-assembly.md`](../50-outfit-and-hair-assembly.md) (2026-09-20, D-28, parent page at 15,915 B over the limit). The three original sections are unchanged, line for line.
> For ownership rules see [Foot-shape and shrink key ownership](foot-and-shrink-key-ownership.md); for the definitions of the two key types and criterion bias see [Two key types and writers](foot-and-shrink-key-ownership/two-key-types-and-writers.md).

## Body shrink keys to prevent clipping

> ⚠ 2026-09-18: fitting body blend shapes to outfits hasn't been done well in any existing project; the workflow in this section is **not fully tested** and serves only as samples that include both good and bad examples, pending a rewrite under the new regression procedure (see the header of [70](../70-regression-testing.md)).


**Attach MA Shape Changer to the garment part, don't leave it in the vendor's outfit-switch animation.**
Shape Changer is a ReactiveComponent: when the garment object is inactive it doesn't take effect, so it **naturally follows the garment**;
whereas shrink keys written in animations follow “the parameter is true” — leading to “clearly wearing a different outfit, yet the shoulders are shrunk by the shirt's shrink key”.

> Measured: one vendor's top toggle animation sets the body mesh's shoulder shrink key to full to shrink the shoulders,
> and as long as the parameter is 1 this animation keeps playing.

## Clipping and shrink keys: an executable check workflow

> ⚠ 2026-09-18: fitting body blend shapes to outfits hasn't been done well in any existing project; the workflow in this section is **not fully tested** and serves only as samples that include both good and bad examples, pending a rewrite under the new regression procedure (see the header of [70](../70-regression-testing.md)).


**Whether the vendor provides shrink keys is not guaranteed; check set by set.**
> Measured in the Kaguya order: MMN's three sets and ANEMONE's two sets **come with** `ModularAvatarShapeChanger`;
> while Kitty Crop Shirt and Re-Poppin' Cat **have only MergeArmature, not a single shrink key** — these two sets need manual attachment.

| # | Action | Criterion / output |
|---|---|---|
| 1 | List the base avatar mesh's **shrink key candidates** | Iterate the SkinnedMeshes directly under the avatar root, filter blend shape names containing `OFF` / `hide` / `shrink` / `消` / `非表示` |
| 2 | List the **existing** ShapeChangers of each outfit | `GetComponentsInChildren<ModularAvatarShapeChanger>`, dump `ShapeName / Value / referencePath` |
| 3 | Difference set = **candidate list to attach** | Where an outfit covers that body part but has no corresponding shrink key, that's a suspect |
| 4 | Judge set by set with screenshots **which are really needed** | See “Don't assume” below |
| 5 | Attach `ModularAvatarShapeChanger` **on the garment part itself** | It's a ReactiveComponent; when its object is inactive it doesn't take effect, naturally following the garment |
| 6 | Zero **all** `blendShape.*` curves in vendor animations that target the base avatar mesh | Change values, don't delete curves (safer, reversible) |

```csharp
var sc = Undo.AddComponent<ModularAvatarShapeChanger>(part.gameObject);
sc.Shapes = shapes.Select(s => new ChangedShape {
    Object = new AvatarObjectReference { referencePath = "Body" },
    ShapeName = s, ChangeType = ShapeChangeType.Set, Value = 100f }).ToList();
PrefabUtility.RecordPrefabInstancePropertyModifications(sc);
```

**Don't assume; test set by set.**
> Project G's four outfits **needed no foot shrink keys at all** — base avatar boots fully enclose the foot / open-toe slides (toes should be exposed anyway; adding them would be wrong) /
> the other two sets barefoot. `Body_Base` had complete `Foot_OFF` / `Toe_OFF` ready, and not one was used.

**Static renders can only check T-pose.** Places like cuffs, hems and armpits only show up when you **run through motions** in Gesture Manager.

**Know the cost**: after moving shrink keys from animations to ShapeChanger, **granularity gets coarser** —
the vendor could originally set `Upper_arm_OFF` back to 0 on its own in “short sleeve” mode; after binding as a whole, the upper arm is still shrunk with short sleeves.
To keep the fine granularity, add another layer of reactive conditions.

## Shrink keys come in two families: **pose-type** can be used freely, **deletion-type** requires measuring the shoe's coverage first

### Trigger

**When choosing foot-shape keys for a set of shoes**, especially when names like `Shrink_*` / `*_OFF` / `hide` appear among the candidates.

### Ask

**“Which parts of the foot does this shoe **enclose**? For the exposed parts, will this key of mine delete them?”**

The base avatar's foot keys are actually two families, with completely different costs:

| Family | Typical key names | What it does | Consequence of misuse |
|---|---|---|---|
| **Pose-type** | `Toe_heels` `Toe_highheels` `Foot_heel_OFF` | Changes the foot's **angle**, geometry conserved | Pose doesn't fit; visible but not fatal |
| **Deletion/shrink-type** | `Shrink_Foot` `Shrink_Ankle` `Foot_OFF` `Toe_OFF` | **Deletes vertices / shrinks volume to 0** | As soon as the shoe isn't fully enclosing, **the exposed area is empty** |

The precondition for deletion-type is that **the shoe fully encloses that part**. True for boots and high-tops;
**not true for pumps / loafers / open-toe sandals / any style that exposes the instep**.

### What if you get it wrong

Replace deletion-type with pose-type. **Pose-type keys can be stacked** (this order finally used `Toe_heels=100` + `Toe_highheels=100`),
adjusting the angles of the sole and toes, with not a single bit of geometry lost; the exposed parts render normally.

If it still clips, go in the direction of “make the **shoe** bigger / add a lining”; don't go back to deleting the foot.

### Criterion (⚠ don't use “looks clean”)

**Don't use overall statistics like pixel variance / edge count / “picture tidiness”** —
**deleting the foot makes all of these metrics better**, and the criterion will reliably recommend the worst option.
(Learned the hard way, see [Self-check question for variable criteria](../troubleshooting/observation-criteria.md):
“If I **delete** the object under test, would this metric get better?” Yes → the criterion is broken.)

What to measure is **the geometry itself**, using `BakeMesh` to get the actual mesh:

| Measure | Expected |
|---|---|
| Foot vertex bounding box **length** | Changes < 5% before and after applying the key (pose-type changes angle, shouldn't change length) |
| Foot **volume / vertex count** | Same as above; **losing half means it was deleted** |
| Foot's lowest point vs shoe's lowest point | Foot inside the shoe (negative difference) |

### Evidence (2026-09-08 Project C · Outfit_VioletNocturne)

The author pointed out: “The shoe is a boat sock, why did you shrink the instep and toes to 0?”
Measured: `Shrink_Foot=100` made the foot **32% shorter and nearly halved its volume**,
while this shoe is an **open, instep-exposing** style — the shoe opening was simply empty.

I had chosen this key because I ran an offscreen scan of “five blend shape tiers × five outfits” using **pixel variance** as the criterion.
**The tier with the lowest variance was exactly the “delete the foot” tier** — the criterion didn't measure wrong; **its direction was backwards**.

- Bust following: the outfit carries bust keys with the same names as the body's, but no one syncs them (pokes through at max bust) → `50_服装发型装配/胸型跟随_同名键无人同步.md`
- Garment lacks a body key (nipple covers without `Breast_small`) → add a frame to a copy of the original mesh in Unity, no FBX round trip → `50_服装发型装配/给衣物补形态键.md`

## Six semantics of MA ShapeChanger (MA 1.18.1, verified against source · D-22)

| # | Semantics | Checkable question / consequence |
|---|---|---|
| C1 | `ChangeType` has only two values: **Delete=0, Set=1** | In serialized JSON it's just 0/1; don't guess from the panel text |
| C2 | **Delete deletes vertices**; it doesn't set the key to 100 | The panel has Set=60, and **the same object, same key** also has a Delete — each field is legal on its own, but the vertices Set acts on have been deleted/hidden, so it's set for nothing |
| C3 | Multiple writers go by **hierarchy pre-order** (the order of `GetComponentsInChildren`), **later registrants override** | When two garments pressing the same key are on together, the winner is decided by pre-order: first predict the winner by pre-order, then reconcile with renders |
| C4 | **Set automatically reverts when the host object is deactivated** (a ReactiveComponent property) | So “body doesn't recover after undressing” can only come from the places where **animator layers write blend shapes directly**, never from Set |
| C5 | **Persistent Delete physically removes vertices at build time** (`RemoveVertices`); Delete that changes with a switch goes through **NaNimation** (bone scale=NaN while the deletion is in effect) | Deletion regions can only be measured from the original mesh in **edit mode** — after Play/build those vertices are either gone or NaN. Checkable question: “Are the vertices I'm measuring still the same ones in Play?” |
| C6 | The deletion region is computed by the writer's own `m_threshold` (default 0.01, **mesh local units**) + primitive-level selection | Not 0.1 mm in world coordinates, and not “counts if delta>0” |

### Three hard rules

1. **The same object must not Set and Delete the same key at the same time** (C2) — report it when found; don't think “keeping both is safer”.
2. **Declare persistent ShapeChangers separately**; don't mix them in one table with switch-dependent ones: the former delete vertices at build time and **cannot be undone**.
3. **When sliders/radials fight over a key, check layer weights first**: whether the animator layer or the MA reactive layer wins is known only from the build output or runtime state;
   a layer with default weight 0 that nothing raises does nothing when toggled — first read each FX layer's `m_DefaultWeight` after baking and cross-check against all LayerControls.

### Set / Delete trade-off: first ask “can it be undone”

| | Reversible? | When to use |
|---|---|---|
| **Set** | Yes (reverts when the host object is deactivated) | **Choose it by default** |
| Switch-dependent **Delete** | Yes (NaNimation, hidden at runtime) | The vertices must truly disappear: cutouts, under see-through fabric |
| Persistent **Delete** | **No** (physically deleted at build time) | Certain this set will never need those vertices, **and confirmed with the user** |

### Socks Deleting foot keys: must be checked against **the shoes worn with them**

Socks deleting `Toe`/`Foot`/`Ankle` show no problem under the default enclosed shoes; switch to **open-toe / cutout** shoes and toes are missing, with holes.
Method: list all Deletes on foot keys → using the vendor showcase images, sort the shoes that can be worn with them into **open-toe / cutout / enclosed** →
render the foot once for each class (low camera + top-down). How ownership itself is decided: see [Foot-shape and shrink key ownership](foot-and-shrink-key-ownership.md).
