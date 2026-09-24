> 🌐 English translation · [中文原文](../../../开发工具/SOP/03_装配与冲突通则.md)

# 03 · Assembly and conflict rules　🤖

> A cross-stage **decision table**, not an operations manual. It answers two questions:
> **① Which method should the thing in hand be installed with?　② When two things fight, which side gets suppressed?**
> The concrete procedures are in [50 Assembly](50-outfit-and-hair-assembly.md) / [55 Accessory placement](55-accessory-placement.md) /
> [60 Menus and animator layers](60-menu-and-animation-layers.md); this page only does triage.

---

## 1. Assembly method: classify first, then decide

**Classification is based on "what it carries itself", not on what it's called.**
Before doing anything, always run a component probe first (list all component type names on the prefab),
and match it against the table below. **Skipping the probe and adding components directly is the most expensive mistake at this stage.**

| Category | How to recognize | How to install | Most common mistake |
|---|---|---|---|
| **Full outfit / hairstyle** (humanoid-isomorphic) | Has an `Armature`, and bone names match the base avatar's humanoid trunk | MA **MergeArmature** | Judging compatibility by filename → compare bones instead |
| **Pieces that ship with BoneProxy** | The prefab already has a `BoneProxy` | **Use as is**; don't add MergeArmature on top; when adding your own, don't use BoneProxy, see [55 Iron rule 3](55-accessory-placement.md) | Adding MergeArmature was measured to **map 0 bones**; and BoneProxy **doesn't take effect at edit time**, so it looking unmoved is normal |
| **Ring-shaped pieces** (rings / wrist accessories / head rings / neck rings) | Has a hole and must fit over a limb | Compute the hole axis and hole center → **parent directly to the bone** | Filling in the pose by hand → it should be **fully computed** |
| **Accessories with their own armature** (ears/tails etc., non-humanoid) | Has its own `Armature`, but bone names don't match the humanoid | Attach to the vendor's adapter node | Not **checking bone segment lengths** after attaching → statically perfect, flies off as soon as PhysBones run |
| **Floating / surface-hugging pieces** (hair accessories, panels, halos) | No bones or a single bone, placed against a surface | Place relative to a reference surface | Wrong reference surface: **it's the rendered surface**, not the bone position |
| **Held items** (things hugged in the arms) | Needs a matching arm pose | Object attached to the chest + arm pose **goes through the Additive layer** | Putting the arms in Gesture → the arms get locked when it's turned off (see [Humanoid arms and fingers](60-menu-and-animation-layers/humanoid-arms-and-fingers.md)) |
| **Static attachments inside the armature** | `MeshFilter` + `MeshRenderer`, tucked under `Armature/…` | Follows the group it belongs to | **The easiest to miss entirely** — clothes are SkinnedMesh, these are static meshes, and you only find them by searching by renderer type: `find_gameobjects(by_component: MeshFilter)` pulls out all static meshes at once (measured: a fish toy tucked under `armature/…/Bag/ContentsPosition/` stayed floating in place after the bag was turned off) (canonical entry) |

### Three cross-category rules

**① Poses are computed, not filled in.**
Anything that can be written as a closed-form criterion (whether it fits over, off-center, angle, bone segment length) **should not be fed as images at all**; assert it directly in a script.
Images are only for checking detail textures and clipping.

**② The reference surface is the rendered surface, not the bones or the bounding box.**
"How deep it's embedded" must be measured against the rendered surface in place; don't use the skull center or bounding-box boundary as the baseline.
And most are **top-aligned**, not center-aligned.

**③ When moving a generic pack to a different base avatar, judge size first, then position.**
For generic accessory packs made for another base avatar, when installing on a new base avatar **first scale proportionally by base avatar size**.
Adjusting position first gives "right position but absurd size", and you redo it twice.
Measure the ratio from the vendor's renders.

---

## 2. Conflict handling: first identify which kind it is

**The three kinds of conflict have completely different semantics, and using the wrong method has completely different consequences.**
There is only one classification question: **"Can the user still turn B back on afterwards?"**

| Kind | Semantics | Method | Consequence of getting it wrong |
|---|---|---|---|
| **A · Turn off in passing when switching** | Turned off once; the user **can turn it back on** afterwards | `VRCAvatarParameterDriver` **changes B's parameter** | Written as a property → B **can never be turned on** |
| **B · Suppress while on** | While A is on, B stays suppressed; when A turns off, B comes back automatically | Write B's property in **a separate layer** | Using a Driver → when the user manually turns it back on, it clips again |
| **C · Same-position mutual exclusion** | Two things at the same position can't appear at the same time | Define a **priority chain** and suppress only the lower-priority side | Suppressing in both directions → **both sides disappear together** |

> **One-line mnemonic: change the parameter = turn off once; write the property = hold it down continuously.**

### How to write kind B (the key: "the off state must write nothing")

```
Layer: <accessory>_Suppress   ordered after the part toggle layers and the full-outfit layer
  ├─ Empty     default state, clip has no curves   ← under WD=OFF, unwritten properties pass through from earlier layers unchanged
  └─ Suppress  condition <accessory parameter> == true, clip writes <suppressed object>.m_IsActive = 0
```

**Criterion**: after turning the accessory off, the clothing sub-content **comes back on its own** = correct; if it doesn't come back = you've locked it in another layer.

### Kind C: a conflicting pair may only be suppressed in one direction

When two suppression rules in opposite directions hold simultaneously, they **suppress each other out**;
what the user sees is "nothing at this position", not "one of them isn't showing" —
because no single rule is wrong, **checking rules one by one won't find it**.

