> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/60_菜单与动画层/结构惯例.md>)

# Structural conventions: the mechanisms are hard, the clustering is soft

> Subpage split out of [60 · Menu and animator layers](../60-menu-and-animation-layers.md). Takes over the section of the same name; step 2's “write the menu structure per structural conventions and hard constraints” now reads this page.

## Structural conventions: the mechanisms are hard, the clustering is soft

**Hard (not changeable)**
- Switching **whole outfits** and **hairstyles** always uses `RadialPuppet` (203) + a Float parameter, **not a pile of Toggles**
- **Only part toggles use Toggle**, and they're **grouped by body part** (jacket / top / skirt·pants / underwear / socks / shoes …),
  not “one group per outfit” — only one outfit is worn at a time, and the other outfit's meshes are already turned off by the root object
- **With ≥2 accessories at the same position, switch from Toggle to RadialPuppet**: 0=off, 1=accessory 1, 2=accessory 2…
  Only positions with a single accessory keep using Toggle
- **Rings need two controls**: one for on/off, the other a “which finger” radial `0–7`
  (left little / left ring / left middle / left index / right index / right middle / right ring / right little, **no thumbs**);
  the position radial **doesn't handle on/off**; **position and scale are fine-tuned per finger**; one transform can't cover all eight
- **≤8 controls** per menu; beyond that paginate with “Next page ▶”
- Plugins use their own `MenuInstaller`'s **`installTargetMenu`** to slot into your submenu; **don't modify plugin prefabs**
- Vendor menus are **referenced, not copied**

**Soft (re-divided per model)**
How many sections, what each is called, what goes in which group — decide by content, **aiming for simple and clear**.
Reference: Project G used `换装/外观/动作/素体`; it could also be `服装/功能/玩具/头像`.
Copying another project's grouping may actually be a poor fit.

**First check whether the vendor menu is good enough; don't default to building your own.**

## Measured samples

**One vendor parameter often controls meshes, bone poses and blend shapes at once** (three instances of the [60 one-sentence iron rule](../60-menu-and-animation-layers.md)):

| Vendor parameter | What that one parameter controls | Consequence of writing meshes only |
|---|---|---|
| `Outfit_Cap` | Hat mesh + fishbone hair ornament + cat ear mesh and KemoEar bone pose | Ears on, but the bones are still folded into the head |
| `Outfit_Vest` | Vest mesh + two spine shrink blend shapes on the top | Jacket off, but the top is still missing a section, exposing the belly |
| `Outfit_Bag` | Bag + name tag + fish toy in the armature | The fish toy is left floating in place |

**Intervention intensity is also soft** (found by digging through three old projects on site):

| Project | Approach |
|---|---|
| Project G | Built its own root menu, with vendor menus referenced in |
| Project F | **Minimal intervention** — only added a `Clothes` radial to the vendor menu |
| Project E | Used the vendor IKUSIA menu directly |
