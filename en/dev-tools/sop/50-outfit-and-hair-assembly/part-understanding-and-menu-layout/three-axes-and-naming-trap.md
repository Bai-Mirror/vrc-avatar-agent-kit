> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/50_服装发型装配/部件理解与菜单编排/三轴与望词生义.md)

> ← [Part understanding and menu layout](../part-understanding-and-menu-layout.md)　Source abbreviations (`sop/` `A/` …) and source levels 〔explicit〕〔corrected〕〔convention〕〔vendor〕〔practice〕: see the main page.

# Part understanding: three axes, and “names are only hints”

## 1. Three axes: every part must fill all three cells

If one can't be filled, write “TBD + what evidence is missing”; it may not be left empty, nor filled in from the name.

| Axis | Values | How to judge (evidence from strongest to weakest) | Cannot be used alone to judge |
|---|---|---|---|
| **What it is** | Free description: what shape, attached/worn where, connected to what | ① Blind-labeled renders (part only + on body, [Blind labeling and sensitive images](blind-labeling-and-sensitive-images.md)) ② Who it toggles together with in the vendor clip (`m_IsActive` paths, [03 Assembly and conflict rules](../../03-assembly-and-conflict-rules.md); only clips in the vendor directory count, see [Conflict checklist](conflict-handling-checklist.md) C03; when the vendor has no switch mechanism write “N/A + source”) ③ Skinning dominant bone (measurement must be “skinning per vertex”), blend shapes, material names unique to this item ④ Vendor showcase images, product description and tags (`.booth-meta.json`) ⑤ Object name; material names shared by ≥2 items in the same set; dominant bone measured “bone to bounding box” | ⑤ alone |
| **Visibility condition** | Always visible / visible only when the outer layer is removed (covered by which item) / visible only in specific poses or views | Default-look renders; “full set - with/without” difference pixels (computed after blacking out the overlay text, [Blind labeling and sensitive images](blind-labeling-and-sensitive-images.md) section 4; method from `B/Assets/_Work/_60内衣.md:3-4`); sitting and squatting renders ([Scenario classification mapping](../../65-perception-mechanism/scenario-classification-reference.md) D8) | Bounding box; “it's underwear so it's covered” |
| **Visual weight** | Selling point / accent / base layer | See “How to judge weight” below | Area or pixel count (small items can be selling points); visibility condition (covered items can be selling points) |

Basis for the weight axis: the author 09-22 〔explicit〕; texture tiering “by how much of the full-body shot it occupies, not by what it's called” ([Textures and PhysBones](../../80-performance-optimization/textures-and-physbones.md)) is an older use of the same idea for performance.

### How to judge weight (candidate criteria; H-03 report in the Velour atlas, pending H-04 verification)

- First fill the atlas's set-level “Style” and “Style tags” rows (tags from `booth_tags` in `.booth-meta.json`); **part weights must cite these two rows**. For sets whose tags include words like セクシー or ランジェリー, skin-tight items may not default to “base layer”; re-assess them one by one.
- Run a set-level comparison round ([Blind labeling and sensitive images](blind-labeling-and-sensitive-images.md) section 2), asking whether each part is a focal point in the showcase images and how many images it's visible in.
- Grading: **selling point** = named by the product description or tags, and a focal point in at least one showcase image; or ranked top 3 in the comparison round and visible in more than half the showcase images. **Accent** = visible, but ranked low and not named. **Base layer** = not visible in the showcase images. **Focal point** = the composition is mainly showing that part (close-up, centered, or occupying a large share), not appearing incidentally; merely being worn in a full-body image doesn't count, and the comparison round's task brief must say so.
- Calibration anchor: the Velour nipple covers were set as a selling point by the user 〔explicit〕. If the criteria fail to yield “selling point”, the criteria are wrong; change the criteria, not the grade the user set. H-03: it failed to yield the Velour nipple covers; the revised proposal is in item 1 of the calibration report in `pkg/The Velour/部件图鉴.md`.
- The Velour product description lists the nipple covers together with the bag as “アクセサリー” (`description_html` in `.booth-meta.json`). That is a weight hint (it was named), not a basis for classification; classification follows the user's “underwear” 〔explicit〕.

