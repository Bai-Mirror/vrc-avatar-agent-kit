> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/50_服装发型装配/部件理解与菜单编排/菜单编排决策.md)

> ← [Part understanding and menu layout](../part-understanding-and-menu-layout.md)　Source abbreviations and source levels: see the main page. `A/…/` = `A/Assets/Editor/AvatarGen/`.

# Menu layout decisions: granularity, ownership, radials, defaults

The atlas only records **recommendation + reason + source**; how this order is finally laid out goes into the project's `菜单结构.md`, and partitioning and naming get 2 candidates for the user to decide ([60 Menu and animator layers](../../60-menu-and-animation-layers.md) 〔convention〕).

## Decision 1: separate switch, or merged into a part group

**Merge by default**: part switches are aggregated by body part and shared across sets. The sources describe this differently: the SOP records it as a convention ([Structure conventions](../../60-menu-and-animation-layers/structural-conventions.md)); Project A's generator comment calls it “the user's hard cross-project convention” (`A/…/MenuGenA2.cs:10-12`); Project B records “the mechanism is hard, the clustering is soft (the user's own words, 2026-09-02)” (`B/菜单结构.md:497`). The user's original words for “aggregate by part” itself can't be found, so treat it as 〔explicit·relayed〕.

**What “separate switch” means**: listed as its own item under the area of the class it belongs to, with its own parameter. Example: Velour nipple covers are listed separately under the “Underwear” area, not sharing a parameter with the panties. Don't create cross-set switches named after the item; only once a second set's item of the same type appears and is judged a selling point by the three axes, discuss whether to merge into a cross-set switch.

**Conditions for a separate switch** (any one):

| Condition | Example | Source |
|---|---|---|
| Named by the user | Velour nipple covers (09-22, relayed in `lt/作业清单_全部未完成.md:965`); add-on high heels as an independent switch (`A/_感知/声明.yaml:360`); things held in the mouth as a separate group (`A/…/MenuGenA2.cs:495-499`) | 〔explicit〕 |
| Weight = selling point ([three axes](three-axes-and-naming-trap.md)) | Nipple covers | Generalized from the single 09-22 case; **the generalization itself is pending review**; the default action during review is in section 2 of [DSH execution points](dsh-execution-points.md) |
| Vendor already has a separate switch, and it has visual weight | the pasties pieces of Itazura and Sweet Midnight (already separate switches in each vendor's bundled private menu) | 〔vendor〕 |
| Add-on / replacement items | Project G “long pants”: when on, removes shorts, boots and socks; when off, the three come back (Play test `G/_施工记录.md:43`; a static read of the clip once suggested it didn't restore, `G/_审查准备_20260918.md:58,69`) | 〔convention〕 |
| Two pairs at the same part, vendor shows one or the other | LUNALICE long and short gloves (`B/_施工记录.md:112`) | 〔explicit〕 |

**Opposite direction**: one switch must not remove items from several parts at once — Project F Shellmarin's cardigan, skirt and shoes all hung under “Outerwear”, one click left only the swimsuit, and the user decided to split them (`F/_施工记录.md:47,52,58`) 〔explicit〕.

### Conflict and trade-off ①: separate nipple-cover switch vs “bras always go under Top”

- **Nipple-cover items are exempt from Project A's rule**; the user's 09-22 〔explicit〕 prevails.
- Project A set “chest garments always go under Top, Underwear only covers the bottom piece” (chest garment here means bra: `root:Bra`, `A/…/MenuGenA2.cs:443`), reasoning that when the chest-cover gate judges by switches, “outerwear off, top off, underwear on” would misjudge a bare chest as covered (`:450-453`) 〔convention〕.
- That gate was later changed to judge by an **explicit list of visible items** (`A/_感知/声明.yaml:605-619`, confirmed by the author 09-19), no longer depending on switch ownership, so that reasoning no longer holds.
- **Candidate trade-off (pending Claude's review)**: this set's nipple covers get their own item under the “Underwear” area (Decision 1's definition), without creating a cross-set “nipple covers” switch; and add them to the chest-cover gate's `when` list — otherwise, when the nipple covers are visible, the nipple key is still written to 100 as if bare. Before review, DSH only writes this into the atlas's conflict column and does not change the project.
- Opposite practices in delivered orders — Project C merged the pasties into `Part_Under` (`C/_物品状态全表_20260909.md:58-59`), Project D put `Breast_Bandage` under Top (`D/_审查准备_20260918.md:57`) — whether to change them is up to the user; don't revert them automatically.

## Decision 2: follow the full set

- Form variants of the full set (hood up/down) take full-set slots, not part switches (`A/…/MenuGenA2.cs:88-90,472-473`) 〔explicit〕.
- Base avatar items yielding are written into the full-set layer's curves, with no switch and no parameter slot ([Layer order and suppression](../../60-menu-and-animation-layers/layer-order-and-override.md)) 〔convention〕.
- Items moved away by BoneProxy at build time must be written explicitly in the full-set clip (`C/菜单结构.md:187`) 〔convention〕.

## Decision 3: when to use a radial

- Full sets, hairstyles: RadialPuppet + Float ([Structure conventions](../../60-menu-and-animation-layers/structural-conventions.md)) 〔explicit·relayed〕. The last slot must be selectable (`E/_施工记录.md:59`, the user decided to add one slot to the outfit radial) 〔explicit〕; method: when the vendor clip has `loopTime=1`, make a copy with `loopTime=0` (`:65-66,69`) 〔convention〕.
- ≥2 sources at the same position: radial, with mutual exclusion guaranteed by slots ([Structure conventions](../../60-menu-and-animation-layers/structural-conventions.md); Project B head radial `B/菜单结构.md:613`) 〔explicit〕.
- Ears and tails of the same style combined into one radial (`C/菜单报告.md:112-116`) 〔convention〕.
- **Color schemes**: Project A swaps materials for isomorphic color schemes + color radial (`A/…/MenuGenA2.cs:97-110`; the requirement was to change materials for color schemes rather than add duplicate prefab variants, `:107`) 〔explicit〕. Project B does no runtime switching for hair color and eye color (the author 2026-09-08, `B/菜单结构.md:18,141,220`) 〔explicit〕; whether Project B's **outfit** color schemes should switch at runtime has no user decision on record (the phrase “install only one color variant” can't be found on those lines either, and has been removed). So **ask per order**; the atlas only records “the variant mechanism is swapping objects / swapping materials / swapping textures” (`pkg/_条目模板.md` “variant mechanism”).

## Decision 4: default values

| Item | Default | Source |
|---|---|---|
| Part switches | Worn | `A/…/MenuGenA2.cs:2260`; `B/Assets/Editor/MenuGen60.cs:180-181` |
| Head accessories | Off (ears showing) | `A/…/MenuGenA2.cs:2261-2263` 〔explicit〕 |
| Add-on items (extra long pants, neck ribbon) | Off | `G/_审查准备_20260918.md:19` 〔convention〕 |
| Play items (hug bear, eye area) | Off | `A/…/MenuGenA2.cs:2272-2274` 〔convention〕 |
| Items with rendering risk (leg glass, RenderQueue 3000) | Off | `C/菜单结构.md:277-278` 〔convention〕 |
| Full-body stocking underlayer | Off | `B/菜单结构.md:449` 〔explicit〕 |
| Selling-point items (nipple covers) | Velour nipple covers: **default on** 〔explicit〕 (the author 09-22 13:3x AskUserQuestion, original text copied verbatim in the user-wording table of `pkg/The Velour/部件图鉴.md`). For other sets, until decided, follow the vendor prefab's default activeSelf and the worn state in the showcase images, marked “TBD” | Section 2 of [DSH execution points](dsh-execution-points.md) |

- **Switch semantics within one menu must be uniform**: Project F set `Inverted` on the glasses, unifying eight switches to “lit = removed” (`F/_施工记录.md:52,59`) 〔explicit〕. Projects are already inconsistent: Project G part switches default 1 = worn (`G/_审查准备_20260918.md:19`), Project D defaults 0 = worn, on = hidden (`D/_施工记录.md:38`). So the atlas's “default” column records “worn/removed, shown/hidden”, not 0/1.

## Decision 5: hook into vendor parameters, or write the mesh directly

- Items controlled by a vendor parameter layer always drive the vendor parameter ([60 Menu and animator layers](../../60-menu-and-animation-layers.md)) 〔convention〕; all curves of the vendor ON/OFF clip must be included — writing only `m_IsActive` gives you “mesh gone, body still dented” (`A/…/MenuGenA2.cs:34-42`).
- Vendor parameters that look right by name but whose effect hasn't been verified are not hooked up; keep the vendor's original menu for the client to use (`B/菜单结构.md:176-178`) 〔convention〕.
- Vendor menus are referenced, not copied ([Structure conventions](../../60-menu-and-animation-layers/structural-conventions.md)) 〔convention〕; exception: Project F copied one and deleted the broken entries (`F/_施工记录.md:57`, user decision at `:52`) 〔explicit〕.
- ⚠ “Vendor conventions rank last” only applies to **menu preferences**; **facts** like “which items form a group, parameter polarity” follow the vendor clip ([03 Assembly and conflict rules](../../03-assembly-and-conflict-rules.md)).

## Decision 6: wording

- Chinese part names; the user's terms prevail — Project B renamed one part to the client's preferred term, changing only the display name, not the parameter (`B/_施工记录.md:797,806`) 〔explicit〕.
- Counter-intuitive ownership (items moved out of their original part switch) and mutual exclusions that didn't take effect are written into the delivery notes ([Property ownership and writing](../../60-menu-and-animation-layers/property-ownership-and-authoring.md)) 〔convention〕.
- Conditions go in parentheses, such as `爱心眼开(面捕专用)` (heart eyes on (face tracking only)) (`hist/H4-Manuka/_工程档案.md:43`) 〔practice〕.
