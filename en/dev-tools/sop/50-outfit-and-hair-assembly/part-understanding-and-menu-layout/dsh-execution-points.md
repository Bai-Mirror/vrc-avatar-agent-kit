> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/50_服装发型装配/部件理解与菜单编排/DSH执行要点.md)

> ← [Part understanding and menu layout](../part-understanding-and-menu-layout.md)　Source abbreviations and source levels: see the main page.

# DSH execution points: fixed task-brief lines, default actions when undecided, integration points

## 1. Fixed task-brief lines (included in all three kinds: fitting, building/changing menus, building atlases)

```
- First look up the file by Booth product ID: grep -rl '<商品号>' 开发工具/素材包说明/*/部件图鉴.md; handle the result per the four states in section 1 of the method page.
- A fitting task doesn't stop when the atlas is missing: after attaching and confirming rendering, shoot and build the file; menus and shrink keys are not finalized. A build/change-menu task stops when the atlas is missing and reports NO-PARTS-DOC <商品号> <商品名>.
- Before reshooting, check 开发工具/素材包说明/<商品名>/部件图/: if non-empty and this task brief doesn't say “overwrite same base avatar”, stop and report ATLAS-DIR-NOT-EMPTY.
- Build the file filling every field of 开发工具/素材包说明/_部件图鉴模板.md; if not applicable write “N/A + reason”; deleting fields is not allowed.
- Labeling is two rounds: blind labeling uses anonymous copies (overlay text box masked, renamed P<nn>_v<k>.png), and the task brief contains no mesh names, material names or product names; names are given in the name-matching round. Anything with images always uses --model vision plus --images, and only per-image verification PASS counts as read; one session per part, ≤8 images.
- Sensitive items (judged from image A and geometry: skin-tight small pieces covering the chest or lower body; not judged by name) **may be sent externally** (the user decided 09-22 13:3x); when a model refuses, fall back to geometry and difference pixels, and note in the atlas's “evidence” column which images were refused.
- Every menu and conflict recommendation carries “path:line” and a source level (explicit/corrected/convention/vendor/practice); visual weight, default values and easter eggs are written only as “recommendation + reason”, marked “pending Claude/user decision”.
- Always extract vendor zip/unitypackage with `-C <临时目录>`, **never into cwd** (on 09-22 PuNyaNya left 75 GUID directories in the workspace root).
- When nesting DSH dispatches (opening vision sessions for parts), `~/.dsh` is read-only in the sandbox: `HOME=<工作区临时目录>` (copy in `.dsh/profiles` and credentials) + `DSH_BIN=<绝对路径>`, and **delete the shadow credentials when done**; see the nested dispatch section of [DSH capabilities and modifications](../../01-automation-and-parallelism/dsh-capability-and-modification.md).
  - With several nested sessions running concurrently, the verification block may report “can't identify session” with exit code 2 (09-22 H-05 6/6) while the answers are actually fine: first manually decompress `<影子HOME>/.dsh/sessions/**/session.jsonl.zstd` and check the `read_image` count before judging; root cause (found and fixed 09-22 22:40): when nested, `dsh_task.js` inherited `DSH_HOME=<真家目录>` and `HOME=<影子目录>` and looked for sessions by DSH_HOME, while the child process wrote sessions by the shadow HOME; changed to look in the child process's `$HOME/.dsh/sessions` (old version reproduced FAIL in the same environment, new version PASS; H-05 re-verification nested 28/28 claimed successfully).
- If the vendor switches are not in MA MenuItem components but in a **prefab VRCExpressionsMenu asset** (`menuToAppend`) + FX under the `MA_Animator/` directory, the capture tool's “vendor clip / switch components” columns will be 0/empty (09-22 bunny loungewear); read these two places manually.
- Output: the atlas goes into 开发工具/素材包说明/<商品名>/; this task doesn't change the project menu. Dispatch with --record <the project that triggered this atlas build>, and the work log is recorded in that project; commit the atlas with ws_git, with the product ID in the commit message.
```

For the `--record` rules see `CLAUDE.md` mandatory rules 5 and 6; for text masking and batching see [Blind labeling and sensitive images](blind-labeling-and-sensitive-images.md).

## 2. Default actions when undecided

Of what the method page and subpages mark “candidate”, “pending review” or “undecided”, only the items in the table below apply; when DSH hits one, do what the “Default” column says and write one line in the atlas's “undecided” column. **Rules outside the table must be followed**; situations outside the table that really aren't covered are handled as “write a recommendation + mark TBD, don't apply to the project”.

| Undecided item | Where | Default |
|---|---|---|
| Generalizing the nipple-cover wording to other sets (selling point → separate switch) | [Menu layout decisions](menu-layout-decisions.md) Decision 1 | Write both options (separate, merged) side by side, marked “TBD” |
| Weight grading criteria (comparison-round thresholds) | [Three axes](three-axes-and-naming-trap.md) section 1 | Grade by the candidate criteria, marked “candidate”; if the Velour nipple covers come out not a selling point, report “criteria need revision” and don't change the grade the user set |
| Whether the chest-cover gate should include selling-point items | Menu layout decisions conflict ① | Write into the atlas conflict column as a candidate; this task doesn't change the project |
| Sending sensitive images externally | [Blind labeling and sensitive images](blind-labeling-and-sensitive-images.md) section 3 | **Decided: may be sent** (the author 09-22 13:3x) |
| Selling-point items default worn/removed | Menu layout decisions Decision 4 | Follow the vendor prefab's default activeSelf and the worn state in the showcase images, marked “TBD” (Velour nipple covers decided: **default on**, the author 09-22 13:3x) |
| Difference-pixel threshold for 768² images | Blind labeling and sensitive images section 4 | Supporting evidence only; don't conclude “not visible” from it alone |
| Whether to adopt easter egg material | [Easter egg item layout](easter-egg-item-layout.md) | The atlas only lists the material; nothing goes into the menu |
| Body/foot blend shapes | [Conflict checklist](conflict-handling-checklist.md) C08, C09, C11 | Only write “candidate keys + candidate host + to verify” |

## 3. Integration points (H-06, landed 09-22)

50 step 1 preconditions + subpage index, 60 step 2 preconditions, the gate on the 50 row of the 00 overview table, item 4 of [Project edit dispatch and acceptance](../../01-automation-and-parallelism/project-edit-delegation-and-acceptance.md); lookup script `开发工具/通用工具/部件图鉴/check_parts_doc.py` (four states, exit codes 0/10/20/30); when the `dsh_task.js` task text matches `装配|菜单|部件图鉴|换装|服装` and carries a Booth product ID, it automatically looks up the file and appends the result to the end of the task brief (`--no-parts-check` turns it off). See task list H-06.

## Descriptions often miss “small but conspicuous metal parts” (09-23 H-05 spot checks, two hits in a row)
- Rogue Noir `Bat` missed the two spiked metal bands on the bat head and the wine-red/white color split; Peridot `2. Belt` missed a row of silver round rivets on the strap face — both pointed out by Gemini in spot checks, and written by neither DSH's blind-labeling nor its name-matching round.
- **When writing descriptions, go through item by item**: main color / color split → material (leather/cloth/metal/transparent) → metal parts (buckles, rings, chains, rivets, spikes, tags) → patterns/prints → shape keywords. Metal parts have a big effect on perceived weight (highlights draw the eye); missing them misjudges an “accent” as “base layer”.
- Spot-check rule: Claude spot-checks at least 1 part per atlas, sending the original description text + the part-only and on-body images to Gemini asking “are any obvious features missing”, and annotates additions inline with “Claude spot check + Gemini”.