### Three axes → default menu handling (candidate; H-03 report in the Velour atlas)

**Switch granularity is decided by weight alone; the visibility condition only governs default values, texture tiers and conflict checks.**

| Weight | Switch granularity | Basis |
|---|---|---|
| Selling point | Separate switch: listed as its own item under its class's area, with its own parameter ([Menu layout decisions](menu-layout-decisions.md) Decision 1) | The author 09-22 nipple covers 〔explicit〕 |
| Accent | Follows the body it hangs on (decorations toggle together), or merged into the accessory group at the same position | [Decoration vs variant criteria](../../03-assembly-and-conflict-rules/decoration-and-variant-criteria.md) |
| Base layer | Merged into body-part group switches (underwear, socks…), shared across sets | [Structure conventions](../../60-menu-and-animation-layers/structural-conventions.md) |
| TBD | Write “TBD”, list both options (separate, merged) side by side for the user; don't pick yourself | Main page section 4 |

| Visibility condition | What it governs |
|---|---|
| Always visible | Default value; textures follow “easily visible main textures are not dropped to 1024” ([Textures and PhysBones](../../80-performance-optimization/textures-and-physbones.md)) |
| Visible only when the outer layer is removed | State which item covers it; go through conflict checks C06, C07 (cover gate, yielding) |
| Visible only in poses/views | Conflict checks must cover poses ([Scenario classification mapping](../../65-perception-mechanism/scenario-classification-reference.md) D8) |

Example: in the full set's default look the Velour nipple covers only show an edge and the front clasp above the corset's upper rim (before the fix, H-03 V9), and are fully visible only once the corset is removed — i.e. “visible only when the outer layer is removed × selling point” — and still get a separate switch. If the table routed by visibility condition, they would land in “merge into the part group”, exactly the opposite of the user's wording.

## 2. Example: both “underwear”, handled differently

