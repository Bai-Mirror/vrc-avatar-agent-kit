> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/40_贴图配色/素体贴图与改色手法/lilToon叠色层.md)

# lilToon color overlay layers: vendors often leave idle masks behind, enabling local recoloring without touching a single pixel

> A subpage split out of [`base-texture-and-recolor-techniques.md`](../base-texture-and-recolor-techniques.md). It takes over the lilToon color overlay layer section of “Base texture and recolor techniques”; the division of labor with “prefer offline compositing” remains on the main page.

### lilToon color overlay layers: vendors often leave idle masks behind, enabling local recoloring without touching a single pixel

`_UseMain2ndTex` / `_UseMain3rdTex` are **masked color overlay layers**. Many vendors have already painted the masks and put them in a mask directory inside the pack
(commonly an eye mask covering only the eyeball circles, an eyebrow mask with a single stroke, and a hair-mesh mask;
measure the coverage before use to confirm it covers only the target part). Enable one layer and you can tint only the eyeballs:

```
_UseMain2ndTex       = 1
_Main2ndTex          = the mask itself       ← alpha determines the affected area
_Main2ndBlendMask    = the same one
_Color2nd            = target color (alpha = strength)
_Main2ndTexBlendMode = see below
```

Division of labor with “prefer offline compositing” above: **vendor mask exists, only changing color** → overlay layer (zero pixel changes, reversible, a new tier just by changing `_Color2nd`);
**replacing the whole image, or no mask** → offline compositing.

- **⚠ Mask names lie**: the `Eyebrow` mask does not include the eyelashes (its coverage is only enough for one eyebrow). Don't assume the extent from the name; **measure the alpha coverage first** and compare it with the UV island area of the target part
- **⚠ No mask ≠ you can only do pixel surgery on a flattened texture** — first look for the layered source file (“When there's a PSD/CLIP source file” below). I once edited eyelashes on a flattened PNG on that basis and the user rejected it on the spot

**Blend mode enum Normal(0) · Add(1) · Screen(2) · Mul(3)**, source: `sBlendModes` at `lilLanguageManager.cs:145`;
the vendor's own face material uses **3** in this slot. The plan said “乗算” (multiply), and guessing by semantic order filled in `0` = Normal = **straight replacement**:
the whole eye got flat-painted into a single color disc, and the iris layering and pupil patterns were all lost. **Look enum values up in the source code; don't guess by order.**

**乗算 (multiply) can never brighten.** When “the color is a bit dark”, pushing `_Color2nd` toward white is wrong: multiply can only darken, and pushing toward white only makes the darkening approach 0;
**it can never go above the base**. Measured four tiers `#FFB0C8`→`#FFE8F0`: **V stays constant at 0.62, only S drops from 0.42 to 0.23** —
that's desaturation; the naked eye can't tell “lighter” from “grayer”, but an HSV measurement gives it away immediately.

| Want | Knob | Cost |
|---|---|---|
| Actually brighten | Switch to **Screen(2)**: α0.25 / 0.45 → V 0.76 / 0.82 | Washes the iris out, S drops to 0.20, pupil-to-iris contrast gets smeared flat |
| Darken less, keep structure | **乗算 (multiply) + lower α** (best most of the time) | Can't brighten, only darkens less |
| Push toward white | — | **Fake move**: V doesn't change, only saturation is lost |

Before adjusting lightness, state clearly whether you are moving **V or S**; report all three HSV components in the numbers, don't just paste a hex.

Masks you derive yourself must have sRGB turned off (`importer.sRGBTexture = false`), otherwise channel values get twisted through gamma.
