> 🌐 English translation · [中文原文](../../../开发工具/SOP/00_总表.md)

# Avatar customization commission procedure · Overview v2.0

> **Technical process only.** Client communication, quoting, and payment collection are outside this procedure.

> **Public edition note**: this repository is exported from a private workspace and anonymized. `A/`…`G/` (Project A…G) are 7 anonymized projects; `lt/`, `hist/`, `pkg/`, `_长程任务_*`, `_归档/`, `菜单架构/`, `审查产出/`, `…/_施工记录.md:行号` and the like are unpublished records of the original workspace, serving only as provenance markers; things like A-xx, B-T23, D-03, L5-5c, F-01 are ticket numbers from the original workspace.

## How to use this procedure

Four layers, **retrieve on demand, don't read it all at once**:

| Layer | Page | When to read |
|---|---|---|
| **Overview** | This table | Read once at kickoff: the whole flow, the gates, the hard rules that run throughout |
| **Orchestration** | [01 · Automation and parallelism](01-automation-and-parallelism.md) | Read once when scheduling: what can run without a human, what can run concurrently, how to write steps so that even a weak model follows them correctly |
| **Dispatch** | [DSH dispatch](01-automation-and-parallelism/dsh-delegation.md) · [Codex dispatch](01-automation-and-parallelism/codex-delegation.md) · [Subagent prompts](01-automation-and-parallelism/subagent-prompts.md) | **Read once before dispatching**. Work goes to DSH by default (automatically re-dispatched to Codex at peak hours); **project changes are dispatched too**, with Claude doing acceptance ([Project-change dispatch and acceptance](01-automation-and-parallelism/project-edit-delegation-and-acceptance.md)); missed-dispatch self-check [Dispatch boundaries and self-check](01-automation-and-parallelism/delegation-boundaries-and-selfcheck.md); changing DSH config [DSH capabilities and modification](01-automation-and-parallelism/dsh-capability-and-modification.md) |
| **Environment** | [02 · Environment preparation and manual intervention](02-environment-and-manual-intervention.md) | **Go through it every time before touching Unity**: how to tell whether MCP is connected, and how to correctly get a human when it isn't |
| **Work log and git** | [04 · Work logs and version control](04-build-log-and-version-control.md) | **Every step must be logged and committed**: `log_step.py` records entries and the status header, `ws_git.py` commits, two-tier distillation, hooks |
| **Fitting and conflicts** | [03 · General rules for fitting and conflicts](03-assembly-and-conflict-rules.md) | The **triage table** for when you get an item and don't know how to install it, or two items fight; symptom → where to look |
| **Stages** | One page each for `10`~`90` | Turn to the page for the step you're on. Each page opens with a **deterministic step table**; the deep water is in the same-named subdirectory |
| **Troubleshooting** | [Troubleshooting index](00-overview/troubleshooting-index.md) | When stuck, look up by symptom |

**Two cross-stage reminders**
- ⚠ **Regression testing has been rewritten data-first as [70](70-regression-testing.md)** (09-19): no project got body/foot blend shape adaptation to outfits right; the methods of [70 old version](_legacy/70-regression-testing-legacy-20260918.md) and [50/Foot-shape and shrink key ownership](50-outfit-and-hair-assembly/foot-and-shrink-key-ownership.md) must not be reused directly, only as positive/negative samples.
- ⚠ **Face sculpting only adjusts vendor blend shape values** (09-06); AI is forbidden from freely editing vertex shapes, and mesh edits are only for local repair after baking; blend shapes **may be extrapolated beyond 0–1** → top of [30](30-face-sculpt.md).

### Two meta-rules for writing procedures

- **Rules must carry their trade-offs**: state clearly ① where the threshold comes from ② failure modes in both directions ③ what to do when it can't be met ④ the cost of each of the two error types. Self-check: if the number changed, could the agent taking over judge whether it's reasonable? How to write it, with positive/negative examples → [Step templates and hard gates](01-automation-and-parallelism/step-templates-and-hard-gates.md).
- **Each page ≤10 KB (about 5k tokens); split into subpages when over**; priority: complete criteria > page size > fewer pages; step tables and criteria always stay on the main page → [_Size debt](_content-debt.md).

