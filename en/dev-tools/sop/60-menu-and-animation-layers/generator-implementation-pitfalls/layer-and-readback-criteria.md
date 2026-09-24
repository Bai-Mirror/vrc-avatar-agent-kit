> 🌐 English translation · [中文原文](<../../../../../开发工具/SOP/60_菜单与动画层/生成器实现坑/层与回读判据.md>)

# Generator implementation pitfalls · Layer and readback criteria

> ← [Generator implementation pitfalls (index)](../generator-implementation-pitfalls.md)　Parent: [60 · Menu and animator layers](../../60-menu-and-animation-layers.md)

The problem this page solves: **after generation**, how to judge “it's actually right” — two radial steps differ, appended layer weights, empty clip + WD=ON, BoneProxy escaping the outfit root.

## After generating a radial, **you must read back and verify “any two steps have different effects”**

### Trigger
**When you've just generated a set of multi-step clips (radial / one-of-N toggle).**

### Question
**“Reduce each step's clip to `{(path, attribute, 值集合)}` and compare pairwise: are any two steps the same?
Does every object this radial is supposed to control appear in **every step**?”**

```bash
grep -E "path:|attribute:|value:" EarTail_1.anim      # what exactly does this step write
grep -rl "U_kemomimi" Assets/_Work/_60菜单/            # is this object mentioned by any menu asset
```

### What to do if you get it wrong
Add the missing curves. **Also check the object's parent chain** — if the clip writes 1 but a parent node is turned off by another layer, it still won't show.

### Why this criterion is mandatory
The most common way a multi-step toggle breaks is **one step missing curves**, so it has the same effect as another step.
This kind of breakage has **non-empty assets that save, play, and compile with zero errors**,
and **different file md5s** (different clip names), so **comparing by file hash won't find it**.

### ⚠ Don't substitute a render combination matrix for this

A render matrix only sees **effects**, and effects are the sum of multiple causes.
“The step isn't wired” and “the container is turned off by the outfit” produce **exactly the same image**; images can't distinguish the two hypotheses.

