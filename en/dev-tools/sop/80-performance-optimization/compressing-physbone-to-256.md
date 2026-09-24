> 🌐 English translation · [中文原文](../../../../开发工具/SOP/80_性能优化/PhysBone压到256.md)

> ← [80 · Performance optimization](../80-performance-optimization.md) · [00 · Master table](../00-overview.md)

# Squeezing PhysBones under VRChat's hard cap of 256 (Project B in practice, 2026-09-21)

> Trigger: the SDK panel reports `Phys Bone Components: N - Avatar exceeds the maximum limit (256)`.
> This is **not a bad rating**; it is `AvatarValidation.cs:127 MAX_AVD_PHYSBONES_PER_AVATAR = 256`,
> and at build time the **processed** avatar is validated again and `throw ValidationException` is raised, so the upload gets no bundle.
> In the same place: colliders 256 (`:128`), Contacts 256 (`:131`), Constraints 2000 (`:132`), Raycasts 80 (`:126`).

## 1 · An empty AAO MergePhysBone is not “harmless extra”, it is “attach it and the build fails”

In `MergePhysBoneProcessor.cs:52-53`, an empty `componentsSet` just `return`s, but **AAO's Validation phase reports
`MergePhysBone:error:noSources` for it**, NDMF preprocessing returns false, and the whole chain breaks.

Measured: a tool batch-attached 10 MergePhysBones without filling `componentsSet`; the symptom was
`VRCBuildPipelineCallbacks.OnPreprocessAvatar` returning false with **no exception text in the log at all**, which took a long time to track down.

- **Queryable question**: when preprocessing inexplicably returns false, first count the MergePhysBones with `componentsSet.mainSet.arraySize == 0`.
- **Trade-off**: either fill in the source list or delete it. Don't leave it empty.

## 2 · AAO MergePhysBone cannot reduce the number on the **panel**

Panel statistics run on the **pre-build** scene objects (measured: panel shows 520, post-build is 497). AAO merges at build time,
so the panel number does not change. To make that panel Error disappear, you can only truly delete/merge **in the scene**.

## 3 · The correct way to merge in the scene (copy AAO's semantics, but don't touch the hierarchy)

Merge semantics (`MergePhysBoneProcessor.cs:143-176`): the remaining component is attached to the **parent object**,
`rootTransform = parent`, `multiChildType = Ignore`, and `ignoreTransforms` and `colliders` take the union.

### ⚠ The step most easily missed — miss it and the avatar is ruined

`rootTransform=parent + multiChildType=Ignore` turns **all** child chains under the parent into physics chains, **including those that originally had no PhysBone**.
Measured consequence of missing this step on 2026-09-21: the component on `Armature/Hips` covered `Spine` and `Upper_leg.L/R`,
the one on `Head` covered `LeftEye`, the one on `Chest` covered `Neck`/`Shoulder` —— the whole armature went soft.

AAO's approach is to **reparent the source chains under a newly created empty object** to isolate them (`:56-100`; it reuses the parent directly only when “the parent's children are exactly all source chains”
and the parent is not written by animation).

**An equivalent approach that is simpler and safer**: add every child of the parent that **does not belong to this group's source chains** to `ignoreTransforms`.
Same effect, and it **doesn't touch the hierarchy or break animations that reference bones by path**.

### Hard self-check (no human eyes needed)

Right after merging, compute: the number of first-level child chains this component actually covers (the parent's childCount minus those in `ignoreTransforms`),
**must equal the number of source chains**. If it doesn't match, throw an exception and abort; don't continue.

Add one whole-avatar criterion: iterate over all PhysBones and check whether the bones
`Spine / Neck / Shoulder.L,R / Upper_leg.L,R / Hips / Chest / Head / LeftEye / RightEye / Hand.L,R`
appear in any component's “covered child chains”; **it must be 0**.

## 4 · Which groups cannot be merged

| Situation | Why |
|---|---|
| Any member of the group is written by animation (curves of type `m_Enabled` / `VRCPhysBone`) | After merging, that curve points to nothing |
| The group has ≥2 different non-empty `parameter`s | A merge can keep only one; the other's grab/stretch parameters stop working |
| `allowGrabbing` / `allowPosing` are inconsistent | Merging makes something that couldn't be grabbed grabbable (or vice versa). If you merge, explicitly align to the group's majority and write it into the record |

## 5 · Free wins: PhysBones that simulate nothing

Components whose “`rootTransform` (the component itself when empty) has no child transforms, and whose `endpointPosition` is 0”
**simulate nothing**; deleting them costs nothing. Each of Project B's two roots had 5 (`TwistCancel/*Sode_*`, `DrawersFrillRoot1` in vendor items).
> Distinguish carefully: ones with no child bones under the root but with `endpointPosition` **set** have a virtual endpoint; **don't delete them as idle** (Project B had 15 on each).

## 6 · Real numbers (Project B, both roots identical)

| Step | Component count |
|---|---:|
| Start | 520 |
| Delete 5 idle ones | 515 |
| Round 1: same-parent merge of 69 groups (settings aligned to majority) | 257 |
| Round 2: touch only `_Hair`, merging each hairstyle's parts into one (4 groups) | **236** |

**“Same-parent merge” alone cannot reach 256**: the pure mathematical limit is 259 (merge all same-parent, force settings aligned), still 3 over.
You must stack “delete idle ones” or “merge one level up”. When estimating, compute these three tiers first before discussing a plan:
① same parent + identical settings only (zero feel change) ② merge whenever same parent, force settings aligned ③ merge one more level up.

## 7 · Side effect: cyclic dependency Warning

After merging, this may newly appear:
`This avatar contains VRCPhysBone or VRCPhysBoneCollider components which have cyclic dependencies`.
The SDK text says the consequence is “some collider runs one frame late” and “it can be ignored if intentional”; **it is a Warning, not an Error, and doesn't block upload**.
First remove self-loops by “the collider grows on its own chain”; if they can't be removed, it's a loop formed by two components referencing each other; record it as a known item.

## 8 · How to know how many Errors remain without a human reading the panel

Use reflection to get the open `VRCSdkControlPanel` instance → `ResetIssues()` → call `VRCSdkControlPanelAvatarBuilder.OnGUIAvatarCheck(descriptor)`
→ read the two fields `GUIErrors` / `GUIWarnings` (`Issue.issueText`).
Run per root; far more reliable than having the user scroll and screenshot, and you can re-verify immediately after changes.
