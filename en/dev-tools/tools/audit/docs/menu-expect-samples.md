> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/menu-expect-samples.md)

# Compiled-state menu assertions · samples, self-test, and limitations <!-- nav -->

> Former name: W5 (originally `审查/README_menu_expect.md`) §4 / §5. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Compiled-state menu assertions · value conversion, coverage, matching, exit codes, report](menu-expect-rules.md) <!-- nav -->

## 4. Samples and self-test

### 4.1 Real existing research sample (Project A)

- Expectation: `_长程任务_20260918/派工/tmp/w5/期望_工程A_样例.json` (6 entries, each citation written in `note`)
- T1: `_长程任务_20260918/审查产出/工程A/seq_CL_verify_v3` (4 states)
- T4: `…/seq_CL_verify_v3/09_t4_menu/params.json`

```bash
python3 开发工具/通用工具/审查/menu_expect_check.py check \
  --expect _长程任务_20260918/派工/tmp/w5/期望_工程A_样例.json \
  --t1     _长程任务_20260918/审查产出/工程A/seq_CL_verify_v3 \
  --params _长程任务_20260918/审查产出/工程A/seq_CL_verify_v3/09_t4_menu/params.json \
  --out    _长程任务_20260918/派工/tmp/w5/报告_工程A_样例.md
```

Actual research-mode result: **29 comparison rows / 1 business failure / 2 missing / 280 uncovered steps/states (across 93 menu parameters)**, exit code 1.

- Business failure: in `MMN档 高跟鞋开` (MMN step, high heels on), `Body_b:Foot_heel_OFF*` expected 0, measured **100**. The high-heel pose key
  `Foot_Hiheel=100` and the flat-sole pose key `Foot_heel_OFF=100` are both on at the same time — exactly what SOP 50 explicitly forbids:
  "two pose keys both at 100 in the same state". This is a **real inconsistency reported truthfully**; the expectation was not changed to scrape a PASS.
- 2 missing (`原装档`, the original-outfit step): the sample T1 never scanned them; a request was produced with `gen-request`, **pending an actual post-build run**.
- Uncovered: counted per step / per state under the new basis. The old sample only wrote the middle two steps of `A2_Outfit` and 0/1 of `A2_HoleHeel`;
  the other 92 menu parameters had not a single step tested — the report truthfully marks this as a partial result, **not falsely claiming completeness**. The old sample's `A2_Outfit`
  has no `radial_labels`, so research mode infers 0/1 from boundaries, and it too lands in the uncovered list (this is exactly "parameter-name coverage ≠ behavior coverage").

Delivery mode on the same sample: `check --delivery …` → exit code **2 (check failure)**: 27 continuous parameters such as `A2_Outfit`
have no explicit `coverage` convention, and under "continuous axes are not guessed" are judged coverage-undeterminable (plus business failures / missing / 223 uncovered steps/states).
The conclusion is "not passed (check failure)". **The criteria were not relaxed to make the old sample pass**, nor was a step-count convention fabricated for it.

### 4.2 Offline self-test

```bash
python3 开发工具/通用工具/审查/menu_expect_check_selftest.py
```

Covers: rejection of zero assertions (all modes); Bool with only the on state (research records / delivery fails); toggle with both states passes;
Int and radial multi-step missing one step fails; missing params, **duplicate params**, ambiguous match, wrong value, unknown parameter,
**coverage declaration parse errors (`gears:"oops"`, fractional gears, mixed-in illegal values, NaN/Infinity, unknown field/parameter)**,
continuous parameter in delivery without explicit convention, `coverage` missing citation, coverage undeterminable, and empty check result are all non-zero;
**only an explicit continuous boundary/gears convention + citation can pass**; **boundary values are kept unrewritten** (to test 0.25, send 0.25);
`slot:` normalization is consistent with `gen-request`; the real existing research sample keeps its expected diagnosis.
All are synthetic offline samples; no project tests are run and Unity is not opened.

---

## 5. Limitations (explicitly not done)

1. **Discrete coverage ≠ all combinations**: this tool only compares, one by one, the discrete states and blend shapes named in the expectation; it does not do parameter combinatorial explosion or
   analysis of interactions between parameters; it cannot be used to claim "all combinations tested". The pass heading also only says "convention coverage".
2. **T1 is the post-editor-build basis, not the in-game one**: T1 runs the NDMF/VRCFury-built controller in Unity Play
   (GestureManager can be added temporarily), but the VRChat client's parameter compression, remote sync, SDK upload chain, and the
   final form from other people's view may not fully match the editor. **A PASS only proves "consistent after the editor build"**; for the real-device basis see
   `90_交付打包/上传后自测清单.md`.
3. **Remote quantization / blend-shape dependency matrix: see T5**: fine radial sweeps into steps, blend-shape dependency matrix, shrink-key residue, and other
   "continuous interval / writer relationship" problems use `t5_shapekey_matrix.py` (`README_T5.md`).
4. **Limited sources for step counts**: `radial_labels` is the list T4 gets by merging the labels of multiple Radial controls for the same parameter,
   and its count does not necessarily equal the real step count; `radial_label_derived` is T4's estimate. **Delivery mode does not use these as the basis for step counts**;
   continuous parameters must be explicitly declared in `coverage` with a citation (human-reviewed); only research mode may infer and annotate. **No guessing**.
5. **Convention citations are not checked for authenticity**: it only checks whether `source`/`note` (including `coverage`'s note/source) are non-empty and
   not placeholders; it does **not** verify that the cited file/line actually states the convention. Authenticity of citations is the expectation author's responsibility.
6. **Assertions are not bound to each covered parameter individually**: a step having a state with assertions does not mean the assertions target that parameter's effect;
   coverage only guarantees "that step was set by some expected state that has assertions". Hence the pass heading only says "convention coverage", not "deliverable".
7. **Name matching relies on wildcards and T5 restoration rules**; with cross-language naming (parameter called Coat, object called outer), the expectation author must use
   paths/leaf names that line up; a failed match is explicitly recorded as FAIL, never silently let through.
8. **Visibility only looks at `renderers[].visible`** (`activeInHierarchy && enabled`), not material transparency
   (T1's `visibility` has V3/V4, which this tool doesn't use); "semi-transparent but enabled" is judged visible.
9. This tool **does not judge design intent** (which key should follow which, how many steps there should be); it only puts "what the expectation says" and "what the measurement read"
   side by side; correctness is the responsibility of the expectation's source (delivery notes / SOP). Duplicate names / list conflicts in `params.json` are only reported as "structurally invalid",
   which does not mean it has judged which entry is correct.