**Rules**:
- First define a **global priority chain** (e.g. headwear > small outfit head pieces > ears), and resolve all conflicts by the chain
- If the conflict table contains both "A suppresses B" and "B suppresses A", it's wrong, whether or not they were added in the same batch
- Every entry in the table must be able to state **its position on the priority chain**; any entry that can't is redundant

**Acceptance must iterate over "combinations", not "individual items"**: run all combinations of `preset × conflict toggle`,
and for each cell assert "at least one piece is on at this body position"; it only passes when deadlocked cells == 0.
The assertions must be driven by **real animation data**; toggling objects manually proves nothing about what the animator layers will write.

### Mutual exclusion wiring: three layers of responsibility, don't pile it all into one layer

"A and B are mutually exclusive" isn't one action; it's three things assigned to three places:

| Where it's written | What's written | Why |
|---|---|---|
| **The controlled layer itself** | B's layer On writes `A=false`, Off writes `A=true` | The other half of the mutual exclusion is B's own responsibility |
| **Later layers** | Write **only when forcing is needed**; in other presets **touch neither property** | Under WD=OFF, untouched properties pass through unchanged from the previous layer |
| **Switching action** | Use a Driver to change the parameter | "Turn off in passing" is a one-time action, not continuous suppression |

**Counterexample**: unconditionally writing `A=false` into every clip of a later layer →
equivalent to **permanently suppressing** A; it can never be turned on from the menu again.

---

## 3. Symptom → where to look

| Symptom | Prime suspect | Where to look |
|---|---|---|
| A toggle **doesn't respond no matter how you click it** | A layer ordered after it **unconditionally writes the same property** (under WD=OFF the later write overrides earlier ones; the menu parameter does change, the parameter panel looks fine, only the object doesn't move) | Scan all layers for clips that write a property of the same name unconditionally |
| **Nothing at all shows** at some position | Two suppression rules in opposite directions suppress each other | Kind C in section 2 of this page |
| The mesh **is there**, but the shape / position is wrong | The vendor parameter layer is still posing bones by the old value — only mesh visibility was written | [60 main page](60-menu-and-animation-layers.md) one-line iron rule |
| After turning something off, **something stays floating in place** | A static attachment inside the armature was missed | Last row of section 1 of this page |
| The jacket GameObject **exists but doesn't render at all** | The FBX was swapped, and the armature lock broke the jacket armature sync | Uninstall and reinstall once to recover; see [50 · Misalignment is guaranteed after swapping FBX](50-outfit-and-hair-assembly.md) |
| Accessory is statically perfect, **flies off as soon as it moves** | Abnormal bone segment lengths at the adapter node | [Accessories with their own armature](55-accessory-placement/rigged-accessories.md) |
| Looks uninstalled at edit time | BoneProxy **doesn't take effect at edit time by design** | Not a defect; don't "fix" it |
| **Wrong root selected for upload**, or root counts in reports contradict each other | Multiple roots in the scene; "how many" has four conventions (scene roots / scene-wide descriptors / **active root** / including backup prefabs) | [Avatar root conventions](03-assembly-and-conflict-rules/avatar-root-conventions.md); [10](10-order-intake.md) step 6, [90](90-delivery-packaging.md) |
| With the accessory on, only the **bare main body** shows and the decoration is gone | A "decoration" was treated as a "variant" and wired as mutually exclusive | Section 5 of this page |
| Two very similar-looking things **clip through each other** | A "color variant" was treated as a "decoration" and wired to toggle on together | Section 5 of this page |
| After changing material, it **renders solid / opaque** | The shader was changed but the render state wasn't changed with it | [Asset and material troubleshooting · 7](troubleshooting/asset-and-material-checks.md) |

---

## 4. Two reminders before starting

**The vendor's own grouping is the authoritative answer.**
Scan the paths of all `m_IsActive` curves in the vendor's animations and you'll know which items form a group —
far more reliable than guessing by name (measured: that "bag" was actually three pieces — bag body + name tag + the fish toy inside the bag) (canonical entry). Names often deceive: the same name may be both a parameter and a GameObject,
and they **don't control the same thing at all**.

**If you can drive it directly with the vendor's parameter, don't build your own layer.**
Attach the menu control directly to the vendor parameter: it takes no new bits, and you get the vendor's linkages (mutual exclusion, bone poses, swing motions) for free.
If the default value isn't right, change **both** the vendor's parameter asset and the controller.

---

## 5. **Decoration** or **variant**: the wiring is opposite, and the criterion can't be the bounding box

### Trigger

**A vendor accessory directory contains several similar-looking pieces at nearly the same position**
(`Ears` / `Rose_Ears`, `Tail` / `Roses_Tail`), and you need to decide how to wire the menu.

### Question

**"Are these two 'two looks of the same thing', or 'one thing + a decoration attached to it'?"**

The wiring for the two is **completely opposite**; choosing wrong is guaranteed to go wrong:

| | Variant (A or B) | Decoration (A with B) |
|---|---|---|
| Wiring | **Mutually exclusive**: turning one on must turn the other off | **Toggle together**: B's toggle follows A |
| Symptom of choosing wrong | The two clip through each other (pink ears poking through white ears) | Only the bare main body shows; the decoration is gone |

> → [Criteria for decoration vs. variant](03-assembly-and-conflict-rules/decoration-and-variant-criteria.md) — why bounding boxes can't answer it, the per-vertex nearest-distance median criterion (<2mm variant / >5mm decoration), one positive and one negative sample.
