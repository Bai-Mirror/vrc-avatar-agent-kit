> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/问题定位/素材与材质排查/厂商变体不一定两两不同.md)

# A vendor's N variants are **not necessarily pairwise distinct**

> A subpage split out of [`asset-and-material-checks.md`](../asset-and-material-checks.md). It takes over the main page's former section 9; the empty material slots in "Supplement" remain on the main page.

### Trigger

**When you see a row of same-named, different-colored materials in one vendor directory** (`glass_water/Blue/purple/pink/green/white`)
and are about to map them one-to-one onto the N tiers of a menu.

### Question

**"Between these N copies, exactly which field differs pairwise?"**

Don't assume "different file names ⇒ different effects", and don't assume "the difference is in `_Color`".

### If the answer is wrong

Run a **full property-difference table**: iterate over every shader property and print only
those whose values "across the six copies have `Distinct().Count() > 1`". That table is the entire content of the "color".

### Evidence (2026-09-08, Project C · Aquaglass six-color glass)

- `_Color`: **`water` and `Blue` are exactly the same** (both `#241F82`), **`purple` and `white` are exactly the same** (both pure black)
  — the six colors have only **3** distinct values on `_Color`
- What really distinguishes `water`/`Blue` is the **normal ripple texture**, and what distinguishes `purple`/`white` is the **matcap texture**

**This directly determines how the menu is built**: if implemented as "animation writes `_Color`", **two pairs** of the six tiers are dead tiers
(switching to them changes nothing); only "swap the whole material" carries the texture differences along too.

### Criterion

After generating the tiers, do a **pairwise distinguishability** check: reduce each tier's effect to a set and compare pairwise,
or render each tier and compute MD5. **Any two tiers identical = there is a dead tier.**
See [60 · After generating a wheel, you must read back and verify "any two tiers have different effects"](../../60-menu-and-animation-layers/generator-implementation-pitfalls.md).
