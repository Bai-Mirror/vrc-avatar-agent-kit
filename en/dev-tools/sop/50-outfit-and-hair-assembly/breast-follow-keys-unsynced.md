> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/50_服装发型装配/胸型跟随_同名键无人同步.md>)

# Breast-shape follow: the clothing carries the body's same-name breast keys, but nobody syncs them

> Parent: `../50_服装发型装配.md`. Measured on Project E (Rurune) 2026-09-19; fixed.
> Re-run script (C-12): `开发工具/通用工具/审查/unity/Editor/T3RpSyncSim.cs`, menu `Tools/AvatarAudit/T3 RP Sync Sim (Edit Mode)`; request `Library/AvatarAudit/t3_rp_sync_sim_request.json`, example `审查/unity/examples/t3_rp_sync_sim_request.json` (original values from Project E `t3_rp_b1_sync`).

## Trigger
The body's breast-shape keys get driven (the vendor menu has a breast-shape radial / BlendTree, or we built breast-shape steps), and some top, jacket, hood or tie mesh **also has same-name keys** (`Breast_small_____胸_小`, `Breast_big(limit)`, `Breast_Big_____胸_大(mizuki)`…). Same-name keys = the vendor expects you to sync them; many vendors (e.g. PLUMARIUM Re-Poppin) ship prefabs without an MA BlendshapeSync and without any manual.

## Questions (answerable without looking at images)
1. Which breast-shape keys on the body are written? (T1: run one state at each end of the breast shape, read the values on `Body_b`)
2. For every visible upper-body garment: does it have same-name keys? Do those keys **follow** at both ends of the breast shape?
3. For pieces that don't follow, are they intentionally fixed (e.g. a strap tuned for large breasts that fits fine at the default breast shape)? Fixed pieces must be confirmed individually by image; don't sync everything blindly.

## What happens if you get it wrong
Project E's Re-Poppin: the shirt, jacket, tie and two hoods were stuck at 0; with the body's breast shape maxed, both breasts poked through entirely (frontal skin-colored pixels 6,822 vs 837 after syncing), visible to the client with one drag in the original menu. At the default breast shape (0.31) it is almost invisible, so it was missed at delivery.

## Fix
Add one MA BlendshapeSync per piece, `ReferenceMesh` pointing at the body under the same root, binding every same-name key that exists on the piece (local name = source name). Do it for both avatar roots (normal / face-tracking version). After the fix, T1 reads back at breast shape 0 / default / 1; the piece's values should equal the body's value for value.

## Trade-offs
- An open-front jacket (AQUA parka) doesn't cover the chest; if the pieces underneath are already synced, leave it alone — judge by skin-colored pixels in a render with breast shape maxed; if 0, don't touch it.
- Pieces whose fixed value was tuned by someone else (strap `Breast_Big(mizuki)=100`) are left untouched unless a problem is visible at max.
- Perception phase 1 turns this into a static rule: intersection of piece and body key names × keys written on the body × no writer on the piece → candidate (task AK).

## Numeric mismatch ≠ visible (2026-09-19 Project D jacket A)
`key_follow_verdict.py` reported a harness/top mismatch of 38, but measured distance: with the piece at 0 or 38, p50 distance to the body is 5.8 mm in both cases (top 14.5→14.1) — the piece sits in a region where that key barely moves anything. **Measure geometry before judging “needs fixing”**: in edit mode, `BakeMesh` both body and piece at the two mismatched values and compare quantiles of the piece-to-body nearest distance; a change < 1 mm is recorded as “no visible consequence” and the delivered piece is left untouched. Tool TODO: weight the verdict by “displacement of the key within the piece's region”.
