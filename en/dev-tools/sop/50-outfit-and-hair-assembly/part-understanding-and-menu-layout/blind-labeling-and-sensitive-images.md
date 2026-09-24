> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/50_服装发型装配/部件理解与菜单编排/盲标与敏感图.md)

> ← [Part understanding and menu layout](../part-understanding-and-menu-layout.md)　Sister page: [Visual division of labor and evidence](visual-division-and-evidence.md). Source abbreviations and source levels: see the main page.

# Blind labeling and sensitive images: how to dispatch step 3

**Why blind labeling**: the tool overprints “product name / renderer path / view” and “tris / mats=material name” in the top-left corner of every image (`开发工具/通用工具/部件图鉴/PartAtlasCapture.cs` file header comment; `part_atlas_overlay.py:95` overwrites in place, keeping no text-free original; all 300/300 images from the H-02b reshoot are overprinted, `A/_交付/部件图鉴_拍摄报告.md:90`), and file names carry part names too (`<序号>_<部件名>_仅部件-正面.png`). When a model sees bra, briefs, corset in a part name, it answers by the name — exactly the naming trap the user wants to prevent. Until the tool is changed to also save text-free originals, handle it as follows.

## 1. Blind labeling (first round)

1. **Make anonymous copies** in the scratchpad, not in `素材包说明/`: black out the overlay text box and rename by anonymous ID `P05_v1.png`…; the ID mapping table stays local only and is not written into the task brief.
2. **No mesh names, material names or product names in the task brief**. Only ask: “What is this? Where on the body is it attached/worn? What is it connected to? Is it conspicuous in the full set?”
3. **Exit criterion**: join all of this set's mesh names and material names into one regex, grep the task brief and the list of input image paths; the result is 0.

Use the functions below for blacking out. The width of the overlay text box varies with the text length (`part_atlas_overlay.py:77-82`), so black out the entire horizontal band. The with/without paired images must use the same band:

```python
from PIL import Image, ImageChops

def band(im):   # bottom edge of the overlay box: walk down along x=12 until it's no darker than the top-left background
    bg = sum(im.getpixel((5, 5))) - 60
    y = 12
    while y < im.height and sum(im.getpixel((12, y))) < bg: y += 1
    y += 2
    if y > 160: raise ValueError("叠字框量出 >160，停下人工看")
    return y if y >= 80 else 110    # <80 = mismeasured (overlay text is at least two lines ≈83), use fixed 110 instead

def masked(path, y1):
    im = Image.open(path).convert("RGB"); im.paste((0, 0, 0), (0, 0, im.width, y1)); return im

def diff_px(a, b):   # with/without pair: black out the same band, then count nonzero pixels
    y1 = max(band(Image.open(p).convert("RGB")) for p in (a, b))
    d = ImageChops.difference(masked(a, y1), masked(b, y1)).convert("L")
    return sum(1 for v in d.tobytes() if v > 0), y1
```

Measured on 72 Velour images: most measured 83～105 (two to three lines of text); the nipple-cover item's “on body - side” image measured 14 — something was under the box and it wasn't measured correctly. The panties item's “full set - with/without” pair measured 55, **covering only the first line; the second line `tris=… / mats=<材质名>` was exposed below the band** (a bright sleeve sat under the box bottom at x=12, so the walk stopped at 55) — this was only noticed on 09-22 in H-03 when the blacked-out images were stitched into a contact sheet; the original judgment “still covered” was wrong, and the threshold was therefore raised from `<50` to `<80` (overlay text is at least two lines, minimum about 83). `>160` raises an error and stops.
**Always look after blacking out**: stitch the top 200 px of all anonymous images into a contact sheet and look through it; no text is allowed below the band. The exit criterion only greps the task brief and paths and **cannot detect leftover text inside images**, so this step cannot be skipped.

## 2. Name matching (second round) and set-level comparison

