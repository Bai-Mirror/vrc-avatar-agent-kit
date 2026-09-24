> 🌐 English translation · [中文原文](../../../../开发工具/SOP/90_交付打包/编译态菜单断言.md)

> ← [90 · Delivery Packaging](../90-delivery-packaging.md)

# Compiled-State Menu Assertions (origin and tooling of step 3b, 2026-09-23)

**Why**: all four delivered orders are pending re-delivery (Project D: 6 items; Project E: chest shape not following and radial-menu slots; Project F: all 9 toggles in the vendor submenu ineffective — “the client clicks and nothing happens”; Project G: the full package missing 19 files). The defects are all at the “does it work” layer, not the “does it compile” layer; development-time self-checks only verify one's own assumptions — in H-07 round 2, DSH's self-check passed all 382 groups, yet an independent check still found 5 defects. So the delivery gate becomes three stages: **expectations written from a second perspective, measurements taken on the post-build output, comparison done by a script**.

**Tool**: `开发工具/通用工具/审查/menu_expect_check.py`: the delivery chain uses `gen-request --delivery` → post-build T1 → `check --delivery --params <T4/params.json>`. 0 means the in-contract menu assertions passed; 1 means business failure/missing/untested; 2 means the input, source format, matching or coverage contract is undecidable. A partial pass in research mode is not a delivery gate.

**Must have**: non-empty behavior assertions, an expectation source and a citation for every state; Bool toggles with both states, and all actual discrete values covered; continuous radials/axes must have an explicit `coverage` slot count or boundaries with a citation — do not guess the slot count from control labels. When one parameter has both a button and a radial, accept against the union of both coverages. Values are measured as-is; only an explicit `slot:N` is converted to the slot midpoint.

**Independent review**: a second perspective verifies that the citation really supports the operation and the assertion, and checks whether each parameter's assertions verify the effect it actually controls. The script does not check citation text, and cannot automatically detect irrelevant assertions such as “testing an outfit parameter but only asserting an always-on background”. Input anomalies, uncovered states, and unverified citations/meanings must never be treated as a delivery pass. Format: see [Audit: compiled-state menu assertions](../../tools/audit/docs/menu-expect.md) (formerly README_menu_expect.md).

**Trade-offs**
- A wrongly written expectation will judge a correct implementation as FAIL: so every expectation carries a citation line; on FAIL, check the expectation's citation first, then the implementation; never change the expectation to get a PASS — if you change an expectation, record “citation misread”.
- T1 is the post-editor-build measure, not equal to the in-game side (remote quantization, sync bits, other players' view): that layer is handed to the [Post-upload self-test checklist](post-upload-selftest-checklist.md) for the user to tick in-game.
- Cost: one extra T4 + T1 full-slot sweep per order (10–20 minutes batch) plus one agent call to write expectations; compared with the cost of re-delivering four orders, worth it.
