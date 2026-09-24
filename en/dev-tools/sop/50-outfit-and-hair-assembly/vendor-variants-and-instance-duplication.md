> 🌐 English translation · [中文原文](../../../../开发工具/SOP/50_服装发型装配/厂商变体与实例复制.md)

# 50 · Vendor variants: when you can only install a second instance

> ← [50 · Outfit and hair assembly](../50-outfit-and-hair-assembly.md)

What this page solves: the vendor provides **two variant prefabs** of the same outfit (hood up/down, with/without cap, long/short sleeves…),
and the client wants “some slots use A, some slots use B” — how to implement it and what it costs.

---

## 1 · First measure where they differ, then decide how to do it

### Trigger
**You find same-named variants like `Hood_Off/` `NoCap/` in the vendor directory, and the requirement is to switch at runtime.**

### Ask
**“Do the two actually differ in mesh, material, active state, or skeleton pose?”**

Four possibilities, from lowest to highest cost:

| Differ in | Criterion | Implementation |
|---|---|---|
| Only **active state** | Compare `activeSelf` path by path | One Toggle is enough, no second copy |
| **Material** | Compare `sharedMaterials` | Animate a material array swap |
| **Mesh** (each has its own pieces) | Compare the path sets | Two groups, each with its own switch |
| **Skeleton pose** | Compare local transforms bone by bone | **Must have a second instance**, see below |

### Criterion (script, not images)
Dump `(mesh name, vertex count, activeSelf, component list, local transform)` for both prefabs path by path,
and print only the rows **that differ**. ⚠ Compare by **full path**, not by name —
in outfits `Jacket` / `Tops` are often both a mesh name and a PhysBone node name.

### Evidence (2026-09-08 Project B_Milfy · LopEarMine)
441 objects compared path by path: the mesh sets are identical; **the only difference is the skeleton** —
**5 of the 23 bones** in `Hood_Root` and its children have different local transforms
(hood root rot 0.13° → 286.07°, i.e. tilted back 74°; both ears and the ribbon root were re-posed),
and the parent bone also changed from `Head` to a new bone `Hood1` under `Chest`.

---

## 2 · When they differ in skeleton pose: constraints can't reproduce it

### Ask
**“Is the difference only the parent bone, or do the child bones' local poses differ too?”**

- **Only the parent bone differs** → you can add just a constraint with a switchable parent; no need to duplicate
- **Child bones' local poses also differ** → **the author posed it**; constraints can't reproduce that, only a second instance can

### What if you get it wrong
Forcing it with constraints looks right in a static standing pose but **goes wrong as soon as it moves** (especially when following head rotation).
Don't cut corners here — the cost of duplicating an instance is actually small, see the next section.

---

## 3 · But **no need to duplicate the whole set**: only duplicate the meshes actually skinned to those bones

### Criterion (per-vertex bone weights)
1. Take the bone chain where the variant differs (e.g. `Hood_Root` and all its children);
2. For each `SkinnedMeshRenderer`, find the indices in `bones[]` that fall on that bone chain;
3. Count **the vertices with weight > 0 on those indices**. Only those with >0 need duplicating.

⚠ Don't just check whether it's in `bones[]` — ones in the bone array with all-zero weights don't count.

### Evidence (same as above)
Of 23 meshes only 3 need duplicating:

| Mesh | Vertices | Vertices skinned to hood bones | Share |
|---|---:|---:|---:|
| `Jacket` | 14165 | 796 | 5.6% |
| `Jacket_Ear` | 6862 | 6862 | 100% |
| `Jacket_Ear_Pin` | 3056 | 3056 | 100% |

The other 20 (skirt, top, socks, shoes, backpack…) are unaffected and share the existing copy.
The cost drops from “whole set ×2” to **+3 skinned meshes, about 24k vertices + 24 bones**.

---

## 4 · How to install the second instance

