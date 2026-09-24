> 🌐 English translation · [中文原文](../../开发工具/_导出规格.md)

# Export Spec: “VRChat Avatar Modding Work Guide”

Rewrite the project's internal SOPs and experience notes into a set of documents that **can be shared publicly and can teach others how to mod avatars**.

---

## 1. What changes this time is the “way of stating things”, not the content

The source material is **first-person project notes**: “I ran into this”, “client X required”, “measured on 2026-09-0X”.
The target is **objective teaching material**: the reader doesn't know you, doesn't know your clients, and doesn't have your projects.

### Rewrite rules

| How the source puts it | Change to |
|---|---|
| “I ran into this / I misjudged it for three rounds” | “A common mistake at this step is…” “The symptom is…, the cause is…” |
| “Client requested on 2026-09-02” | “If the requirement is…” or write it directly as a rule, removing time and person |
| “It happened on Project A” | “It occurs on avatars with multiple outfits” |
| “The user escalated it to a hard gate” | “It is recommended to make this step a mandatory checkpoint, because…” |
| “That order for Project F / Project G / Project D” | Delete it, or change to “in one case” |

### Things to keep unchanged

- **All verifiable criteria** (thresholds, formulas, field names, API names, order of judgment) — this is where all the value lies
- **Descriptions of failure symptoms** — readers match their situation by symptom
- **Causal chains** — “why this happens” lasts longer than “what to do”
- Specific commercial product names (lilToon, Modular Avatar, Avatar Optimizer, GoGo Loco, VRChat SDK,
  and base avatar/outfit brands) — teaching needs specificity, and these are public products

### Tone

- Declarative sentences, no “I”. “You” may be used to address the reader.
- Don't write it as a diary. **Every section must be understandable on its own**: first state the symptom or goal, then the mechanism, and finally the criteria.
- Mark uncertain points explicitly (“this item has only been verified in situation X”); don't pretend everything was verified.
- Keep emphasis markers such as ⚠, but don't overuse them.

---

## 2. Content that must be removed (privacy and security)

**Check word by word; don't rely on impressions.** If any of the following appears, delete or rewrite it:

1. **Client names and order numbers**: any number starting with `COMM-`; client code names (Project D / Project G / Project F / Project E, etc.)
2. **The author's own identity**: the author's account names and aliases
3. **Private infrastructure**: intranet server code names, server paths like `/data/...`, the size and location of private asset libraries
4. **Any keys/tokens**: this project's review API key is stored outside the project directory and **must never appear in the export**,
   nor should you write where it is stored
5. **Private details of internal tools**: the specific model lineup and subscription tier of the review tool are internal configuration;
   rewrite them as practice-level descriptions such as “use a second model for adversarial review”
6. Specific dates (`2026-09-0X`) — delete them all, change to conditional sentences

---

## 3. Target structure

Output to `开发工具/_导出/VRChat改模作业指南/`, all Markdown, UTF-8 without BOM.

```
README.md                  What this guide is, who it's for, how to read it, prerequisites and scope
00_全流程总览.md            Stage table + hard rules that apply throughout + index
05_交叉评审做法.md
10_接单建档.md
20_素材清点导入.md
30_捏脸.md
40_贴图与配色.md
50_服装发型装配.md
55_配饰装位.md
60_菜单与动画层.md
70_回归测试.md
80_性能优化.md
90_交付打包.md
问题定位/
  观测口径.md
  场景损坏与恢复.md
  构建被中止.md
  素材与材质排查.md
  透明排序与抓屏.md
  存档与依赖.md
经验条目/
  01_渲染与材质.md
  02_动画层与菜单.md
  03_骨骼与动骨.md
  04_网格与形状键.md
  05_工程与构建.md
  06_工作方法.md
附录_术语与缩写.md
```

**`经验条目/` is the focus this time**: **merge and rewrite** 48 scattered memory entries by theme into 6 coherent articles;
don't make it a checklist of 48 subsections. Entries under the same theme that corroborate each other should be narrated together;
for contradictory or overturned claims, **state clearly which one is correct**.

---

## 4. Source material list

### SOP (include all, rewrite each one)

Under `开发工具/SOP/`: `00`, `05`, `10`~`90`, `问题定位/*`.

### Memory files (`.claude/projects/<项目>/memory/`)

