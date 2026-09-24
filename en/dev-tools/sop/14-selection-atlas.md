> 🌐 English translation · [中文原文](../../../开发工具/SOP/14_选型图鉴.md)

# 14 · Selection atlas　🤖

> An **atlas** for the client to pick assets from (also called the asset-selection atlas): image + Chinese name + style tags + checkable,
> the client picks in their chat app and sends the list back.
> Comes after [10 Order intake](10-order-intake.md) and before [15 Set direction at kickoff](00-overview.md);
> independent of [12 Reading reference images](12-reference-image-reading.md), so they can run in parallel.
> **Output**: `<订单目录>/选型图鉴.html` + `选型图鉴.pdf`, plus the list the client sends back.

## Why two versions, and what each can't promise

Clients can't make sense of folder names and won't browse Booth; **only images + Chinese names + style tags let them pick**, and checkbox return saves a round trip compared to screenshots.
The cost of sending only one version is the client being unable to open or check it, adding a round trip (measured in days); the cost of making both is the extra time on the PDF pipeline (measured in hours).

| | Single-file HTML (**primary**) | Checkable PDF (compatibility version) |
|---|---|---|
| Thumbnails | WebP **480px / q74**, base64 embedded, zero external links | Rebuilt with **320px** to reduce size |
| Interaction | Category filter, search, click to enlarge, check count, **"Copy list"** copies the checked items as text | `/Btn` checkboxes + one `/Tx` multi-line notes field |
| Can't do | — | **One-click copy list**: needs JS embedded in the PDF, which only Adobe Reader executes; Chrome / Edge / WPS / mobile don't run it |
| WeChat / QQ built-in preview | Opens | **View only, can't check** |

**Write the copy for the two versions separately**; the PDF version must not promise features only the web version has.

**Where the size comes from**: 187 items ≈ 5.5 MB, about 30 KB/item — the measured point of "forwardable yet the style is still clearly visible".
Larger images → the single file exceeds the chat app's forwarding limit; smaller → style details like lace and patterns become illegible and the client can't choose.
When there are far more than 187 entries, size grows linearly: first drop WebP to 320px (the tier verified in the PDF version), then consider splitting files by category
(once split, the client easily misses one); before splitting, measure the target chat app's single-file limit.

**Zero external links is a hard constraint**: no dependency on any CDN (for mainland China), **no Google Fonts; fonts use the system stack only**.
The symptom of violating it is a blank page or fonts stalling for tens of seconds on the client's side — while everything looks fine on your own machine.

## Deterministic steps

### Step 1 · Pool the candidates　🤖

**Preconditions**
- [ ] "Opening packages to check compatibility" in [10](10-order-intake.md) is done; every item has a verdict of "supported / not supported / pending bone comparison"

**Execute**
1. Items in the client asset pack that **support this base avatar**
2. Plus compatible items from our own library (this machine's `<asset-library>`): filter by the structured fields of `.booth-meta.json`, **not full-text grep** —
   `avatars[]` (`{name, source, confidence, status}`) is the primary criterion; `files[].avatars[]` is the strongest signal (the package really contains a sub-package for that base avatar);
   `variations[]` / `booth_tags[]` are supplementary. Product names in the pipeline contain spaces, full-width brackets and emoji, so `xargs` must use `-0` throughout
   (miss one `-0` and a directory name gets split into multiple lines; measured 164 vs. true value 56)
3. Tag each card **"her library / my library"** (client-supplied vs. added by us — they must be packaged separately at delivery, [90](90-delivery-packaging.md))

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of entries == number of compatible items in the client pack + number of hits in our own library | Add up the three numbers |
| Each entry's source tag ∈ {her library, my library} | Card data column non-empty |
| Items judged "not supported" in 10 hit == 0 in the atlas data | grep each one |

**STOP**
- If any item is "pending bone comparison" → finish the comparison per [50](50-outfit-and-hair-assembly.md) before it goes into the atlas; don't put it in first and sort it out later

### Step 2 · Make thumbnails　🤖

**Execute**
1. For each item take the product images under `images/`, WebP 480px / q74, base64 embedded; for batch fetching
   read this machine's `<asset-library>/*/images/` directly, locating by product-number wildcard

**Post-criteria**

| Expected | How to read |
|---|---|
| Images per item ≥ 1 | Count them |
| Total size ≈ 30 KB × number of entries (same order of magnitude) | `os.path.getsize` |

### Step 3 · Generate the HTML　🤖

**Execute**
1. Single file: category filter / search / click to enlarge / check count / "Copy list"

**Post-criteria**

| Expected | How to read |
|---|---|
| Hits for `src="http` / `href="http` / `@import` / `fonts.googleapis` == 0 (except the PDF variant in step 4, which deliberately carries `x.pick` links) | grep the file |
| After checking N items, "Copy list" outputs N lines | Click it once in the browser |

### Step 4 · Generate the PDF　🤖

**Execute**
1. Rebuild an HTML version with 320px thumbnails, **rendering each checkbox slot as `<a href="https://x.pick/<id>">`**
2. Output with Chrome `--headless --print-to-pdf` — it outputs the links as link annotations as is
3. With pypdf, iterate over each page's `/Annots` and **replace these links in place** with `/FT /Btn` checkboxes:
   provide full `/AP` `Yes` / `Off` appearance streams + `/MK`; enable `NeedAppearances` in AcroForm
4. Add one `/FT /Tx` multi-line notes field
5. Verify with pymupdf: set each of `widgets()` to True, then `get_pixmap`, and check the checkmarks actually render

> The point of this detour is to **let Chrome compute the coordinates for you**: the rectangle of a link annotation is the element's real position on the page.
> Computing checkbox positions yourself means hard-aligning with the layout, and every layout change breaks it all.

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of `/FT /Btn` == number of entries; number of `/FT /Tx` == 1; leftover `x.pick` links == 0 | Count by iterating `/Annots` with pypdf |
| Renders with True and with False differ in pixels | Subtract two pymupdf `get_pixmap` images |
| Hits for `复制清单` (Copy list) in the PDF text == 0 | Extract text and grep |

**STOP**
- Number of checkboxes ≠ number of entries → first list which ids don't appear in `/Annots`, then go back and fix the layout; **don't patch coordinates by hand**

### Step 5 · Send out and collect　🤖

**Execute**
1. Send both together; the HTML note says "check your picks, click Copy list and send it to me", the PDF note says "check your picks, save, and send it back"
2. Save the returned list as is into `<素材包>/客户需求/`, and fill the selected items back into the purpose column of `_素材应用表.md` ([20](20-asset-inventory-and-import.md))

**Post-criteria**

| Expected | How to read |
|---|---|
| Every item in the returned list can be found by id in the atlas data | grep each one |
| The "purpose" column for selected items in the application table is non-empty | Table |

## Related

- Where compatibility verdicts come from → "Opening packages to check compatibility" in [10 Order intake](10-order-intake.md); packaging separately → [90](90-delivery-packaging.md)
