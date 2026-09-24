> 🌐 English translation · [中文原文](../../../开发工具/SOP/_体积欠账.md)

# SOP Per-Page Size Debt

> The procedure's self-imposed limit is **10 KB** (`00_总表` §per-page size). When exceeded, split into subpages: move down “mechanism explanations / pitfall retrospectives / derivations”; **step tables and criteria always stay on the main page**.
> **The time to split is when a third mutually unrelated topic appears on the same page**, not when a certain byte count is reached; complete criteria > per-page size > fewer pages.
> Per-round records before 2026-09-08 are archived: `_归档/2026-09-18_文档精简/开发工具/_体积欠账_至20260908.md`.

## How to measure (run after each addition to a page)

```bash
cd ~/vrc-processing/开发工具 && python3 -c "
import glob,os
a=glob.glob('SOP/**/*.md',recursive=True)
o=[(os.path.getsize(p),p) for p in a if os.path.getsize(p)>10240]
print('共 %d 页，超限 %d 页'%(len(a),len(o)))
for n,p in sorted(o,reverse=True): print('  %7d B  %s'%(n,p))
"
```

Before changing a page, `wc -c` to see the headroom; after inserting or moving sections, `grep '^#' <page>` to check for duplicate top-level headings and lost headings, and leave a pointer in the original position for moved content (on 2026-09-19 BM overwrote 70's “Common pitfalls” heading, and moved 30's acceptance table without leaving a pointer).

Take a fresh snapshot before splitting, and count over-limit pages only for this round: see [Wrap-up distillation](04-build-log-and-version-control/wrapup-distillation-and-status-header.md) rule layer 2.

Always measure **on-disk bytes** (`os.path.getsize`), not in-memory strings; write files with `newline='\n'` or in binary to keep LF. Check for CRLF before finishing (`grep -rlI $'\r' SOP`).

## Current state (2026-09-19, 101 pages / 541 KB, 2 pages over limit; BS added two subpages `70_回归测试/常见坑` and `70_回归测试/视角与动态姿势`, both to free bytes on the 70 main page)

| Bytes | Page | Disposition |
|---:|---|---|
| 15,915 | `50_服装发型装配.md` | **Exempt** |
| 10,250 | `70_回归测试/旧版_20260918_只当样本.md` | **Exempt** |

### Reasons for exempting the two pages

- `50_服装发型装配.md` — **slim it down together with the D-03 rewrite, don't split it separately**. On 2026-09-18 the author judged that the methods in its shrink key / clipping sections must not be reused directly; it was going to be rewritten along with the regression test procedure anyway; task BH explicitly does not touch this page or its subdirectory.
- `70_回归测试/旧版_20260918_只当样本.md` — **sample only, not maintained**, frozen snapshot. On 09-25 moved to [_legacy/](_legacy/README.md), 4 broken links fixed, header compressed to 10,216 B — no longer over limit; valid conclusions have been lifted into the current pages.

## 2026-09-19: this round split 16 pages (D-29–D-41)

| Page | Before | After | New subpages (under the same-named directory) |
|---|---:|---:|---|
| `00_总表.md` | 12,110 | 10,037 | Two cross-stage reminders (merged back into the overview on 09-25, subpage deleted) / troubleshooting index / manual gates and asset sources |
| `03_装配与冲突通则.md` | 10,462 | 8,892 | Criteria for decorations and variants |
| `05_多模型评审规程.md` | 10,507 | 9,806 | Panel trade-offs and single-model quick review (merged back into the main page on 09-25, subpage deleted) |
| `20_素材清点导入.md` | 10,307 | 9,213 | GUID collisions and fixes |
| `30_捏脸.md` | 12,345 | 10,111 | Route decision / basis and exceptions for the hard rules / scheduling constraints between 30 and 50 / Blender preview aliasing |
| `40_贴图配色/素体贴图与改色手法.md` | 11,977 | 8,918 | lilToon overlay layers / vertical gradient |
| `55_配饰装位.md` | 10,478 | 8,943 | Two-step bone-segment length criterion |
| `55_配饰装位/通用坑.md` | 10,590 | 8,995 | Scale sign of mirrored pieces / skinned-piece localBounds |
| `60_菜单与动画层.md` | 11,756 | 9,333 | Measured samples of structural decisions / parameter audit and semantic conflicts / reading the menu tree without opening Unity / structural conventions |
| `60_菜单与动画层/属性归属与写法.md` | 11,830 | 9,800 | Cost and audit of suppression writes / use a radial for multiple sources at one location |
| `80_性能优化.md` | 10,953 | 9,448 | What AAO actually does |
| `80_性能优化/贴图与动骨.md` | 12,085 | 9,890 | Texture tiering criteria and pitfalls |
| `90_交付打包.md` | 10,299 | 9,545 | Exclude rules anchored to the project root |
| `问题定位/观测口径.md` | 14,446 | 6,562 | The criterion itself may be broken |
| `问题定位/观测口径/渲染与取景.md` | 12,800 | 9,707 | Three pitfalls of the render pipeline |
| `问题定位/素材与材质排查.md` | 10,308 | 9,070 | Vendor variants are not necessarily pairwise distinct |