## Division of labor and gates

| Symbol | Meaning |
|---|---|
| 🤖 | Agent completes independently, reports when done |
| 🔒 | **Hard gate**: the user must do it personally, cannot be done on their behalf |
| 🎨 | **Aesthetic gate**: agent produces candidates → multi-model review → continue if passed, escalate to the user only on disagreement |
| 👤 | User decides |
| 🔍 | **Third-party falsification**: required before adopting any conclusion (escalated 09-01); the criterion is "how many times have I restated it", not "is it hard" → [05](05-multi-model-review.md) |

Which places require a human, why, and what automatable parts can be split off → **[Manual gate master table](00-overview/manual-checkpoints-and-asset-sources.md)** (single source of truth).

## Full flow

| # | Stage | Executor | Input | Output (on disk) | Pass criteria (auto-checkable) | Sub-page |
|---|---|---|---|---|---|---|
| 10 | Order intake and project setup | 🤖 | Asset pack `COMM-*_素材/` | `建档.md` (asset list + requirement constraints) | All three txt files read; asset list entry count = product directory count; each compatibility verdict ∈ {supported / not supported / pending bone comparison} | [10](10-order-intake.md) |
| **12** | **Reference image interpretation** | 🔍 | Client reference images | `参考图解读.md` + `参考图解读_Fable路.md` | All five routes marked success/failure; face sculpting direction can be stated as part + direction + magnitude; recoloring can give hex | [12](12-reference-image-reading.md) |
| **14** | **Selection catalog** | 🤖 | 10's compatibility verdicts + own-library hits | `选型图鉴.html` + `.pdf`, client return checklist | HTML has zero external links and every item has an image; PDF `/Btn` count = entry count; PDF text does not contain `复制清单` ("copy checklist") | [14](14-selection-atlas.md) |
| 15 | Kickoff direction | 👤 | `建档.md` + 12's output + 14's return checklist | One-sentence user confirmation | — | — |
| — | Multi-model review | 🔍 | Output of any stage | Review json + adoption list | Detailed tasks: single-model adversarial review; stage commits: 3 models; unclear: expand to 5 | [05](05-multi-model-review.md) |
| 20 | Asset inventory and import | 🤖 | Asset pack + `<asset-library>` library | Project `Assets/`, `导入报告.md`, **`_素材应用表.md`** | No unextracted zips; no missing common/material packs; GUIDs not regenerated; **every row of the usage table has "purpose / reason not used", and the criterion passed a positive-and-negative self-check** | [20](20-asset-inventory-and-import.md) |
| **20.5** | **Blend shape enumeration** | 🤖 | Imported base avatar | List of face-shape / expression keys | Every key name referenced in the plan is in the list (grep one by one) | [12](12-reference-image-reading.md) |
| 30 | Face sculpting | 🔒 30a-2 | Base avatar FBX + 12's direction ∩ 20.5's options | Three restore-point blend/fbx, new FBX, `形态键全量检查.md` | Seam gap <0.3mm, \|Δy\| <2mm; **Basis vs mesh.vertices differ by 0mm**; binary self-check includes vendor material name count; full `.anim` set has no out-of-range extrapolation; **after overwriting the FBX, reassign materials + scan for empty slots** | [30](30-face-sculpt.md) |
| 35 | Face tracking | 🤖 | 30's output | FT avatar root | **Blocked by 30**; cannot start until 30 passes | [30/Face tracking](30-face-sculpt/facial-tracking.md) |
| 40 | Textures and recoloring | 🎨 | Requirements questionnaire + texture pack (scheduled after 30b: replacing the FBX resets materials) | Recoloring candidate images + `配方.py` + base avatar textures | `--fast` quick review at each step; finalization goes through 3-model cross review, ≥2 vendors with no blocker ([05](05-multi-model-review.md)); **every eye/hair color named in the questionnaire has a corresponding output** | [40](40-texture-and-coloring.md) |
| 50 | Outfit and hair fitting | 🤖 | Outfit/hair packs (scheduled after 30b: replacing the FBX breaks the armature lock, see 01 §2) | Scene hierarchy | Part atlas exists (create one if missing); every item has out-of-pack references; zero missing bones | [50](50-outfit-and-hair-assembly.md) |
| 55 | Accessory placement | 🤖 | Accessory packs | Attach-point hierarchy + placement report | Every item is "✓ fitted" (offset < inner radius, angle < 12°) | [55](55-accessory-placement.md) |
| 60 | Menu and animator layers | 🤖 | 50's output | Menu assets + animator layers | Parameters ≤256 bit; ≤8 controls per menu; asset readback non-empty | [60](60-menu-and-animation-layers.md) |
| 65 | Perception mechanism | 🤖 | Declaration + 70's readings | `verdicts.json` | Untested items listed as-is, not counted as pass | [65](65-perception-mechanism.md) |
| 70 | Regression test | 🤖 | Complete project | `回归报告.md` | Verify behavior per 70's discrete levels/toggles and agreed continuous values; motion clipping calibrated per project; explicitly state what is not covered and the run conventions | [70](70-regression-testing.md) |
| 80 | Performance optimization | 🤖 | Project that passed 70 | Before and after `perf_report` | Texture memory decreased; AABB/PhysBone within limits | [80](80-performance-optimization.md) |
| — | Asset usage table backfill | 🤖 | Every time an asset is installed/rejected | Last column of `_素材应用表.md` | No blank cells allowed before delivery; "not used" must state a reason | [20](20-asset-inventory-and-import.md) |
| 90 | Delivery packaging | 🤖 | 80's output | Complete delivery package (format see 90) | First pass 90 step 3 and 3b compiled-state menu behavior assertions; cold import after unpacking compiles, content manifest and sizes match | [90](90-delivery-packaging.md) |
| 95 | Upload and final review | 🔒 | Package + showcase shots | — | — | — |