- **Name matching**: send it the mesh names, material names and vendor switch names, and compare with the first round's descriptions; mismatches go into the atlas's “name hints” column.
- **Set-level comparison** (in a separate session): inputs are the vendor showcase images (`images` in `.booth-meta.json`; all 21 for Velour are `kind=main`) plus each part's image C “full set - with” (from H-02b on, the one framed per part), with parts using anonymous IDs. Ask: “In these images, which numbered parts are the focal points of the picture? Rank them by conspicuousness, and state how many showcase images each is visible in.” For the grading criteria see section 1 of [three axes](three-axes-and-naming-trap.md).
- **Batching**: one session per part, ≤8 images; the comparison round in its own session. One Velour set has 54 part images (72 after H-02b added full-body comparisons) and 21 showcase images; stuffing them all in at once tends to time out and to miss reads.
- **Verification**: dispatch with `dsh_task.js --images` and check its per-image verification PASS; a rejected `read_image` doesn't count as read ([DSH silent failures](../../01-automation-and-parallelism/dsh-silent-failure.md) ⑤). Just checking whether the session log contains a call is the old criterion, which misses things.

## 3. Sensitive images (**the user decided 09-22 13:3x: may be sent externally**)

- **The user's decision (AskUserQuestion, 09-22 13:3x)**: part images (including near-nude “on body” images of nipple covers, panties, etc.) **may be sent externally** to DeepSeek / Gemini for labeling and falsification; when a model refuses to answer, fall back to geometry data and image A.
  The old “don't send nude renders to agy” (`A/_施工记录.md:294`) was Claude's own practice, not a user requirement, and is void.

- **Judge sensitive items by geometry and image A, not by name**: skin-tight small pieces covering the chest or lower body, not full garments. Dominant bone including Breast or Hips is only trustworthy when the measurement is “skinning per vertex”; when it is “bone to bounding box” (all 9 Velour items are, `A/_施工记录.md:926`), judge from image A.

## 4. Difference pixels (the tool doesn't compute them; compute separately)

- Use section 1's `diff_px(with, without)`. **Subtracting directly without blacking out counts the “with” and “without” labels themselves**: measured when this page was written (09-22) on 9 Velour pairs, whether full-body framing or H-02b per-part framing, the overlay text area was exactly 418 px for every pair. That is of the same magnitude Project B used to judge “not visible” (≤253 judged not visible, 482 and 686 decided by looking, `B/Assets/_Work/_60内衣.md:6-20`).
- To see where the difference is: `python 开发工具/通用工具/img_tools.py diff-crop <输出目录> <有.png> <无.png>`, which automatically crops out the hot zones.
- Project B's numbers didn't record the frame size or pixel threshold (`_60内衣.md` is 20 lines in total), and are not comparable with 768² images. **768² images need re-calibration; until calibrated, difference pixels are only supporting evidence.**
- Example: in H-02 agy judged the Velour nipple covers fully covered by the black tube top in the full set's default look (`A/_施工记录.md:935`), yet after blacking out the overlay text the difference was not 0: 429 px with full-body framing, 2153 px with per-part framing (threshold >0). H-03 settled it: an edge and the front clasp were showing (before the fix), not shadow — the close-up, Gemini (V9) and the 1075 px with Σ|Δ|>40 agreed (`pkg/The Velour/部件图鉴.md` “falsification results”).

## 5. Blind-labeling pitfalls hit during the H-04 three-set rollout (09-22)

- **When the blackout function's background reference point (5,5) lands on the character**, `band()` measures >160 (Lead under 4/40 images): switch to parsing the overlay box bottom (the box height in `part_atlas_overlay.py`), or find the box bottom from the brightness difference between x=11 and x=3–8.
- **When the writing model has no image input**, “always look at the contact sheet after blacking out” becomes: programmatically reconstruct the overlay area and assert that the text bottom < the mask band; or open a separate vision session that only looks at the contact sheet (Kaguya original `_agy/maskQA_残留文字.md`).
- **When splitting blind labeling into segments, every segment must include the “part only” images**, otherwise later segments can only guess from full-body images (Kaguya original beret: the two segments reached inconsistent conclusions).
- **Assert consistency between the IDs of with/without paired images and the task brief's wording** (Lead under P01's first run wrote v5/v6 swapped, voided and rerun).