**2026-09-07 Project C proof**: the “cat ears and tail” step of the ear/tail radial was empty
(`EarTail_0`/`EarTail_1` effect sets completely identical; `U_kemomimi`/`U_tail` didn't appear once in the three steps).
70 regression ran a **30-cell combination matrix**, and 80 did another **build-time bake re-verification**;
**neither caught it**, and each produced the self-consistent but wrong root cause “attached under the outfit subtree” —
fixing according to that root cause (moving the container), the step was **still dead**.

Whereas one `grep` of the clip takes **two seconds**.

**Trade-off**: readback verification is cheap enough to do unconditionally; there's no “not worth it” case.
The render matrix still has to run, but its job is to **find what you didn't anticipate** (clipping, layer conflicts, material mix-ups),
**not** to answer “is this toggle wired up”.

⚠ “Any two steps differ” should be written as “**no two steps are identical under all external conditions**”: conditional steps (depending on other parameters) being identical may be by design; only **unconditionally** identical steps are defects.

---

## Appending animator layers: layers created by `AddLayer` have `defaultWeight = 0`

### Trigger
**When appending a layer to an existing AnimatorController** —
patch scripts, extending radial steps, adding override layers. The main generator usually gets it right; **patch scripts are the hot spot**
(they inherently go through one fewer round of checks than the main generator).

### Question
**“What is this layer's `defaultWeight`?”**

`AnimatorController.AddLayer(string)` creates it at **0**.
A layer at weight 0: **the state machine still evaluates, `VRCAvatarParameterDriver` still fires, transitions still happen;
only the curves can't write out.** The symptom is “the parameter panel looks perfectly normal, the object doesn't move” —
**exactly the same symptom** as “a later layer unconditionally writes the same property”, so it's easy to look in the wrong direction.

**MA only rescues the first layer**: `AnimatorCombiner` forces **layer 0** of each merged controller to weight 1,
and carries other layers over as-is. So the 0 on layer N(>0) in the source project is carried all the way into the build.

### What to do if you get it wrong

```csharp
var ls = ac.layers;                 // ⚠ the whole array must be written back; modifying a copy has no effect
for (int i = 0; i < ls.Length; i++) ls[i].defaultWeight = 1f;
ac.layers = ls;
foreach (var l in ac.layers)        // readback assertion
    if (l.defaultWeight != 1f && !有意为0名单.Contains(l.name))
        throw new Exception("层权重为 0：" + l.name);
```

### Trade-off: you can't blindly set everything to 1

| Case | Is weight 0 a defect |
|---|---|
| **Layer 0** of a vendor controller | No — Unity serialization convention; treated as 1 at runtime |
| Non-0 layer, and **a `VRCAnimatorLayerControl` raises it** | No — this is the normal “take over on demand” approach |
| Non-0 layer, **nobody raises it** | **Defect** |

So the criterion must first scan the whole project's `VRCAnimatorLayerControl`s and whitelist the layer names they raise,
then assert on the rest. **The costs are asymmetric**: a miss → a whole menu step is dead and only discovered on a real device;
a false positive set to 1 → that layer takes effect unconditionally and may override other layers, equally serious. **Both sides must be checked; don't rely on defaults.**

### Evidence (2026-09-08 Project C)
`CommC_StickerRadialPatch.cs:213` called `ac.AddLayer("Acc Sticker")` without setting the weight
→ the entire four-step sticker radial was dead. In the same project `SetupC_60Menu.cs:297` and
`CommC_EarTailPatch.cs:306` both explicitly wrote `= 1f`; **only the patch script missed it**.

⚠ **Knock-on effect**: the combination matrix of stage 70 and the build-time re-verification of stage 80 both ran before this patch.
**After changing animator layers, all earlier combination-traversal conclusions are void and must be rerun.**

---

## Empty clip + WD=ON: the vendor defined “default value” as **the current state of your scene**

### Trigger
**When you see a vendor toggle layer whose “on” step holds `Dummy.anim` / `Empty.anim` (0 curves) with WD=ON.**

### Question
**“What values do the properties this layer restores have in my scene right now?”**

When WD=ON meets an unwritten property, it restores **the value in the scene at the moment of build**, not the vendor's design value.
So the same parameter, in two structurally identical layers, **behaves inconsistently** because of different scene states.

### What to do if you get it wrong
Don't change the scene (fragile; any slip of the hand silently breaks it).
Write one curve explicitly in **your own layer** (merged after the vendor layer, so it wins);
other steps write nothing, and under WD=OFF the vendor layer passes through, so behavior stays correct.

### Evidence (2026-09-08 Project C)
Step 0 of the ear/tail radial had a Driver writing `Ear=0, Tail=0` (both = show); the vendor's `Ear`/`Tail` layers were structurally identical,
yet **the base avatar ears showed and the base avatar tail didn't** — because in the scene `Other_ear.activeSelf=True`,
`Other_tail.activeSelf=False`.

---

## BoneProxy moves pieces out of the outfit root — outfit switching can't turn them off

### Trigger
**Some outfit has a child object with `ModularAvatarBoneProxy` (headwear, held items, gimmick anchors).**

### Question
**“After baking, is it still a descendant of that outfit root? Can the outfit-switch clip turn it off?”**

### What to do if you get it wrong
At build time BoneProxy **moves it under the target bone** (`_Outfit/X/HeadDress` → `Armature/.../Head/HeadDress`).
The outfit-switch clip only writes the outfit root's `m_IsActive` → **the moved piece is always shown**, still worn with other outfits.

Fix: explicitly write its `m_IsActive` in **every** outfit-switch clip (writing the source path is enough; NDMF remaps it).
Writing only “this outfit = 1” isn't enough; every other outfit must write 0.

### Why it goes unnoticed for so long
**BoneProxy has no effect at edit time** — at edit time it's still under the outfit root, so manual toggling, edit-time renders,
and even combination matrix traversal (if judged by source hierarchy) **all look normal**. It's only exposed after baking.

### Criteria (without looking at images; both required)
1. In the baked avatar, for each outfit piece with BoneProxy that **has a renderer on itself or a descendant**,
   does its final parent chain still include the original outfit root;
2. In the merged controller, is there a curve controlling its (or some layer of its new parent chain's) `m_IsActive`.

**Both no = escaped, always shown.** Those without renderers (gimmick anchors, PhysBone mount points,
hair armature roots) have no visual impact if they escape and can be ignored — the criterion must filter by renderer first, otherwise you get a pile of false positives.

### Evidence (2026-09-08 Project C)
LUNALICE's headwear group (several renderers: headwear, bow, cat ears) was moved
under the head bone. When switching to WinterCozyKnit, the black lace headband and pearl pendant stayed on the head,
poking through the beret. **The cross-review model independently pointed this out without knowing the design intent**
(“did not unload/hide the black lace cat-ear headband and pearl pendant specific to outfit 01”).

⚠ After the fix, only **re-baking + re-rendering** counts as verification — and the render script must pose states with **real animation data**.
Manually `SetActive`-ing the outfit root is exactly what can't reproduce this defect (because the defect is precisely “turning off the root doesn't turn it off”).

---

## Two collection and value pitfalls hit on 2026-09-18 (Project A)

### Vendor ON clips also turn on “alternate pieces”
- **Trigger**: when collecting objects into a toggle group by the paths in vendor ON/OFF clips.
- **Question**: “For every path in the clip, is its default `m_IsActive` in the vendor prefab 1?” Pieces off by default are alternates (e.g. `outer_breast_big_open`, which the manual requires choosing one of two).
- **Trade-off**: alternates don't go into the group (`VENDOR_ALT` exclusion table); keep them off per the prefab default; build a separate switch if they're needed. Collecting them activates two nearly coincident meshes at once (measured 70% of vertices within ≤0.5 mm).

### Radial step values must use exact i/n
- **Trigger**: setting values on a Motion Time radial during review or readback.
- **Question**: “Is this value ≥ the step's start i/n?” `0.2857 < 2/7` falls into the previous step (constant tangents).
- **Trade-off**: review uses the step midpoint `(i+0.5)/n`; documentation step tables write fractions, not four-decimal numbers.
- **Boundary = keyframe time ÷ the clip's `m_StopTime`** (2026-09-19 acceptance BD): Project A's `Dial_发型.anim` has `m_StopTime=1.0166667` (not 1); parameter 0.3333 maps to clip time 0.339, past the keyframe at 1/3 → it lands on the GoldenHour step, not step 0; the real boundary is about 0.3279. Don't compute i/n in your head; first read the clip's `m_StopTime` and keyframe times.
- **Last step and 1.0 (`B-补-16` scope, 2026-09-19)**: with clip `m_LoopTime: 1`, parameter 1.0 wraps to step 0 — in Project E a vendor Motion Time animation had its last key at 1.0, so the last step can never be selected (fix: make a copy with equal divisions and looping off; see Project E work log 09-19). Review and the dependency compiler always: step i uses `(i+0.5)/n`, last step interval written `[lo, 1]` (non-looping) or `[lo, 1)` (looping); **never use 1.0 as a step value**. For a newly taken-over vendor Motion Time radial, check `m_LoopTime` first.
