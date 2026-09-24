> 🌐 English translation · [中文原文](../../../../开发工具/SOP/50_服装发型装配/兼容性判定.md)

# 50 · Compatibility assessment (compare bones, not file names)

> A subpage split out of [`50-outfit-and-hair-assembly.md`](../50-outfit-and-hair-assembly.md) (2026-09-20, D-28). The two original sections are unchanged, line for line.

## ⚠ Judging compatibility: **an `avatar/<素体名>/` folder in the pack ≠ support for this base avatar**

### Trigger
**When, in a generic outfit pack that “supports N avatars”, you find a folder that seems to be named after this order's base avatar.**

### Ask
**“Comparing with the base avatar's real bone names, are all 19 humanoid core items present?”**

### What if you get it wrong
Any core bone missing → **incompatible, don't force it**.
First check per “look on this machine first for missing items” whether the library has a real variant; if not, **record it in the “not used” column of the asset application table with the reason**.
The cheapest way to check for “a real variant” is to open the pack and list `pathname` to see prefab names ([10 · Open the pack and check compatibility](../10-order-intake.md)); no need to import first.

### Evidence (2026-09-07 Project C)
A generic outfit pack did contain a folder named after this order's base avatar (shinano), but on comparison **the humanoid core was missing the head, lower leg and foot bone classes**,
with the same result for every variant in the pack. The verdict: **a different “shinano” with the same name from a different source** (a base avatar from another shared project),
not the one bought for this order. None of the several versions in this machine's library had a real corresponding variant either.

**Same-named base avatars from different sources are not rare on Booth** — judging compatibility by folder name installs a garment that can't be worn,
and **in the editor it looks “installed”**, only exposed once PhysBones move or the pose changes.

## Compatibility assessment: compare bones, not file names

**Don't judge outfit compatibility by “whether the file name contains this base avatar's name”.**
Many Japanese base avatars belong to **shared base avatar projects**; outfit authors publish fits by **project name**, not character name.
> Measured: none of Hollow's 26 variants was named `Kipfel`, and I concluded incompatible on that basis — in fact Kipfel is exactly a まめふれんず base avatar,
> and `Hollow_Mamefriends` fits perfectly. 43+ outfits across three packs were nearly excluded for nothing.

**The correct criterion** (offline, a few minutes): compare the **set of bone names in the FBX**.
- In FBX binaries each object name is immediately followed by two control bytes (NUL + SOH) and then `Model`; use a regex on that to pull out object names
  (in Python build it with `chr(0)+chr(1)`; don't write a literal escape — a shell heredoc eats one layer of backslashes)
- Criterion: **zero missing humanoid core bones** (Hips/Spine/Chest/Neck/Head/Shoulder/UpperArm/LowerArm/Hand/UpperLeg/LowerLeg)
- Extra bones in the outfit (with a pack prefix or `.001`~`.00N` chains) are its own physics bones; MA Merge Armature brings them along; they don't count as missing
- **Naming quirks are the strongest fingerprint** — some base avatar projects' bone names carry fixed spelling variants (e.g. a few finger bones missing a letter, with only one in the group spelled correctly),
  and such inconsistent mistakes are identical letter for letter across all parties' FBX in the same project; if the same mistake appears in both bone name sets, they can basically be judged to share a source

## ⚠ “All bone slots under the base avatar skeleton after merging” ≠ a good fit (09-22 Project A)

**Trigger**: after processing a clone with NDMF/MA, when judging whether it fits by “are all bones used by the outfit's skinning inside the base avatar's `Armature` subtree, unmerged bones 0”.
**Ask**: **Were the outfit's humanoid core bones (upper arm/forearm/hand/thigh/lower leg/foot) snapped by name onto the base avatar's bones, or only re-parented under the base avatar's bones while keeping the original base avatar's pose?**
The latter still reads “all bone slots inside the base avatar subtree”, but the sleeves hang in the air at the original base avatar's arm angle.
**Evidence**: two outfits transplanted across base avatars (one scaled from another base avatar's mesh, one another base avatar's version) passed all readings, while agy confirmed from renders that the left sleeve was tilted up floating and the arm sleeves floated above the upper arms.
**Method**: change the criterion to two that must both pass — ① list each humanoid core bone as “snapped to which base avatar bone / not snapped”; unsnapped core bones must be 0; ② send three-view renders to agy to look for floating.
Count “same-named bones present or not” against the base avatar's bone name set **before merging**; the merged set already contains the outfit bones re-parented into it, which is self-referential.

## ⚠ The reference key of a vendor `BlendshapeSync` doesn't exist on this base avatar version ⇒ sync silently idles (09-22 Velour × Kaguya v1.06)

**Trigger**: after installing an outfit, the outfit's bust/waist blend shapes stay at the vendor default (commonly 100) and don't match the body, with the garment floating off or clipping.
**Ask**: **Can the `Blendshape` (reference key) of every binding of `ModularAvatarBlendshapeSync` be found on the reference mesh?** (list `refMeshHasKey` per binding)
**Evidence**: the bust reference keys referenced by several parts of an outfit existed on the current version of that base avatar's body mesh only as a similar key with a suffix (the original name doesn't exist); MA doesn't report an error, the outfit stays at 100, and the nipple covers' median was about 30 mm off the body.
**Method**: on the **instance**, repoint the reference key to the corresponding key on the base avatar (closest name, same body part), without changing the vendor prefab; **don't just hand-set the outfit key to 0** — then the outfit stops following as soon as the body's bust shape changes. After the change, do a reverse check (push the body key to 100; the outfit should follow to 100).