### Structure: container gating
```
_Outfit/<容器>                    ← the full-set radial controls this level
  ├ <原件>                        ← all meshes + all MA components
  └ <变体>                        ← only the affected meshes + skeleton
```
When the container is off, the child objects' state doesn't matter — this lets part layers / accessory radials write child objects freely
without releasing this outfit under other full-set slots. Details in
[60 · Property ownership and writing](../60-menu-and-animation-layers/property-ownership-and-authoring.md).

### What to delete and keep in the variant copy

| Component | Handling | Why |
|---|---|---|
| `MA MergeArmature` | **Keep** | The new bone chain relies on it to merge into the avatar skeleton |
| `MA MergeAnimator` | Delete | Otherwise the vendor's layers get merged twice |
| `MA Parameters` | Delete | Otherwise the vendor parameters get declared twice |
| `MA MenuInstaller` / `MenuItem` | Delete | Otherwise the vendor menu gets installed twice |
| Unaffected meshes | Delete | They waste performance budget |

⚠ To delete child objects of a prefab instance you **must `UnpackPrefabInstance` first** — deleting directly gives
“Cannot delete GameObject that is part of a Prefab instance”.

### Wiring: the vendor's layers can't reach the second copy

Vendor parameters (e.g. `LEM/Jacket`) only write the **original's** paths. So:

- **Part switches** must write the variant copy's visibility themselves (using full paths — the two copies under the container have same-named meshes, and resolving by leaf name is ambiguous)
- **The accessory radial** is only responsible for **suppressing one copy** between the two:
  its own slot doesn't write the original (leaving it to the vendor and part switches), other slots write false; the variant copy the other way round.
  Both are released by part switches and suppressed by the radial; **no layer force-ons anything** —
  so “top turned off but hood still hanging” can't happen.

### Read-back criteria (always check after installing)

| Criterion | Expected |
|---|---|
| Number of child objects under the container | == 2 |
| Meshes in the variant copy | == the ones computed in section 3 above |
| `MergeArmature` in the variant copy | == 1 |
| `MergeAnimator` / `Parameters` / `MenuInstaller` in the variant copy | == 0 |
| Local transforms compared with the original **by full path** | Differ only on the variant bone chain, 0 differences elsewhere |
| Number of paths only in the variant | == number of roots of the added bone chain (here 24 = `Hood1` + 23 bones) |
| Ownership audit | The variant copy's meshes “have a layer that writes 1” |

⚠ Don't check the skeleton with absolute thresholds like “longest bone segment < 500 mm” —
the local coordinate of `Hips` under the skeleton root is the hip height of 760 mm, **a false alarm every time**.
The right way is to compare path by path using the original as the **control sample**. See
[The shape of a criterion](../troubleshooting/observation-criteria/shape-of-a-criterion.md).

## ⚠ When instantiating a vendor prefab, don't touch the root Transform: the vendor bakes “fit scaling” into the root (09-22 Project A)

**Trigger**: when a script instantiates a vendor outfit prefab under the avatar (setting `localPosition/Rotation/Scale` after `InstantiatePrefab`).
**Ask**: **Was the instance root's `m_LocalScale` overwritten? What's the vendor's original value?** (check `m_LocalScale` in `PrefabUtility.GetPropertyModifications`)
**Evidence**: Velour's Kaguya-version prefab uses another base avatar's (Mizuki) mesh, and the vendor baked a fit scale smaller than 1 into the root (different for each base avatar version); our instance root was overwritten to 1 ⇒ the whole garment one size larger, shifted up about 0.23 m, sleeves floating above the arms.
MA merging **preserves the mesh's world appearance** (`MeshRetargeter.cs:239-240` changes bindposes, not poses), so with the wrong root scale it is still misaligned after merging, and the main bones still “all snap”.
**Base avatars of the same family in different sizes** (IKUSIA's Mizuki / Rurune / Kaguya share one body at different sizes): when the vendor only provides a Rurune pack (PuNyaNya's variant labeled “Rurune/Kaguya” only includes the Rurune version),
putting it on Kaguya as-is shifts it up 13–18 cm; take the ratio of the root scales the same-family vendor baked for each base avatar version (target base avatar version ÷ the version included in the pack) and scale the root to align — this is not a made-up number; write the source of the ratio in the work log, and ask the user first.