**27 subpages** added in total, each ≤10,240 B; main pages all ≤10,240 B too. Method: move whole sections without rewording; script `split_page.py` moves by line range and automatically recomputes relative links in subpages for their new location.

Verification (scripts in `_长程任务_20260918/派工/tmp/bh/`):
- **Not a single line of the original lost**: `check_lines.py` merges the non-empty lines of “main page + its new subpages” per page and compares with the pre-split archive `before/`; total missing **0 lines** (20 lines differ only due to relative-link rewriting, 1 line due to rewriting a `../` path inside backticks — path rewrites allowed by item 4, listed separately by the script).
- **Links**: `check_links.py` over all 366 relative `.md` links in SOP; new broken links this round **0**; the 4 that were already broken before the split (all in the exempt `70 旧版`) were listed and left unchanged.
- **Encoding**: UTF-8 without BOM, LF; `grep -rlI $'\r' SOP` is empty.

## Suggested next steps (not done; waiting for sign-off or to be done when next touched)

| Page | Suggestion |
|---|---|
| `50_服装发型装配.md` | Slim it down with the D-03 rewrite; don't split it separately |
| `30_捏脸.md` (10,111), `00_总表.md` (10,037), `80_性能优化/贴图与动骨.md` (9,890), `60/属性归属与写法.md` (9,800) | Already close to the limit; before adding content next time, check whether a third topic appears — split first, then add |
| The “subpage index” tables of each main page | This round's new subpages only left pointers at the original section positions; the index tables were not filled in item by item (`30_捏脸` has no byte headroom left); fill them in when next touched |

## 2026-09-20 23:2x · Size after finishing a round on face-sculpt bumps
- Added `30_捏脸/捏脸凹凸的归因与修复.md` (5569 B); `30_捏脸.md` after adding the index is 10140 B (right at the limit; one more entry and it must be split).
- `问题定位/观测口径/判据本身可能是坏的.md` reached 10266 B after adding “occlusion-type criteria” → **split out** `遮挡类判据.md` (1317 B); the parent page is back to 9220 B.
- `02_环境准备与人工介入/B850_Linux环境.md` reached 11285 B after adding the pgrep/ERE and `read -t </dev/zero` entries →
  **split out** `B850_Linux环境/进程与等待.md` (2419 B, collecting the three entries on pkill/pgrep/waiting); the parent page is back to 9350 B.
- `40_贴图配色/素体贴图与改色手法.md` **was already over** (11628 B); this round only added one subpage pointer line → 11854 B.
  New subpage `素体贴图与改色手法/眼贴图包多半是整脸图集.md` (2647 B). **That parent page needs splitting; noted here.**

