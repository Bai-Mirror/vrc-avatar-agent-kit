> 🌐 English translation · [中文原文](../../../../开发工具/SOP/90_交付打包/上传后自测清单.md)

> ← [90 · Delivery Packaging](../90-delivery-packaging.md)

# Post-Upload Self-Test Checklist (template, 2026-09-23)

**Why**: the post-editor-build measure ≠ the in-game side (remote quantization, sync bits, mirror/first person, other players' view). On 09-22 Project B passed all Play/build final checks, yet after upload the user reported two in-game problems. This checklist makes the “real-device measure” the last box of delivery, ticked by the user in-game.

**How to generate**: convert each entry of `期望.json`'s states into one row; one row per slot of every radial, one row each for on/off of every toggle; then add the fixed items below. Write it into the “Please self-test after upload” section at the end of the delivery notes.

## Fixed items (every order has them)
- [ ] Look once in the mirror and once in first person: default outfit, fully undressed, one slot of each outfit
- [ ] Have a friend (Friends permission) watch you: after switching each radial slot, it changes on their side too (sync bits)
- [ ] Drag the radial to the last slot and the first slot: both selectable, no jumping back
- [ ] Click each toggle twice: on → off → on, no “turned off and can't turn back on”
- [ ] After switching outfits, no small pieces of the old outfit (socks, gloves, accessories) remain
- [ ] With expressions/face tracking on, make 3 expressions: tongue, eyes, and small mouth pieces don't clip through
- [ ] PhysBones: shake hair/skirt/chains, nothing explodes or gets stuck in the body
- [ ] Performance rank and parameter count match the delivery notes (SDK panel)

## Items for this order (generated from `期望.json`)
| # | Action | Should see | Tick |
|---|---|---|---|
| 1 | Outfit radial → slot 1 | … | [ ] |

**Return**: the user sends it back once ticked (screenshot or text); unticked items go into that project's `_任务账本.md` to-do list with the screenshot path attached.
