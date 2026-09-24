> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/menu-expect.md)

# Compiled-state menu assertions menu_expect_check.py · modes, pipeline, expectation file <!-- nav -->

> Former name: W5 (originally `审查/README_menu_expect.md`) page header / §0–§2. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Next page: [Compiled-state menu assertions · value conversion, coverage, matching, exit codes, report](menu-expect-rules.md) <!-- nav -->

# W5 · Compiled-state menu assertions `menu_expect_check.py` — expectation format, two modes, and coverage basis

> Goal: **mechanically compare** "the menu behavior promised in the delivery notes" against "the state scan measured after the build (after NDMF/VRCFury)",
> and output PASS/FAIL line by line. Expectations are written from a **second perspective** (delivery notes / menu notes), measurements come from the post-build T1 scan,
> and the comparison is done by the script — replacing "self-verifying your own assumptions inside the development-state project".
> This tool is a **pure Python 3 standard library** script: it doesn't start Unity, doesn't call MCP, doesn't touch the project; it only reads inputs and only writes `--out`.
> Design basis: dispatch `W5_编译态菜单断言工具.md`, `P02_交付菜单验收.md`; samples in
> `_长程任务_20260918/派工/tmp/w5/`.
> Tools it depends on: T4 `AuditMenuDump` (exports `params.json`), T1 `AuditStateDriver` (post-build state scan).

---

## 0. Two modes (read this first)

| | Research mode (default) | Delivery mode (`--delivery`) |
|---|---|---|
| Purpose | Spot checks, troubleshooting, figuring out mechanisms | Pre-delivery gate, **must not let things through by mistake** |
| `--params` | Optional | **Required**, otherwise exit 2 |
| `source` and each `note` citation | Not enforced | **Enforced** non-empty and not a placeholder, otherwise exit 2 |
| State with `visible/hidden/shapes` all empty | Rejected (exit 2) | Rejected (exit 2) |
| `Bool` both states / each `Int` `menu_values` | Recorded only, not blocked | **Enforced**; missing any one step fails (exit 1) |
| Continuous `Float`/`radial`/axis coverage | Allowed to **infer** from `radial_labels`/boundaries and record it | **Must** explicitly declare `gears`/`units`/`boundaries` in top-level `coverage` with a `note`/`source` citation; otherwise exit 2 |
| `coverage` declaration parse error | **exit 2** (input error; no silent filtering/truncation) | **exit 2** |
| Duplicate parameter names / list conflicts in `params.json` | **exit 2** | **exit 2** |
| Schema can't determine steps and nothing is declared | Recorded | **exit 2 (check failure)** |
| Same `set` matches multiple T1 states | Take the one with the fewest parameters and record the ambiguity count | **exit 2 (cannot be uniquely determined)** |
| Check result is empty (no assertion rows at all) | Treated as missing → exit 1 | **exit 2** |
| Meaning of exit code 0 | All states written this time passed (does not mean complete) | Every step/toggle/boundary covered per the explicit convention in the expectation passed (still does not mean all combinations / in-game) |

**Common baseline**: a state whose `set` only names parameters and writes no behavior assertion is rejected in every mode.
Parameter-name coverage ≠ behavior coverage: testing `Coat` only at `=1` does not count as covering that toggle.
**Continuous axes are not guessed**: `radial_labels` is only "the label names of the Radial controls that reference the parameter" (T4 merges multiple
controls for the same parameter), and does not guarantee the real number of steps; delivery mode requires a human to write out the step count / boundary convention and its source; only research mode is allowed to infer and annotate.

---

## 1. Deliverables and pipeline

| File | Role |
|---|---|
| `开发工具/通用工具/审查/menu_expect_check.py` | This tool (the only code file) |
| `README_menu_expect.md` | This page |
| `menu_expect_check_selftest.py` | Offline standalone self-test (synthetic positive/negative cases + real existing research sample), no Unity |

