> 🌐 English translation · [中文原文](<../../../../../开发工具/SOP/60_菜单与动画层/属性归属与写法/同一位置多来源用轮盘.md>)

# Multiple sources at the same position: use a radial, not several Toggles overriding each other

> Subpage split out of [60 · Menu and animator layers / Property ownership and authoring](../property-ownership-and-authoring.md). Takes over the section of the same name; wiring of radials and mutual exclusion is on the main page and in `层序与压制.md`.

## Multiple sources at the same position: use a radial, not several Toggles overriding each other

With ≥2 sources at the same position, the scheme of multiple Toggles + mutual overrides has two inherent flaws:
scopes easily get fragmented, and override directions are easily written backwards. **Switch to one radial and mutual exclusion is guaranteed by the steps themselves**;
the override layers disappear along with their deadlock risk.

### Aggregate toggle scopes must be **closed by semantics**, not divided by “what it grows on”

> Evidence (2026-09-08 Project B_Milfy): the “animal ears and tail” toggle originally covered only the base avatar's bear tail, KEMO cat tail, and lop-eared bunny ears/tail;
> while KEMO's **cat-ear headband** went under “headwear”, LUNALICE's **lace cat ears** also went under “headwear”,
> and the fox ears/dog ears bundled with two hairstyles **had no toggle at all**.
> As a result the same set of ears/tail was split across two menu items, and the default state had two pairs of ears: “gyaru cat ears + base avatar bear ears”.

**Self-check**: list each toggle's scope and ask item by item **“are there any other sources at this position”**.
The source list should be enumerated by the scene itself (solo-render each renderer to confirm what it actually is);
don't guess by name — something named like ears may be a hair clip, and something named `Ring` may be a halo above the head.

### Along the way: attachments tied to vendor toggles are easy to miss

A vendor `Toggle-*` often writes several objects at once. Turning off only the main piece leaves small floating parts behind.

> Measured: `KemoHandMB/Toggle-NekomimiHB` writes the headband itself + **two bells**.
> The override table only listed the headband → two bells floated on either side of the head.
> **Read the vendor clip to get the full list**; don't guess by name.