The user's own words on 2026-09-22 〔explicit〕 (full text in `lt/作业清单_全部未完成.md:965`):
> I think these nipple covers should be an item with their own switch; classifying them as "underwear" is fine (but they shouldn't toggle together with the panties). What makes them different: they are "underwear" with obvious visual weight, a visually attractive part of a fairly bold, hot outfit, and "not quite the same" as underwear in other outfits that you only see after taking off the outer layer or shirt.

Key point: **classification** (underwear) and **switch granularity** (separate) are two different things; granularity is decided by weight.

| Item | Current handling | Under the 09-22 wording |
|---|---|---|
| Velour nipple-cover item (material name contains bra, not covered by any color variant, `A/_新根菜单方案_调研.md:445`; “the nipple covers the user meant = this item” confirmed by looking at images in H-03) | The new root's menu isn't built yet | Separate switch, classified as underwear, not on the same switch as the panties item; default on 〔explicit·relayed〕 (`lt/作业清单_全部未完成.md:979`) |
| Kaguya base avatar `Pants` | Project A “Underwear” switch, covers only the bottom piece (`A/Assets/Editor/AvatarGen/MenuGenA2.cs:450-453`) | Unchanged (base layer) |
| Itazura's pasties piece (judged by name, **not verified with renders**) | Project C merged it into `Part_Under`, on the same switch as the panties (`C/_物品状态全表_20260909.md:58-59`); in the vendor's bundled private menu it was originally a separate switch | We coarsened the vendor's granularity, opposite to the new wording |
| Sweet Midnight's pasties piece | In the vendor's bundled private menu, pasties and underwear are separate switches; Project D kept the vendor menu | Consistent 〔vendor〕 |
| Esmera `Breast_Bandage` (called nipple covers in the work log) | Project D put it under “Top” (`D/_审查准备_20260918.md:57`) | Opposite |
| Milfy base avatar `BandAid_Chest` (chest band-aid, not verified) | Grouped with `Baretop` under “Top” (`B/_60合规评估.md:97`) | Not verified; candidate same as above |

Whether to change delivered orders is up to the user; don't revert automatically (see [Menu layout decisions](menu-layout-decisions.md) conflict ①).

## 3. Names are only hints: five checks

1. **Blind-label first, match names after**: write “what you see” for anonymous images, then give the names for comparison; inconsistencies go into the atlas's “name hints” column — this is itself a finding.
2. **Read the vendor clip**: who it toggles together with; parameter polarity (whether `true` means shown or hidden).
3. **See how the vendor menu splits them**: what the vendor gives a separate switch or puts in Private, we don't merge.
4. **Look at the vendor showcase images and product description** ([General pitfalls](../../55-accessory-placement/common-pitfalls.md)): is it a main-image selling point, which looks expose it, does the description name it.
5. **Self-check question**: “If I strip off the top entirely and wear only shoes, should this thing be there?” ([Property ownership and writing](../../60-menu-and-animation-layers/property-ownership-and-authoring.md))

### Examples of being fooled by names

| Name | Assumed | Actually | Source |
|---|---|---|---|
| ANEMONE `skirt` | Skirt | Outer layer of a pinafore dress → outerwear | `A/Assets/Editor/AvatarGen/MenuGenA2.cs:434-436` 〔corrected〕 |
| MMN `Ring` | Finger ring | Halo above the head | Same file `:546-549` 〔corrected〕 |
| Violet `Straps` (material `Anklet`) | Top item | Ankle straps | [Property ownership and writing](../../60-menu-and-animation-layers/property-ownership-and-authoring.md) 〔corrected〕 |
| KemoHandMB `Toggle-Foot` | Leg accessory | Animal-paw shoe covers, only exposed in the all-off cell | `B/菜单结构.md:818-824` |
| PixelBoot | Boots | Hair accessory (83×6 false hits in the audit tool) | `A/_施工记录.md:105` |
| “Platform” sneakers | Cover the ankle | Low-top | [Foot-shape and shrink key ownership](../foot-and-shrink-key-ownership.md) 〔corrected〕 |
| Itazura's animal-ear switch parameter | `true` = shown | `true` = hidden | That set's asset pack notes under `pkg/` |
| Shinano `Sweater/Dress/…` five items | Five independent garments | `*_OFF` layering switches of the default outfit | `lt/历史工程总览.md:150` |
| Rurune `leg fixed` | Leg part | Paryi Loco “足固定” (leg lock) | `hist/H5-Rurune/_工程档案.md:112-116` |

The `Rose_Ears` misjudgment wasn't caused by the name but by the bounding box; see the negative example in conflict checklist C02.

### Name traps in Velour (verified against list data; H-03 verified by looking at images)

- The corset part carries its own waist-cinching blend shapes (source: the `pkg/` part list). It is a garment, not the waist-cinching blend shapes that the classification table's “body reshaping” row refers to.
- The nipple-cover part's material name contains “bra”, but it is not a bra and Project A's “bras go under Top” rule does not apply (`A/…/MenuGenA2.cs:443`).
- The material slot names of the neck accessory and the panties cross over each other (`A/_施工记录.md:610`). These are atlas slot names shared across the whole set; they can't be used to tie the neck accessory and the panties together (evidence downgraded to ⑤).

Not yet verified, with name suspicions: a LUNALICE part whose name falls between panties and garter belt (`B/_物品状态全表_20260909.md:101`), and an Itazura part whose name looks like a tattoo sticker but whose vendor switch has a different name (`C/_60菜单规范评估.md:308`). Verify them first when building the atlas (the Velour panties item was verified by looking at images in H-03: it's a thong).