```bash
T=开发工具/通用工具/审查/menu_expect_check.py

# ① Before delivery: write the expectation .json from the delivery notes (by a human/Claude, each entry with a note citation line)
# ② Expectation → T1 request (validates parameter names and values; slot:N computes the representative value per the explicit convention, numeric values passed through unchanged)
python3 $T gen-request --delivery --expect 期望.json \
        --params <工程>/t4_menu/params.json --out t1_request.json
#    → Claude copies t1_request.json to <工程>/Library/AvatarAudit/request.json,
#      and triggers Tools/AvatarAudit/Run Request in Play (after the build)
# ③ Post-build measurement → line-by-line comparison (delivery gate)
python3 $T check --delivery --expect 期望.json --t1 <T1 输出目录> \
        --params <工程>/t4_menu/params.json --out 报告.md --json 报告.json

# Self-test (purely offline; no Unity, no project tests)
python3 开发工具/通用工具/审查/menu_expect_check_selftest.py
```

- `check` reads T1 output: a directory (recursively finds `state_*.json`), a single `state_*.json`, or `states.json` all work.
- For T1/T4 deployment and request fields see `README.md`; for `params.json` fields see `README_T4.md`.
- This tool does not copy any files into the project; moving `request.json` is up to the caller.

---

## 2. Expectation file `期望.json`

```json
{
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "source": "工程A/_交付/原根_A21实测报告.md:62-69",
  "coverage": {"A2_Outfit": {"gears": 7, "note": "档位表：原根_A21b补证.md:14"}},
  "states": [
    {
      "name": "MMN档 高跟鞋开",
      "set": {"A2_Outfit": "slot:1", "A2_HoleHeel": 1},
      "visible": ["HoleHeel.main", "HoleHeel.belt"],
      "hidden": ["*Outfit_MMN_黑*/Shoes", "kaguya_cloth/loafer"],
      "shapes": {"Body_b:Foot_Hiheel*": 100, "Body_b:Foot_heel_OFF*": 0},
      "note": "HoleHeel 开 → 显示高跟、隐藏整套鞋靴、Foot_Hiheel=100：菜单生成报告.md:94"
    }
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `avatar` | Yes (or `gen-request --avatar`) | Avatar root name, written into the T1 request's `avatar`. |
| `source` | Recommended; required in delivery mode | Source of the expectation (delivery notes / menu notes path and line numbers), written into the report header. |
| `coverage` | No | Coverage convention: `{参数名: 数组 \| {gears:N} \| {units:[...]} \| {boundaries:[...]}}`. Continuous `Float`/`radial`/axes **must** be explicitly declared **in delivery mode** (object form + `note`/`source` citation); the array form has no citation and is only usable in research mode. A declaration can only **tighten** the known steps; **it cannot be used to downgrade a Bool to testing only one state**. Parse errors (unknown field/parameter, fractional gears, NaN/Infinity, mixed-in illegal values) all exit 2. |
| `states[].name` | Yes | Expected state name, used to locate it in the report; **must not repeat within the same file**. |
| `states[].set` | Yes | `{参数名: 值}`; when comparing, matched as a **subset** of the T1 state's `params_applied`. |
| `states[].visible` | No | Renderers that should be visible; path / unique leaf name / `*` wildcard. |
| `states[].hidden` | No | Renderers that should not be visible; same syntax as above. |
| `states[].shapes` | No | `{"<网格>:<键名>": 期望值}`; both mesh and key name may contain `*`. |
| `states[].t1_state` | No | Optional; pins the match to a specific T1 `id` (used when the same `set` has multiple candidates). |
| `states[].note` | Recommended; required in delivery mode | Citation line; `check` lists it verbatim in the missing/coverage lists. |

> **Hard rule**: at least one of each state's `visible`/`hidden`/`shapes` must be non-empty, otherwise exit 2.
> A state that only writes `set` proves no behavior at all.
