> 🌐 English translation · [中文原文](../../../../开发工具/SOP/70_回归测试/必查清单实测案例.md)

# Required checklist: what actually occurred in seven real orders

> A subpage split out of [`70-regression-testing.md`](../70-regression-testing.md). It takes over the section of the same name (post-mortem of defects from seven real orders); steps 1–7 and their criteria remain on the main page.

## Required checklist (what actually occurred in seven real orders)
| Class | Example | How to check |
|---|---|---|
| Same-name key not synced by anyone | Project E Re-Poppin: breast shape at max pokes through; Project B: bodystocking doesn't follow the high-heel foot shape | Step 5 |
| Key missing on a part | Project D Esmera: nipple pasties lack `Breast_small`/`Breast_big(limit)` | Step 3 readings × writer list |
| Writer attached to the wrong part | Lop-eared rabbit: 11 shrink keys attached to the whole outfit; MMN: flat-foot key attached to the socks; Project D Rurune-Black: flat-foot key only on the shoes, stockings not under the socks toggle → toes poke through the stockings once shoes are off | Step 3 + the `MA Responsive:` layers in the post-build FX |
| State bleed | Project B: base-avatar cardigan; Project A: base-avatar underwear in the Kitty tier | Step 4 |
| Grab-pass point too early | Project A: recolor animation references the vendor 2450 material | Probe `grab_chain` ([Transparency sorting and grab pass](../troubleshooting/transparency-sorting-and-screenshots.md)) |
| Alternative parts shown at the same time | Project A: double-layered coat; Project B LUNALICE: long and short gloves | Probe `coincident` |
| Dead menu | Project F: vendor Outfit submenu (layer weight 0) | T4 + zero change in the single-off state |
| Deleted area relies on another part to cover it | Project B Snowflake Romance: footless long socks deleted the ankle (relying on the boots to cover it), leaving a hole at the ankle in "socks on, shoes off" | Read the host part of every ShapeChanger Delete: can the host alone cover that area; render each part "single-off" |
| Delivery root missing a component | Project D: Velvet China shrink SC on the face-tracking root was overwritten and deleted | Present in the writer list but reading is always 0 → compare the components of the two roots ([Face tracking](../30-face-sculpt/facial-tracking.md) section five) |
| One toggle controls several parts | Project F Shellmarin: cardigan/skirt/shoes hang off the same toggle | Preparation-sheet writer list + T1 |
