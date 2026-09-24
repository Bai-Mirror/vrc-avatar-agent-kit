> 🌐 English translation · [中文原文](../../../../开发工具/通用工具/审查/README.md)

# VRChat avatar visual audit tools · T1 `AuditStateDriver` / T3 `AuditTurntable`

> Design basis: the T1 and T3 sections of `_长程任务_20260918/审查工具设计.md`.
> Runtime environment: Unity 2022.3.22f1 (Editor assembly; from T-09 on in the `AvatarAudit.Editor` asmdef, no longer compiled into `Assembly-CSharp-Editor`).
> This round **only wrote code and did not start Unity**; the code has been compiled successfully with Unity's bundled Roslyn/Mono compiler against Unity 2022.3.22f1's
> reference assemblies (see §0.2); runtime behavior awaits Claude's acceptance in the Project A project.

---

## What this directory is

A VRChat avatar **visual/data audit toolkit**: inside Unity it drives menu states, reads visibility and blend shapes, runs geometric probes, renders turntables, and exports the menu tree and part inventory (`unity/`, a C# Editor assembly); Python scripts then generate requests, merge and analyze results offline (this directory's `*.py`, `perception/`). The goal is to turn "are the toggles right, does clothing clip, are the menu's promises kept" from eyeball comparison into re-runnable data.

| Location | Contents |
|---|---|
| `unity/` | Unity-side source (`Editor/`, `Runtime/`, deployed to the project's `Assets/AvatarAudit/`) and edit-mode small tool request samples (`examples/`) |
| `t5_shapekey_matrix.py` · `menu_expect_check.py` · `dual_root_diff.py` | Offline scripts: blend shape dependency matrix, compiled-state menu assertions, dual-avatar-root difference survey |
| `perception/` | Perception mechanism offline tools (declaration validation, writer graph, validator, pose library, sync/strip), see [perception/README.md](perception/README.md) |
| `replay/` | Defect replay library, see [replay/README.md](replay/README.md) |
| `docs/` | All documentation (see the documentation directory) |

## Dependencies

- **Unity 2022.3.22f1** + VRChat SDK3 Avatars. `AvatarAudit.Editor.asmdef` references NDMF, Modular Avatar core/editor, AAO `api.editor`, `VRC.SDK3A`, `AvatarAudit.Runtime`, with precompiled references `0Harmony.dll`, `VRCSDKBase(-Editor).dll`, `VRCSDK3A.dll`, `System.Collections.Immutable.dll`; `versionDefines` exactly match MA `[1.18.1]` / AAO `[1.9.16]`. GestureManager and most of the SDK go through reflection; if missing it degrades and writes that into the output (see [Deliverables list](docs/deliverables.md)).
- **Python 3**: `t5_shapekey_matrix.py`, `menu_expect_check.py`, `dual_root_diff.py` use only the standard library; `perception/` needs **PyYAML** (`unity_yaml.py`, `decl_draft.py`, `decl_validate.py`), `jsonschema` is optional (without it the schema layer reports skipped), and `key_class_blender.py` runs only inside Blender (`bpy` + `numpy`).

## Quick start

```bash
# 1) Deploy to the project (look at the plan first; after syncing, refresh in Unity, Console 0 errors)
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>" --dry-run
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>"
# 2) Write <工程>/Library/AvatarAudit/request.json, and in Play mode click the menu Tools/AvatarAudit/Run Request
#    (request format see docs/state-driver-request.md; progress and results in status.json in the request's out directory)
# 3) Generate a toggle sweep request from T4 params.json, then after T1 finishes analyze the blend shape dependency matrix
python3 开发工具/通用工具/审查/t5_shapekey_matrix.py sweep --params <t4>/params.json --slots <run>/slots.json ...
python3 开发工具/通用工具/审查/t5_shapekey_matrix.py analyze --t1 <run>/sweep --sweep <run>/sweep/t1_request_sweep.json ...
# 4) Before delivery: compare menu promises ↔ post-build measurements item by item
python3 开发工具/通用工具/审查/menu_expect_check.py check --delivery --expect 期望.json --t1 <T1 输出目录> ...
# 5) Before delivery, strip the audit code
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>" --strip
```

Parameter details in [Deploy](docs/deploy.md), [T5](docs/shapekey-matrix.md), [Menu assertions](docs/menu-expect.md).

## Documentation directory

Each page's header states its "former name" and the § number in the original README; `§x.y` in body text still refers to the original numbering; look up the page in the table below. Codes: T1 = state driver, T2 = fit probe, T3 = turntable renders, T4 = menu export, T5 = blend shape dependency matrix, W5 = compiled-state menu assertions, T-05 = part inventory, T-12 = build-time interception, T-30 = PhysBone static inventory.

| Page | Original section |
|---|---|
| **Overview and deployment** | |
| [Deliverables list and machine verification done](docs/deliverables.md) | §0 / §0.1 / §0.2 |
| [Deployment (sync_audit.py) and invocation](docs/deploy.md) | §1 / §2 |
| **T1 state driver `AuditStateDriver` (original README §3–§4)** | |
| [Request format](docs/state-driver-request.md) | §3 |
| [What each state does, sanity checks, volatile blend shapes](docs/state-driver-steps.md) | §3 "What each state does" / §3.0 / §3.0.1 |
| [Callback isolation, avatar resolution, GestureManager takeover](docs/state-driver-isolation.md) | §3.0.2 / "Avatar resolution rules" / "GestureManager takeover" / §3.1 |
| [reset mode and toggle residue test](docs/state-driver-reset.md) | §3.0.3 |
| [Version stamps, state readback assertions, level slot numbers, sentinels, sequence/history](docs/state-driver-readback.md) | §3.3 (in the original it came after §3.2.8 without its own heading; §2 cites it as "§3.3") |
| [`state_<id>.json`](docs/state-driver-output.md) | §4 |
| [states.json summary](docs/state-driver-states-json.md) | §4 "states.json" first part |
| [states.json field conventions](docs/state-driver-states-fields.md) | §4 "states.json" second part |
| **T1 pure-data probes `AuditProbes` (original §3.2–§3.4)** | |
| [T1 pure-data probe overview · grab_chain / coincident](docs/probes.md) | §3.2 / §3.2.1 / §3.2.2 |
| [Probe containment (containment ratio)](docs/probe-containment.md) | §3.2.3 first half |
| [Probe containment hit-count conventions · probe range](docs/probe-containment-crossing.md) | §3.2.3 second half / §3.2.4 |
| [Probe poke (static poke-through patches) · criteria, request and output](docs/probe-poke.md) | §3.2.5 first part |
| [Probe poke · hit count and area threshold conventions, Unity acceptance](docs/probe-poke-area.md) | §3.2.5 second part (including "Claude·Unity·Play acceptance") |
| [Probe poke · diag diagnostics and shell/normal fixes](docs/probe-poke-diag.md) | §3.2.5.1 |
| [Probe poke · two hard blocks behind false negatives and area convention review](docs/probe-poke-false-negative.md) | §3.2.5.2 / "Task CX review" |
| [Project A regression acceptance conventions](docs/regression-project-a.md) | §3.2.6 |
| [Probe delete_coverage (MA ShapeChanger delete-region coverage)](docs/probe-delete-coverage.md) | §3.2.7 |
| [Probe shrink_cover (shrink key occlusion consistency) · request and parameters](docs/probe-shrink-cover.md) | §3.2.8 first part |
| [Probe shrink_cover · criterion revision log (CU / CX / CT)](docs/probe-shrink-cover-rule.md) | §3.2.8 middle part |
| [Probe shrink_cover · output, diagnostics, self-check and calibration](docs/probe-shrink-cover-output.md) | §3.2.8 last part |
| [R9 foot/shoe selection candidates · request, execution and output](docs/foot-shoe-candidates.md) | §3.4 first part |
| [R9 foot/shoe selection · new fields (CS / D2 / CW)](docs/foot-shoe-candidates-fields.md) | §3.4 middle part |
| [R9 foot/shoe selection · lessons, insole surface conventions and acceptance](docs/foot-shoe-candidates-metrics.md) | §3.4 last part |
| **T3 turntable renders `AuditTurntable` (original §5–§6)** | |
| [T3 turntable renders · request and output](docs/turntable.md) | §5 / §6 |
| [Transparency sorting criterion](docs/turntable-transparency.md) | §6 "Transparency sorting criterion" |
| **T1/T3 self-checks and limitations (original §7–§10)** | |
| [Self-check 1 · sources of GM / SDK symbols used via reflection](docs/selfcheck-symbols.md) | §7 |
| [Self-check 2 · temporary change → restore table; self-check 3 · compile time](docs/selfcheck-restore.md) | §8 / §9 / §9.1 |
| [Self-check 3 · runtime points to verify (1–17)](docs/selfcheck-runtime.md) | §9.2 first half |
| [Self-check 3 · runtime points to verify (18–22) and what was explicitly not verified](docs/selfcheck-runtime-2.md) | §9.2 second half / §9.3 |
| [T1/T3 known limitations](docs/known-limits.md) | §10 |
| **Other Unity-side tools (original §11–§14)** | |
| [Scope and conventions](docs/part-inventory.md) | §11 / §11.1 |
| [Output skeleton](docs/part-inventory-output.md) | §11.2 |
| [Same-name key following key_follow and known limitations](docs/part-inventory-key-follow.md) | §11.3 / §11.4 |
| [Principles and output](docs/build-capture.md) | §12 / §12.1–12.3.1 |
| [Criteria, deployment, request and acceptance](docs/build-capture-verify.md) | §12.4–12.8 |
| [Request sequence](docs/sequence.md) | §13 / §13.1 / §13.2 |
| [Request sequence · samples, acceptance and limitations](docs/sequence-example.md) | §13.3–13.5 |
| [Single-button dialog suppression AuditDialogGuard](docs/dialog-guard.md) | §14 |
| **T2 fit probe `AuditFitProbe` (former name T2, originally `README_T2.md`)** | |
| [Deployment, dispatch, request](docs/fit-probe.md) | Page header / §1–§3 |
| [Algorithm and criteria (1–6)](docs/fit-probe-algorithm.md) | §4 first half |
| [Algorithm and criteria (7–10), v2 exclusions and rejections](docs/fit-probe-algorithm-2.md) | §4 second half / §4.5 |
| [v3 coverage, output, performance](docs/fit-probe-scope-output.md) | §4.6 / §5 / §6 |
| [Self-check 1: API signatures](docs/fit-probe-selfcheck-api.md) | §7 |
| [Self-check 2/3: restore table, runtime self-checks A/B](docs/fit-probe-selfcheck.md) | §8 / §9 / self-check A / self-check B |
| [Self-check C and v3 regression checklist](docs/fit-probe-selfcheck-2.md) | Self-check C / §9.5 |
| [Known limitations and first-run checks](docs/fit-probe-limits.md) | §10 |
| **T4 menu export `AuditMenuDump` (former name T4, originally `README_T4.md`)** | |
| [Deployment, request, behavior](docs/menu-dump.md) | Page header / §1–§4 |
| [Output fields](docs/menu-dump-output.md) | §5 |
| [Self-check and known limitations](docs/menu-dump-selfcheck.md) | §6–§8 |
| **T5 blend shape dependency matrix (former name T5, originally `README_T5.md`)** | |
| [Pipeline and subcommands](docs/shapekey-matrix.md) | Page header / §1–§4 |
| [analyze, classification and candidate criteria](docs/shapekey-matrix-analyze.md) | §5–§7 |
| [Self-check, limitations, encoding](docs/shapekey-matrix-selfcheck.md) | §8–§10 |
| **Compiled-state menu assertions (former name W5, originally `README_menu_expect.md`)** | |
| [Modes, pipeline, expectation file](docs/menu-expect.md) | Page header / §0–§2 |
| [Value conversion, coverage, matching, exit codes, report](docs/menu-expect-rules.md) | §2.1–§3 |
| [Samples, self-tests and limitations](docs/menu-expect-samples.md) | §4 / §5 |
| **PhysBone static inventory (former name T-30, originally `README_T30.md`)** | |
| [PhysBone static inventory pb_static.py and U7](docs/physbone-static.md) | Full text |
