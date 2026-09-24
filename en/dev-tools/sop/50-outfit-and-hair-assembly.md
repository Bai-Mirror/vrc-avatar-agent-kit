> 🌐 English translation · [中文原文](<../../../开发工具/SOP/50_服装发型装配.md>)

# 50 · Outfit and hair assembly　🤖

**Purpose**: attach outfits/hair/accessories to the base avatar with aligned armatures, no clipping, and a script-traversable structure.
**Output**: scene hierarchy + `装配报告.md` (which components each piece got, skinned mesh count)

> ## ⚠ Comes after [30 face sculpting](30-face-sculpt.md); do not run in parallel (this entry is canonical)
>
> **Swapping the FBX during face sculpting invalidates part of the results of this stage and of [40 recoloring](40-texture-and-coloring.md)**: swapping the FBX resets the material arrays (`sharedMaterials`) of renderers in the scene,
> and `ArmatureLockMode.BaseToMerge` also misaligns the jacket armature (symptoms and fix below under [Misalignment is guaranteed after swapping the FBX](#换-fbx-之后必然错位)).
>
> So: **start 50 only after 30 is done**, otherwise every outfit has to be removed and reattached, and recoloring reapplied.
> Exception: face sculpting that only changes vertices and doesn't touch the armature is unaffected — but that's the minority; schedule as if it will invalidate by default.
> **Do not touch the scene while 30a is in progress** — a human may be hand-tuning; the first explanation for an unexpected scene state is “a human changed it”.
> For scheduling see [01 · Automated execution and parallelism](01-automation-and-parallelism.md).

---

## Compatibility judgment

The trigger, the questions, what to do if you get it wrong and the evidence for “the package has an `avatar/<base-name>/` folder ≠ supports this base avatar”, plus the judgment steps for **comparing bones, not file names** →
**[50 · Compatibility judgment](50-outfit-and-hair-assembly/compatibility-assessment.md)**

## Deterministic steps

### Step 1 · Probe what each prefab ships with　🤖

**Preconditions**
- [ ] Environment confirmed usable per [02 · Environment preparation and human intervention](02-environment-and-manual-intervention.md)
- [ ] 30 done (or confirmed this order doesn't swap the FBX)
- [ ] Look up `开发工具/素材包说明/*/部件图鉴.md` by Booth item number; if missing, attach, photograph and build one ([Part understanding and menu layout](50-outfit-and-hair-assembly/part-understanding-and-menu-layout.md)); the menu and shrink keys are not finalized until the part atlas is complete

**Execution**
1. For each prefab to be attached, run `GetComponentsInChildren<Component>` and print component type names

**Post-criteria**

| Expected | How to read |
|---|---|
| Every piece falls into one of four classes: “ships MergeArmature / ships BoneProxy / both / neither” | Probe report |

**STOP**
- Don't add components before probing. Adding MergeArmature to hair that ships BoneProxy measured **0 bones mapped**

---

### Step 2 · Judge compatibility (compare bones, not file names)　🤖

**Preconditions**
- [ ] Step 1 done

**Execution**
1. Scrape object names from the FBX binary and take the set of bone names
2. Compare against the base avatar's humanoid trunk

**Post-criteria**

| Expected | How to read |
|---|---|
| Missing humanoid trunk bones == 0 | Comparison report (trunk list below) |

**STOP**
- The base avatar's name not appearing in file names **does not make it incompatible** (shared-base projects publish under the project name); you must compare bones

---

### Step 3 · Attach and confirm it actually renders　🤖

**Preconditions**
- [ ] Step 2 passed

**Execution**
1. Attach according to probe results (don't blindly add MergeArmature)
2. Create the `_Outfit` / `_Hair` / `_Acc` / `_Gimmick` groups (see structural conventions below)

**Post-criteria**

| Expected | How to read |
|---|---|
| MergeArmature bones mapped > 0 | Component readout |
| Each piece is **visible** when turned on alone | Render check, not just the hierarchy |
| After a full `MeshFilter` scan, all attachments inside the armature are grouped | Query by component, check one by one |

---

### Step 4 · Handle anti-clipping shrink keys　🤖

**Preconditions**
- [ ] Step 3 passed

**Execution**
1. Follow the six steps of “Clipping and shrink keys: executable check flow” below

**Post-criteria**

| Expected | How to read |
|---|---|
| Every outfit has a **per-outfit judgment record** for shrink keys (needed/not needed, each with a reason) | Judgment table |
| `blendShape.*` curves in vendor animations targeting the base avatar mesh have been zeroed (**change the value, don't delete the curve**) | Scan clips |

**STOP**
- Whether a vendor provides shrink keys **varies**; check each outfit, never generalize one outfit's conclusion to all

---

### Step 5 · Item-by-item acceptance　🤖 →🎨

**Preconditions**
- [ ] Step 4 passed

**Execution**
1. Go through the acceptance table at the end of this page, **every item, no sampling**

**Post-criteria**

| Expected | How to read |
|---|---|
| Every row of the acceptance table has evidence (screenshot or value) | Acceptance table |
| Every piece has an **out-of-package reference** | GUID reverse lookup, hits > 0 |

**STOP**
- Static renders only check T-pose; cuffs, skirt hems and armpits only show problems in motion → leave to [70 regression test](70-regression-testing.md)

## Subpage index

| Subpage | When to open |
|---|---|
| [Vendor variants and instance duplication](50-outfit-and-hair-assembly/vendor-variants-and-instance-duplication.md) | The vendor ships two variants of the same outfit (hood up/down etc.) to be switched at runtime; judging where they differ, whether to duplicate, which meshes to duplicate |
| [Foot-shape and shrink key ownership](50-outfit-and-hair-assembly/foot-and-shrink-key-ownership.md) | Assigning foot-shape keys/shrink keys; feet still on tiptoe after removing shoes; feet poking out of socks; pixel-diff key selection picks the wrong key |
| [Shrink key flow and the two families](50-outfit-and-hair-assembly/shrink-key-workflow-and-families.md) | Where shrink keys go, the clipping check flow, pose-type vs deletion-type trade-offs |
| [Part understanding and menu layout](50-outfit-and-hair-assembly/part-understanding-and-menu-layout.md) | When attaching an outfit: what the parts are, how prominent, how they go into the menu; look up or build a part atlas |
| [Compatibility judgment](50-outfit-and-hair-assembly/compatibility-assessment.md) | How to judge “supports this base avatar”; compare bones, not file names |

## Iron rule: see what the prefab ships with before deciding whether to act

Vendor prefabs are assembled in different ways — some ship **MA MergeArmature**, some are **MA BoneProxy attached to Head**,
some have both, some have neither (attach by hand).

> **Measured lesson**: adding MergeArmature to hair that shipped BoneProxy resulted in **0 bones mapped**.

**Method**: the assembly script first probes and prints component type names with `GetComponentsInChildren<Component>`, then decides.
Reference implementation: `Probe()` in `工程A/Assets/Editor/AvatarGen/SetupA.cs`.

## Misalignment is guaranteed after swapping the FBX

`ArmatureLockMode.BaseToMerge` syncs the jacket armature to the base avatar armature →
the symptom is **the jacket GameObject exists but doesn't render at all**. Removing and reattaching once restores it; then reapply recoloring.
Unaffected when only vertices change and the armature isn't touched.

## Shrink keys: execution flow and the two-family trade-off

Attaching MA Shape Changer to the clothing part (so it follows the clothing) rather than leaving it in the vendor outfit-switch animation, the executable “clipping and shrink keys” check flow, and the trade-off **pose-type keys are free to use / deletion-type keys require measuring the shoe's coverage first** with its criteria and evidence →
**[50 · Shrink key flow and the two families](50-outfit-and-hair-assembly/shrink-key-workflow-and-families.md)**

## Attachments inside the armature are easy to miss

Collect static meshes via `MeshFilter` (clothing is SkinnedMesh, attachments are static meshes) → canonical version in the last row of [03 · Assembly method table](03-assembly-and-conflict-rules.md).

## The vendor's own grouping is the authoritative answer

Scan all `m_IsActive` curves in vendor animations to determine grouping → canonical version in [03 · Two reminders before starting](03-assembly-and-conflict-rules.md).

## Structural conventions (AI maintainability first)

Create empty objects per **group** as attachment points; names within a group are `<group>_<label>`:

```
Kaguya-工程A/
├─ _Outfit/   Outfit_MMN_黑  Outfit_MMN_黑粉撞色  Outfit_ANEMONE_黑  …
├─ _Hair/     Hair_GoldenHour  Hair_SweetyHair
├─ _Acc/      Acc_光环_金  Acc_头饰_金  Acc_耳尾1  …
└─ _Gimmick/  Gimmick_SPS
```

This lets [60 menu](60-menu-and-animation-layers.md) generate directly by traversing groups, without maintaining a second list.
Mutual exclusion within a group (one outfit at a time) is guaranteed by the menu layer; the accessory group can stack.

## Acceptance (item by item, no sampling)

| Item | Criterion |
|---|---|
| Armature | Zero missing humanoid trunk bones; MergeArmature bones mapped > 0 |
| Rendering | Each piece visible when turned on alone (not “object exists but doesn't render”) |
| Shrink keys | The 6 steps above completed, and **every outfit has screenshot evidence** |
| Accessory placement | **Screenshot each accessory individually to confirm placement and size**; attaching in the right place in the hierarchy is not enough |
| Combinations | **Screenshot every outfit × every accessory × every toggle combination**; passes only with no clipping and no misplacement |
| Omissions | Full `MeshFilter` scan confirming all attachments inside the armature are grouped |
| Actually used | Every piece has an **out-of-package reference** (GUID reverse lookup); anything without one isn't wired up |

---

## Foot-shape and shrink keys: belong to “the piece that actually wraps that body part”

Shoes just go over the socks, and shoes and socks are usually **two independent part toggles** —
put the foot-shape key on the shoe, and when the user turns off the shoe the foot shape returns to neutral while the sock is a rigid mesh that can't follow → **the foot pokes out of the sock**.
The same applies with a hand-written animator layer: **never write it in the whole-outfit switch layer** (symptom: feet still on tiptoe after removing shoes).

The criterion (per piece, compute the fraction of vertices covering those bones; ⚠ compare by bone name, not by Transform object: MergeArmature is build-time, so comparing by object at edit time matches nothing),
“the sock slot's default value is not ‘none’”, the measurement method for three scenarios and false negatives →
**[50 · Foot-shape and shrink key ownership](50-outfit-and-hair-assembly/foot-and-shrink-key-ownership.md)**
