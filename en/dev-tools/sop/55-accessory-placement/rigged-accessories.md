> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/55_配饰装位/带骨架配饰.md>)

# Rigged accessories

> ← [55 · Accessory placement](../55-accessory-placement.md)

The problem this page solves: accessory packages like ears and tails that **ship their own armature (often with PhysBones) and are not rings around a limb** —
how to attach them under humanoid bones without wiping the coordinates the author set up, how to make it idempotent,
and the bone-segment length check that is mandatory after attaching — PhysBones aren't simulated at edit time, so this check is the only thing that catches them flying off in Play ahead of time.

## Non-ring accessories (ears/tails with their own armature): three hard lessons

### ① Moving a child out of a **prefab instance**: Unity refuses without an error

`SetParent` silently fails and the script log still prints “attached”. Measured: the entire ear/tail set stayed where it was
(world y=−0.082, by the feet), nothing appeared in the render, and the report looked perfectly normal.

**Method**: before changing structure, first
`PrefabUtility.UnpackPrefabInstance(GetOutermostPrefabInstanceRoot(go), OutermostRoot, AutomatedAction)`,
**and immediately assert `c.parent == mount` after attaching**. This kind of “API silently has no effect” can only be caught by readback criteria.

### ② Base-avatar-specific accessory packages use **absolute coordinates in the avatar root space**; don't zero them

Pirouette's ear/tail package has no MA components at all; it's simply laid out for Kaguya's proportions:
placed under the avatar root with an identity transform, `ear_root`'s world position is (0, 1.130, −0.012) — exactly on top of the head.

So attaching under a bone is **only so it follows the head/hips**; the position is already right:
use `SetParent(mount, worldPositionStays: true)` and **do not** zero localPosition/Rotation.
Zeroing inherits the bone's orientation (the Head bone measured roughly 105° around X): the ears flip onto the chest and the tail sticks out sideways from the shoulder.

To tell which kind a package is: check whether it has MA components and whether its bone names match humanoid bones.
If neither, and the bones' world positions land on the right body part as soon as it's placed — it's this kind.

### ③ If repeated trial and error has dirtied the object, delete it and re-instantiate the prefab

I revised the ear/tail piece three times in a row (zeroed → kept world transform → zeroed again), and in between there was also
“the idempotent step moved the children under `_Acc`”; in the end the object had a leftover 0.5 scale and wrong parenting,
and **any adjustment on top of that was wrong**. Delete, re-instantiate from the prefab, run placement again — right the first time.

### ④ Idempotent = “same result no matter how many times you run it”, not “right on one run”

The placement script must tear down the previous mount at the start and redo it. When tearing down and moving children back into the container,
**you must `SetParent(container, worldPositionStays: true)`**.

Using `false` resets localPosition to (0,0,0) — equivalent to wiping the absolute coordinates the author tuned.
The symptom is highly misleading: **the first run is right, the second run is misplaced**. And in a normal workflow
“tweak a parameter and run again” is routine, so this bug is guaranteed to strike after you think you're done.

Self-check: run placement twice in a row and compare both reports and world positions; only exact equality counts as idempotent.

---

## Mandatory after attaching: bone-segment length

After attaching an accessory armature under base avatar bones, **measure each bone's distance to its parent bone**. Any segment over 30cm on a humanoid accessory is suspect.

Measured on Project A: the vendor's animal ears' `armature.ear` carried a prefab-space offset
(local Y +3.219), `ear_root` carried a Blender Z-up leftover (1.131 ended up on Z),
and the child bones `ear_L/ear_R` had locals that cancelled it back out — **the net effect was completely correct**:

| Check | Result |
|---|---|
| Render | Correct |
| Bone world positions | Correct |
| Per-vertex scan (after BakeMesh, all vertices <20cm from the head) | Correct |
| Measured after baking with the full NDMF pipeline | Correct |
| **Bone-segment length** | `ear_root → ear_L` = **4.07 meters** |

`ear_root` has a PhysBone; a 4-meter arm × 36.6° angle limit ≈ 2.4 meters of swing,
so in Play the ears fly two meters away. **PhysBones aren't simulated at edit time, so only this check catches it ahead of time.**

### Fix and acceptance

1. Zero the transforms of intermediate adapter nodes (**criterion: not present in any `SkinnedMeshRenderer.bones[]`**).
   Don't use “only-child chain” as the criterion — bone chains are naturally strings of only children, and real bones would be zeroed too.
2. Move the anchor bone to the centroid of its children's world positions.
3. **Write back every descendant's world TRS unchanged** (parents before children).
4. If rootBone was touched, **`localBounds` must be recomputed**, otherwise the whole thing gets frustum-culled.
5. Acceptance criterion: **per-vertex world position deviation after baking**. Skinning only sees bone world transforms;
   per-vertex identical ⇔ render identical. Should measure <0.001mm. If it fails, roll back on the spot.

**⚠ Fixing overly long segments**: move the PhysBone off the absurd adapter bone onto **each child bone** (one copy each), and **`rootTransform` must be cleared**; **don't shorten segments by moving bones** — unchanged skinning ≠ unchanged physics; the rest orientation is taken from the parent→child vector, so it will turn in Play.

## Supplement

- MA BoneProxy's `target` is a **non-serialized property**; the serialized fields are `boneReference` + `subPath`, `SerializedObject.FindProperty("target")` returns null, and nothing happens in the script.
- MA ShapeChanger's serialized field is **`m_shapes`, not `Shapes`**; reading the wrong one makes the audit script report “0 shrink keys” for every outfit.
- Accessories shipping their own Animator are split by curve content: **constant keyframes → delete the component**; **keyframes that change → disable it or copy the clip**, don't modify vendor assets in place; nested Animators in the avatar tree are a performance item in themselves.
- Troubleshooting order: local value difference between Play and edit time → look up the PhysBone subtree by **Transform reference** → components on the bone chain → **Animators on the parent chain**.
