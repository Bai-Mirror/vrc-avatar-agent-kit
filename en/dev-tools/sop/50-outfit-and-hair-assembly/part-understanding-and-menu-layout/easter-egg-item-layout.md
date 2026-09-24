> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/50_服装发型装配/部件理解与菜单编排/彩蛋项编排.md)

> ← [Part understanding and menu layout](../part-understanding-and-menu-layout.md)　Source abbreviations and source levels: see the main page. `A/…/` = `A/Assets/Editor/AvatarGen/`.

# Easter egg item layout

## Current state: the term “easter egg” did not exist before

`grep -rl 彩蛋` gets 0 hits in `开发工具/`, the client orders, and Project B's root-directory documents (measured on 2026-09-22 when this page was written); the user raised it for the first time on 09-22 and listed it as a required part of the part atlas (`lt/作业清单_全部未完成.md` §H, `:965`).
What past work maps to are the “play / gimmick” categories below. **Section 1 of this page has sources; sections 2 and 3 are candidates**, pending H-03 (Velour demonstration) and user calibration.

**Candidate definition**: easter egg = an effect that is not part of the regular part switches and only appears when actively discovered or combined. Known forms: vendor gimmicks, state blend shapes (ずらし, ほどき — “shifted / undone” types), combined styling presets, hidden or special color schemes, contact triggers. 〔convention〕, proposed by this page, pending user confirmation.

## 1. Past practice

| Class | Examples | How it was placed | Source |
|---|---|---|---|
| Outfit's own prop gimmicks | LUNALICE dagger gift, Violet umbrella, Itazura grab feel | Vendor `MenuInstaller` routed into a self-built submenu (Project C calls it `Menu_OutfitExtras`); if `installTargetMenu` is empty, MA stuffs it into the avatar's root menu | Asset pack notes for the three sets under `pkg/` 〔convention〕 |
| Outfit's own private submenu | The private submenus bundled with Itazura and Sweet Midnight (several part switches + state gimmicks) | Vendor menu kept as-is: Project C put it in “Outfit accessories”, Project D in “Functions/Appearance/<set name>” | each outfit's bundled private menu/parameter assets; `lt/审查产出/工程D/t4_menu/menu_tree.md:101-120` 〔vendor〕 |
| Prop play | Esmera phone camera; Project E umbrella (switch, flowers, WorldPin) | Project D: Functions/Appearance/Esmera/Phone; Project E: Parts/Accessories/Umbrella | `lt/审查产出/工程D/t4_menu/menu_tree.md:103-109`; `lt/审查产出/工程E/t4_menu/menu_tree.md:60-66` 〔convention〕 |
| Play items | Hug bear: off / hugging / being hugged | Three-slot mutually exclusive radial, default off; in the “being hugged” slot the big bear passes over the head, so the halo is turned off | `A/…/MenuGenA2.cs:516-519,630-636` 〔explicit〕 |
| Interaction plugins | SPS, PCS, RealKiss, CERP | Project A puts them in the “Toys” area: the partitioning is what the generator comment calls “the user's hard cross-project convention” (`A/…/MenuGenA2.cs:15`), area built at `:2024-2030`, keyword-to-area mapping at `:2054-2059` 〔explicit·relayed〕. Project B flattened it at the user's request into “Interaction → content” (user raised at `B/_施工记录.md:797`, implemented at `:1395-1403`) 〔explicit〕 | Same as left |
| The user's own old projects | `18+` submenu (DPS, `爱心眼开(面捕专用)` — heart eyes on (face tracking only)); one-click “strip all”, `色色` (lewd), “no clothes”; all three Eku projects installed the same LOGO hair clip | Adult items concentrated in one submenu; conditions written in parentheses | `hist/H4-Manuka/_工程档案.md:40-43`; `hist/早期-作者工程/_工程档案.md:50`; `hist/早期-H12/_工程档案.md:52`; `hist/H1-Eku/_工程档案.md:25` (H2-Eku, H3-Eku same line) 〔practice〕. Whether the LOGO hair clip counts as an easter egg is this page's own generalization 〔convention〕 |

Rules with sources:
- Vendor gimmicks are **not rebuilt and not split into part switches** (`B/菜单结构.md:14,184`, a practice we set on Project B 〔convention〕; `C/_60菜单规范评估.md:97-103`).
- **Effects the client didn't name are not added proactively** (`B/_60合规评估.md:152` 〔convention〕); the user decided not to do one-click meteors (`B/_施工记录.md:1087` 〔explicit〕).
- **Items the design requirements call for but the asset pack lacks** are added from our own library as menu items, with the out-of-pack source listed separately in the delivery notes: pieces that recur in the reference images but are missing from the asset pack are added from our own library (precedent: `C/建档.md:69-80` 〔explicit〕).
- Optional play items are not installed without asking: Stardust body stickers (`A/_素材应用表.md:32`) 〔convention〕.

## 2. The atlas records “easter egg material”; the project decides whether to use it (candidate, no precedent)

**Product layer (written into the atlas's “easter egg material” column)**: what this product itself can be combined into, regardless of which order. Ask item by item:

1. **Did the vendor provide gimmicks or a private submenu?** If so it must be recorded; keep the vendor menu by default (sourced, see above).
2. **Are there vendor-provided state blend shapes?** (ずらし, ほどき types) List them if present.
3. **Can a recognizable styling slot be combined?** E.g. a bold look keeping only the selling-point items + choker + bag; items judged selling points per the [three axes](three-axes-and-naming-trap.md) are the raw material for such combinations. Record “combination + reason + showcase image source”.
4. **Is there anything special among the color schemes?** E.g. the one or two color variants with a clearly different style (set-level “color variants” in the list; Velour has 11 variant prefabs, `A/_施工记录.md:918`).
5. None of the above holds → write “no easter egg material + reason”; don't make things up to fill the column.

**Project layer (written into the project's `菜单结构.md`)**: decide whether to adopt based on this order's requirements. See the requirements questionnaire in [10 Order intake and project setup](../../10-order-intake.md) and [12 Reference image interpretation](../../12-reference-image-reading.md). Example: when the requirements allow it, the outfit's bundled private submenu can be kept; write the link between requirement and decision into `菜单结构.md` rather than inferring it afterwards.
**Every item needs AskUserQuestion before entering the menu** (`CLAUDE.md` mandatory rule 4); “don't proactively add what the client didn't name” still applies.

## 3. Placing into the menu (candidate)

- Vendor gimmicks: reference the vendor menu, collected into one submenu per set name (Project D's approach); `installTargetMenu` must be set.
- Private/adult items: concentrated in one submenu, not mixed with appearance (two precedents: vendor `Private`, the user's old-project `18+`).
- Default off (Project A's play items default off, `A/…/MenuGenA2.cs:2272-2274`).
- The relationship with part switches must be spelled out: Itazura's “underwear” and “pasties” switches are in the vendor `Private`, while our `Part_Under` also controls the same items (`C/_物品状态全表_20260909.md:57-63`) — when one item has two entry points, the project documentation must state who the owner is.
