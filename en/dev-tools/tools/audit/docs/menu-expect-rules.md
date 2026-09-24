> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/menu-expect-rules.md)

# Compiled-state menu assertions · value conversion, coverage, matching, exit codes, report <!-- nav -->

> Former name: W5 (originally `审查/README_menu_expect.md`) §2.1–§3. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Compiled-state menu assertions menu_expect_check.py · modes, pipeline, expectation file](menu-expect.md) · Next page: [Compiled-state menu assertions · samples, self-test, and limitations](menu-expect-samples.md) <!-- nav -->

### 2.1 How `set` values are converted (same logic for `gen-request` and `check`)

| Type (`value_type_name` in `params.json`) | Rule |
|---|---|
| `Bool` | Only accepts `0/1/true/false` → written as `0/1` in the request. |
| `Int` | Only accepts integers. |
| `Float` (`radial` / axis / plain) | **Numeric values are passed through unchanged, with no snapping and no rewriting to step midpoints** (to test 0.25, send 0.25; it won't quietly become 0.375 and then claim a pass); `suggested_values` is only used to validate the range. |
| Explicit slot number (any `Float`) | Only the string `"slot:3"` is recognized: the step count comes from top-level `coverage[参数].gears` (must be explicit in delivery mode; research mode may fall back to the `radial_labels` count), converted to the representative value of step 3, `(3+0.5)/N`. **Integers 0/1 are endpoint values, not slot numbers**; an integer ≥2 that falls within the step-number range but outside the continuous interval raises an explicit error suggesting `slot:` instead, and is not rewritten automatically. |

- `check` and `gen-request` use **the same** `resolve_value` and **the same effective convention**:
  `slot:3` is converted to the same representative value, so it won't be misjudged as "missing" just because T1 stores the converted number;
  non-slot values are never rewritten to make up coverage.
- Parameter name not in `params.json`: **delivery mode = input error (exit 2)**; research mode degrades to a warning and matches on the raw value.
- Illegal value (Bool given `maybe`, Int given `1.5`, Float given `true/on/NaN/Infinity` or out of range): exit 2 in both modes.
- Parameter exists but `declared_in_expression=false` → reminder only (T1 may not be able to set it), not blocking.

### 2.2 How coverage is built (delivery mode: discrete by evidence, continuous must be explicitly declared)

For every "menu parameter" in `params.json` (`menu_value_kinds` or `referenced_by` non-empty), coverage is required item by item over the reachable steps:

| Parameter type | Required test units | Source |
|---|---|---|
| `Bool` | Both states `0` and `1` | Both toggle states (discrete, evidence-backed) |
| `menu_values` non-empty (except `Bool`, always 0/1) | Every real discrete value; if the same parameter is also referenced by radial/axis, a continuous coverage convention is also needed, accepted as the union | A button's values can't substitute for radial/axis coverage of the same parameter |
| `Int` (`menu_values` empty) | Delivery: must be explicitly declared in `coverage`; research: fall back to `suggested_values` and annotate | T4 suggested values |
| `Float` + `radial` (with/without `radial_labels`) | Delivery: `coverage` explicitly declares `gears`/`units`/`boundaries` + citation; research: infer from the `radial_labels` count or 0/1 boundaries | **Human-reviewed convention** (`radial_labels` is only control label names and does not guarantee the real step count) |
| `Float` + `axis2`/`axis4` | Delivery: explicitly declared in `coverage`; research: infer `-1/0/1` boundaries | **Human-reviewed convention** |
| Plain `Float` | Delivery: explicitly declared in `coverage`; research: infer `0/1` boundaries | **Human-reviewed convention** |
| Neither schema nor declaration can determine it | —— | `无法确定覆盖` (coverage undeterminable) → exit 2 in delivery mode |

- `coverage` declaration rules (strict):
  - Array form `[0, 0.5, 1]`: **research mode only** (no citation).
  - Object form `{"gears": 7, "note": "档位表：…:14"}`: `gears` must be an **integer ≥2** (fractions/strings/booleans all error;
    no `int()` truncation); `units`/`boundaries` must be non-empty arrays of finite numbers only (mixing in `true`/`NaN`/`Infinity`/
    illegal strings errors, **no silent filtering**); unknown fields, unknown parameter names, multiple conventions, and missing `note`/`source` in delivery mode all error.
  - **A bad convention does not fall back to a lenient default**: a parse failure means exit 2; it will not fall back to endpoint boundaries.
- Coverage only looks at the normalized values of the expected `set`, and is **counted separately** from whether T1 found that state ("missing" is counted separately),
  so the two kinds of failure don't mask each other.
- Coverage is still built "one discrete state at a time": **it does not represent all parameter combinations**, nor interactions between parameters.

### 2.3 How measurements are matched (`check`)

- **State matching**: the expected `set` (after normalization) is a **subset** of T1's `params_applied` (numbers compared at `1e-4`);
  when multiple match, research mode takes the one "with the fewest extra parameters written" and lists the ambiguity count, **delivery mode judges it a check failure (exit 2)**.
  `t1_state` can pin it.
- **Renderers**: candidates = `path` / `key` / leaf name / T5 restored name from the snapshot (path segment `名$原物体$编号` → `原物体`).
  When a pattern contains `/`, it matches the whole path; when it doesn't, it also matches any single segment. `visible` requires every hit to be visible,
  `hidden` requires every hit to be invisible; **no hits at all counts as FAIL** (the part doesn't exist).
- **Blend shapes**: `keys_all` (full set) + `blendshapes` (non-zero) merged and deduplicated; key names are matched both by the original name and by the T5 restored name
  (`AAO_Merged_<原名>_<n>` → `<原名>`). When multiple match, all values must equal the expectation (`1e-4`).

### 2.4 Exit codes and the four result categories

| Code | Meaning |
|---|---|
| `0` | All expected states found and every comparison PASSes; delivery mode additionally requires no coverage gaps |
| `1` | **Business failure** (comparison mismatch) / **missing** (state not found in T1) / **uncovered** (missing step/state) |
| `2` | **Check failure**: invalid input / duplicate names or list conflict in `params.json` / `coverage` declaration parse error / missing delivery prerequisite / empty check result / ambiguous match / coverage undeterminable |

The report records the four categories separately: `业务失败` (business failure), `缺失` (missing), `未覆盖` (uncovered), `检查失败` (check failure) (plus `无法确定覆盖` (coverage undeterminable) and `歧义匹配` (ambiguous match)).
**Check failures do not enter normal diff judgment**. In research mode, "uncovered / undeterminable / ambiguous" are only recorded and don't affect the exit code;
in delivery mode they are all non-zero; `coverage` parse errors and `params.json` input errors are **non-zero in both modes**.

---

## 3. What the report looks like

`--out 报告.md` is the human-readable version; `--json 报告.json` is the structured version. Markdown sections:

1. **Summary**: mode, count table of the four categories, exit code, conclusion (in delivery mode, when passing it writes "menu behavior assertions passed (convention coverage)",
   on failure "not passed"; in research mode "partially passed / partially not passed");
2. **Check failures**: input / prerequisite / undeterminable items listed one by one;
3. **Line-by-line comparison**: `状态 | 项 | 期望 | 实测 | PASS/FAIL`;
4. **States not found in T1 (missing)**: listed together with their `note` citations;
5. **Matched multiple T1 states (ambiguous)**;
6. **Coverage**: per parameter, lists uncovered steps/states, reasons coverage could not be determined, and the number of fully covered parameters;
7. **Limitations**: what is explicitly not proven (all combinations, in-game, transparency, authenticity of citations, etc.).

The JSON keeps the old fields (`rows` / `per_state` / `not_found_states` / `uncovered_menu_params` /
`fail_row_count` / `not_found_count` / `exit_code`), and adds:
`mode`, `business_fail_count`, `missing_count`, `uncovered_count`, `undetermined_count`,
`ambiguous_count`, `check_failure_count`, `check_failures`, `uncovered_units`,
`undetermined_coverage`, `coverage_requirements`, `warnings`, `limitations`.

---