**Include and rewrite (merge by theme into `经验条目/`):**

| Theme | Memory files |
|---|---|
| Rendering and materials | `null-material-magenta`, `fbx-swap-resets-materials`, `offscreen-render-vs-grabpass`, `review-image-granularity`, `review-the-shipped-state` |
| Animator layers and menus | `vrchat-menu-architecture`, `playable-mask-comes-from-layer0`, `additive-layer-needs-ramp`, `finger-muscle-binding-names`, `vrchat-animation-layer-conflicts`, `trace-existing-mechanism-first`, `ma-shape-changer-body-hide`, `vendor-prefab-animator-overrides-mount`, `ft-installer-clones-avatar`, `project-f-clothes-dial` (generalized) |
| Bones and PhysBones | `skinned-bounds-culling`, `vendor-armature-transfer-node`, `boneproxy-no-editmode`, `sampleanimation-collapses-humanoid`, `annular-accessory-fitting`, `wearable-placement-reference-planes`, `embed-reference-surface`, `vendor-pack-scale-to-body`, `layered-face-card-scaling`, `name-is-not-the-part` |
| Meshes and blend shapes | `blender-fbx-export-recipe`, `shapekey-bake-and-compensation` |
| Projects and builds | `unity-scene-parsing-pitfalls`, `unity-asset-create-then-populate`, `generated-asset-verification`, `delete-create-breaks-guid`, `undo-loop-is-destructive`, `never-discard-scene-changes`, `vendor-pack-import-integrity`, `vendor-subpackage-guid-collision`, `ndmf-build-abort-diagnosis`, `ndmf-bake-is-expensive`, `vcc-project-scaffold-and-import`, `unity-project-archiving`, `archive-dependency-reproducibility`, `vrchat-delivery-packaging`, `material-usage-ledger`, `vrchat-avatar-perf-optimization` |
| Working methods | `prove-cause-before-fixing`, `verify-numerically-not-visually`, `stat-criteria-need-controls`, `unity-play-mode-observation-timing`, `scene-view-not-the-avatar`, `prove-cause-before-fixing`, `agy-visual-critique-panel` (generalized), `gemini-check-every-visual-claim` (generalized), `extract-intent-not-steps`, `keep-moving-ask-inline` (generalized into “collaborating with the commissioner”), `run-to-delivery-without-stopping` (generalized), `nail-placement-habits` (generalized as an example of “client conventions must be written down”) |

**Not included (private / client / infrastructure):**

`project-d-commission-status`, `project-g-commission-status`, `personal-vs-client-projects`,
`本机-archive-location`, `old-archive-correspondence`, `vrc-asset-library-on-本机`,
`sop-is-provisional`, `unity-mcp-setup`, `vrchat-commission-workflow`
(the “how project directories are organized” part of the last one can be generalized and merged into `05_工程与构建`,
but **do not** carry over any real paths or client directory names).

---

## 5. Four things the README must make clear

1. **Scope**: VRChat avatar modification (outfit swaps/accessories/menus/performance), Unity + VCC workflow;
   does not cover modeling or texture painting itself.
2. **Prerequisites**: the background readers need (basic Unity operations, the VRChat SDK3 playable layer concept).
3. **How to read**: start with the stage table in the overview; turn to the article for whatever step you're on; when stuck, turn to troubleshooting;
   `经验条目/` is cross-cutting, and reading it through once before starting work is recommended.
4. **Credibility statement**: these conclusions come from actual delivered projects, and most come with reproducible criteria;
   but the VRChat SDK and the various plugins update quickly, so **verify once in your own project before using them**.
   State explicitly the main versions at the time this material was written (Unity 2022.3, VRChat SDK3,
   Modular Avatar, NDMF, Avatar Optimizer, lilToon).

---

## 6. Self-check after completion (write into `_自检.md`)

- [ ] Search the full text for `COMM-`, client code names, the author's account names, server code names, `/data/`, `key`, `token` — hit count is 0
- [ ] Search the full text for `2026-`, `我` — confirm each hit individually whether it should stay
- [ ] Every internal link points to an existing file
- [ ] Every article is understandable on its own (doesn't depend on “as the previous article said”)
- [ ] Not a single criterion, threshold, field name, or API name is lost
