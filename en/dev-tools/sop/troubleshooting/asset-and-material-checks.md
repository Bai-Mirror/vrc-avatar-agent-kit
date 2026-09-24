> 🌐 English translation · [中文原文](../../../../开发工具/SOP/问题定位/素材与材质排查.md)

# Troubleshooting · Assets and materials

> The common feature of this category: **no error, no crash, the effect is just quietly wrong**, discovered only at client acceptance.
> So you must scan proactively; you can't wait for an error.

## 1. The vendor package was only partially imported

### Symptoms and instances

| Instance | Manifestation | Root cause |
|---|---|---|
| A hair package's gradient material | The hair color the client named always rendered with default settings | It's a Material Variant; **the parent material was never shipped with the package** (the package author's packaging mistake). With the parent missing, only a few override properties were serialized; the rest of the lilToon settings **all fell back to the shader's factory defaults**. A property-by-property comparison (e.g. `_ShadowColor`) shows the shader default rather than the base avatar's tuned value |
| Eye package Berrixy | Textures changed but no emission/reflection/masks | The texture folder was dragged into Assets by hand, but the key material files (`.mat`) were still sitting in **an unextracted 26 MB `.unitypackage`** |
| Hairstyle package with only 2 files | Hairstyle has no materials | Materials were in the accompanying `Materials_*.zip`, which wasn't imported |

### Four checks

1. **Any unextracted packages** — open every remaining `.zip`/`.unitypackage` in the asset directory
2. **Any missed common/material packages** — file names containing `material`/`shader`/`common`/`core`/`dlc`
3. **Material line-count checkup** — a complete lilToon material is **700+ lines**; one with only a few dozen lines is most likely a variant with a missing parent
4. **Broken GUID scan** — set difference between the project-wide GUID index and all `guid:` references in `.mat`/`.prefab`/`.unity`

### Screening out false positives

- Most broken GUIDs land in lilToon **optional slots** (`_OutlineTex` `_BumpMap` `_ReflectionColorTex`
  `_EmissionBlendMask` `_GlitterColorTex`); **when the corresponding `_UseXxx` toggle is off they are inert, not defects**
- `0000000000000000f000000000000000` is a **Unity built-in resource**, not missing

### Fix

Break the variant chain in place + `Material.CopyPropertiesFromMaterial` to take the complete settings from the base avatar's material of the same kind +
re-apply the few overrides the package author actually meant.
**Never change the GUID** — renderers reference by GUID.

### Look at the instruction images in the package

Authors often state in `導入.jpg` / `README` which material goes into which slot.
> Measured: "put the avatar's own texture as the main texture and the eye color on the second layer" was learned from an instruction image — at first it was installed the other way round and the eyebrows vanished entirely.

## 2. Folder `.meta` GUIDs got regenerated

→ [Build aborted ④](build-aborted.md)

**Permanent fix**: always unpack assets via `.unitypackage`; don't drag folders.
`通用工具/unpack_unitypackage.py` preserves the original GUIDs.

## 3. Two typical causes of white models

1. The material is URP/Lit but `_BaseMap` is empty and `_BaseColor` is the default 0.8 light gray
2. The FBX has `materialImportMode: 0` (don't import materials) and no remapping, falling back to Unity's default material
   — **the slot name shows as `Lit`, which is a great criterion**

Neither has anything to do with build/compression; **both are visible in the editor**.

## 4. To find materials, don't guess from YAML; write a probe

> Measured three wrong calls in a row: misjudged as over-compressed textures → misjudged as another similarly named material (actually the same name with a prefix)
> → misjudged as the outline layer (the main body was another renderer).

**The probe script should report**: each Renderer's actual `sharedMaterials`, shader name,
whether each texture slot is empty, `mesh.colors.Length`. One run pins it down.

**Prefabs often have multiple Renderers** (main body + outline/glow layers); replacing by matching material name easily hits a decoration layer —
**confirm by renderer name or by printing each one**.

## 5. Shared material slots

One material slot is often shared by multiple meshes (measured: one slot shared by five meshes — shirt/shorts/socks/vest/boots).
**Swapping a shared material directly changes unrelated parts.** Override textures can only be assigned to a specific mesh's material slot.

## 6. Batch material edits must be idempotent

Scripts with relative operations like "blend 50% toward the target color" drift a second time when rerun.
- Use a **state file** to record processed items; **don't stuff marker comments into `.mat`** (the Unity serializer will rewrite them)
- First `dry-run` to produce a change table, apply after confirming, **and run only once**

---

## 7. Configuring your own transparent material: **`mat.shader = x` does not reset render state**

### Trigger

**When you want to "make one just like the vendor's"** — copy the base avatar material, switch to a transparent shader, attach a mask.
Typical scenario: the vendor only shipped a sample material for another base avatar, and you must configure the one for this order's base avatar yourself.

### Question

**"Besides the shader asset, how many other things didn't switch along with it?"**

`material.shader = lts_trans` **only swaps the shader reference**. At least four categories stay where they were:

| What stays | Consequence |
|---|---|
| `_SrcBlend` / `_DstBlend` / `_BlendOp` | `_DstBlend = 0 (Zero)` → the blend formula degenerates into pure overwrite, **renders solid** |
| `_ZWrite` / `_ZTest` / `renderQueue` | The transparent part writes depth → blocks parts behind it |
| **shader keywords** (`m_ShaderKeywords`) | 9 leftover keywords carried over from Standard; lilToon doesn't recognize them but doesn't clear them either |
| **Mode enums** like `_TransparentMode` | I guessed `2` from semantics; the vendor's was actually `0` |

### If the answer is wrong

**Don't guess item by item; diff against a reference known to work.** The copy the vendor shipped for another base avatar is the control group:
compare "mine" vs. "the vendor's" property by property, **looking only at render-state properties** (the four categories above),
skipping color / textures / masks, which are supposed to differ anyway.

```csharp
// Compare render state only, not the full table — the full table gets drowned by textures that "are supposed to differ"
string[] RenderState = { "_TransparentMode","_ZWrite","_ZTest","_Cull",
    "_SrcBlend","_DstBlend","_BlendOp","_SrcBlendAlpha","_DstBlendAlpha",
    "_AlphaToMask","_Cutoff","_AlphaMaskMode","_AlphaMaskScale","_AlphaMaskValue" };
// Then separately compare renderQueue and m_ShaderKeywords (not in the ShaderUtil property table)
```

**The safest approach**: don't "copy the base avatar material and change the shader"; instead
**copy the vendor's reference material, then swap the color/texture slots to this order's base avatar's** — the render state is right by construction.

### Criterion

Render an image with **a solid-color background** (this order used a green `RGB(0.20,0.45,0.30)` background).
It only counts as transparent if the background color is visible behind the transparent part; **"the color got lighter" doesn't count** — an opaque light color looks the same as semi-transparent.

### Evidence (2026-09-08, Project C · Aquaglass)

My two `Shinano_body_ClearLeg_{half,full}.mat` rendered as **solid skin color**.
My `_DstBlend` was `0`, the vendor's `10 (OneMinusSrcAlpha)`; I guessed `_TransparentMode` `2`, the vendor's `0`;
plus 9 dead keywords inherited from Standard. All three were things that "didn't switch when the shader switched".

---

## 8. Comparing materials across projects: **an unresolvable reference ≠ empty**

### Trigger

**Diffing a material that "references assets not in this project"** —
a vendor's sample material for another base avatar, a material moved over from an old project, a half-extracted package.

### Question

**"Does this `null` mean 'the field is empty', or 'the guid can't be resolved'?"**

`AssetDatabase.LoadAssetAtPath<T>(path)` and `material.GetTexture(p)` return `null` just the same
**when the reference exists but the target asset isn't in this project**.
The two cases look identical in probe output, while the conclusions are opposite.

### If the answer is wrong

The probe should either read **the `.mat` YAML guid** (`m_Texture: {fileID: 2800000, guid: xxx, type: 3}` —
only an all-zero guid is truly empty), or **report the two cases as two different results**:

```
_MainTex  = <空>                      ← m_Texture.guid all zeros
_MainTex  = <解析不到 guid a1b2…>      ← has a guid, not found in this project
```

### Criterion

After writing the probe, run it once on **a material known to be in this project** and once on **one known not to be**:
the former should never show "unresolvable", the latter must. For the same family of rules, see
[Observation criteria · The check script itself has a bug](observation-criteria.md).

### Evidence (2026-09-08, Project C)

I diffed the vendor's sample material for another base avatar property by property; the probe reported
"`_MainTex = null`, 44 properties all look like `glass_*`", and I concluded from this that "it's essentially a glass material".
**Completely wrong.** The Wendy base avatar wasn't installed in this project, so **none** of those texture references resolved;
the guids were written plainly in the `.mat` YAML.

**Asymmetric cost**: this mistake made the probe output **look very informative** (44 hits!),
which leads people to conclusions more easily than "nothing found". **A missing value silently replaced by a legal one is the most expensive kind of probe bug.**

---

> → [A vendor's N variants are not necessarily pairwise distinct](asset-and-material-checks/vendor-variants-not-necessarily-distinct.md) — six-color glass has only 3 distinct values on `_Color`, two pairs are dead tiers; the difference may be in the normal/matcap textures; the criterion is "pairwise distinguishable".

> → [Black spots at clothing folds: first suspect the outline shell bleeding through](asset-and-material-checks/outline-black-spot-bleed.md) — black spot persists when rendering only this item, at a fold where two fabric layers sit close: temporarily set outline width to 0 as a control; if it's the outline, copy the material and adjust `_OutlineZBias` (Project B tier 7, 0.005).

---

## Supplement

- **A screen full of magenta = there's a `null` in `Renderer.sharedMaterials`**, not a shader error.
- An empty slot **has no material, so no shader can be read from it**; lists built by shader/material **can't list it**; you must count slots separately: `r.sharedMaterials.Count(m => m == null)`.
- One cause: restore logic written as `if (mats[i] == null) continue;` means **slots that already became null can never be repaired**.
- Fix: `开发工具/通用工具/FixNullMaterials.cs`, menu items `Fix - 查空材质槽` (find empty material slots) / `Fix - 修空材质槽（从预制体源头取回）` (repair empty material slots, restoring from the prefab source).