## 2026-09-21 03:2x · Splitting subpages from 04
- `04_施工记录与版本管理.md` reached 10550 B after two additions in a row (the heredoc `%` formatting pitfall, the directory's own `.meta` left uncommitted) →
  **split out** `04_施工记录与版本管理/落盘与提交的坑.md` (2029 B); the parent page is back to **9000 B**, with a pointer left in place.
- Full-library recheck: 112 pages; over-limit are still the same 2 old debts (`40/素体贴图与改色手法.md` 11854, `70/旧版_20260918_只当样本.md` 10250).
- Incidentally clarified: the “2026-09-18 fox-ear scaling” on line 24 of `04` looks like a work-log entry that slipped in,
  **but is actually a template example inside a code block** — don't delete it by mistake.

## 2026-09-23 · W2 split three pages + fixed 9 dead links

| Page | Before | After | New subpages (under the same-named directory) |
|---|---:|---:|---|
| `40_贴图配色/素体贴图与改色手法.md` | 11,854 | 9,692 | Two-tone iris colour clashes and colour choice |
| `80_性能优化.md` | 10,621 | 10,051 | Why you can't judge format by reading meta |
| `70_回归测试.md` | 10,307 | 9,101 | Measured cases for the must-check list |

The three new subpages are 2,773 / 1,067 / 1,740 B respectively, all ≤10,240. The method is still `split_page.py` moving whole sections
(spec in `_长程任务_20260918/派工/tmp/w2/`): 40 moved down the three trailing sections “two-tone iris / clash colour choice / lightness compensation”,
80 moved down step 4's mechanism explanation “why you can't judge format by reading `.meta`”, 70 moved down the retrospective table “must-check list (things that actually happened in seven orders)”;
step tables and criteria all stay on the main pages, pointers left in place (`70_回归测试/旧版_20260918_只当样本.md` exempt, untouched).

**Fixed 9 dead links** (only relative paths changed, text unchanged; before each change `ls` confirmed the target exists):

| Page | Old path → new path |
|---|---|
| `70_回归测试/常见坑/编辑器调用与重发.md` | `../02_环境准备与人工介入.md` → `../../…`; `../02_环境准备与人工介入/B850_Linux环境.md` → `../../…` |
| `60_菜单与动画层/VRCFury参数压缩.md` | `../../00_总表.md` → `../00_总表.md` |
| `50_服装发型装配/收缩键流程与两族.md` | `70_回归测试.md` ×2 → `../70_回归测试.md`; `问题定位/观测口径.md` → `../问题定位/观测口径.md` |
| `50_服装发型装配/兼容性判定.md` | `10_接单建档.md` → `../10_接单建档.md` |
| `50_服装发型装配/脚型与收缩键归属/两类键与写者.md` | `../问题定位/观测口径/判据的形状.md` → `../../…` |
| `05_多模型评审规程/证伪任务设计/小部件与像素复核.md` | `../01_自动化执行与并行/步骤模板与硬闸.md` → `../../…` |

**Re-check results (three numbers)**:
- Missing lines **0** (same logic as `check_lines.py`, but using a live snapshot taken right before this split, `tmp/w2/before_w2/`, comparing 17 pages; only 70 had 2 lines hit due to relative-link rewriting, which is allowed).
- New broken links **0** (`check_links.py`: all 568 relative `.md` links in SOP; 4 broken, all in the exempt `70 旧版`).
- Over-limit pages **1**: `70_回归测试/旧版_20260918_只当样本.md` (10,250, exempt). ⚠ During the re-check `00_总表/工具索引.md` was 26,823 B; it was the in-progress output of parallel task W1 “scripted tool index”, on this round's do-not-touch list, **left untouched**, so not counted in this debt.

> Note: the 09-19 `before/` archive had become stale through later changes (re-running directly reports old missing lines for 00/30/60/render-and-framing),
> so this round saved a separate live snapshot `tmp/w2/before_w2/` and checked with the same `check_lines.py` logic (wrapper script `tmp/w2/check_lines_w2.py`).

## 2026-09-23 · Exemption addendum
- `00_总表/工具索引.md`: since 09-25 `tools_index.py --write` writes the per-file table in pages to `00_总表/工具索引/<分页>.md` (each ≤10 KB, auto-split into -1/-2 when over); the main page keeps only the handwritten overview + page navigation (about 4.6 KB), **no longer exempt**.
- In this round Claude's edits to `00_总表.md` and `90_交付打包.md` briefly went over the limit; both were trimmed, and the 3b background was moved down into `90_交付打包/编译态菜单断言.md`.