## Five hard rules that run throughout

**① Anything the vendor already has a parameter layer for: always drive the parameter, don't touch the mesh.**
One vendor toggle often simultaneously drives mesh visibility, bone poses, and blend shapes on other meshes. Writing only the mesh is bound to miss something;
the symptom is "the mesh is there, but the shape or position is wrong". → [60 · Menu and animator layers](60-menu-and-animation-layers.md)

**② Imported ≠ used.** Before delivery, reverse-look-up references by GUID and check them off one by one; anything without out-of-pack references isn't wired up.
→ [20](20-asset-inventory-and-import.md)

**③ Wrong observation conventions are worse than not concluding.** Before reporting "X didn't take effect", first ask: was this observation taken at the right moment,
with the right conventions, and does the validation script itself have a bug? → [Troubleshooting/Observation conventions](troubleshooting/observation-criteria.md)

**④ After changing the scene, self-check first, then save.** Saving without confirming the state turns a recoverable error into an unrecoverable one.
Any call that "runs through the Animator" (`clip.SampleAnimation` first and foremost) will collapse the skeleton on a humanoid avatar.
→ [Troubleshooting/Scene corruption and recovery](troubleshooting/scene-corruption-and-recovery.md)

**⑤ Don't act before the cause is confirmed, and "useless" does not mean "harmless".**
Numbers measured in the source scene can't determine the behavior of the delivered build (the build pipeline heavily rewrites the project);
when you find a change ineffective, don't "just leave it"; if you can't give a reason, revert it. → [Troubleshooting/Observation conventions](troubleshooting/observation-criteria.md)

## Troubleshooting index (deep water, consult as needed) → [Troubleshooting index](00-overview/troubleshooting-index.md)

Observation conventions, scene corruption, build aborts, assets and materials, etc., looked up by symptom. **When you hit a wall, first consult [Troubleshooting logging procedure](troubleshooting/troubleshooting-log-procedure.md) on the spot.**

## Tool index → [00-overview/tool-index](00-overview/tool-index.md)

Dispatch DSH with `通用工具/dsh_task.js`, multi-model falsification with `通用工具/agy_panel.py`; for the rest, look up the subpages by task. Asset sources → [Manual gates and asset sources](00-overview/manual-checkpoints-and-asset-sources.md); project to-dos are in each project's `_任务账本.md`.
