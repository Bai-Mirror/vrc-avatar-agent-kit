> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/DSH模型与视觉能力.md)

> ← [DSH dispatch](dsh-delegation.md)

# DSH Models, Pricing and Vision Capability Boundaries

The problem this page solves: **which model to dispatch to, whether tasks with images can be dispatched, and how much it costs**.

## 1. Model aliases (current; the `MODELS` table in `通用工具/dsh_task.js` is authoritative)

From 2026-09-11 DeepSeek has only **one** model left: **DeepSeek-V4.1-Flash** (supports image understanding, 1M context, max output 384K, concurrency 2500).
All three aliases in the table below are it underneath, all billed at Flash prices; the only difference is **which name the DSH harness declares image input for**.

| `--model` alias | Actual model id | When to use |
|---|---|---|
| **`flash` (default)** | `deepseek-flash` | **Plain-text tasks** |
| **`vision`** | `deepseek-v4-flash-vision-exp` | **Tasks with images must use it**; `--images` only allows this alias (`VISION_CAPABLE`) |
| `v41` | `deepseek-flash` | Only for compatibility with old command lines |
| ⛔ ~~`pro`~~ | ~~`deepseek-v4-pro`~~ | **Banned, see below** |

**Why `flash` cannot be used with images**: passing images to `deepseek-flash` is hard-rejected with
`model "deepseek-flash" does not declare image input` — not because the model cannot (the official “Model details” says image understanding = supported),
but because the harness's capability declaration does not add image input for this name. The **name** `deepseek-v4-flash-vision-exp` is an alias left over after the old model was retired;
the original model is gone and requests are served by V4.1-Flash, but it declares image input in the harness — it is kept **only for this one declaration**.
**Lesson**: “the same model” does not mean “the same capability declaration”; capabilities must be measured per **alias**, not inferred per model; and do not infer the model from the behavior of an expired alias (see the change log at the end).

⇒ **Plain text: `--model flash` (the default); with images always `--model vision`.** Other old names (`deepseek-v4-flash` etc.) can still be called, but do not write them any more.
During Beijing weekday peak hours `--engine auto` redirects to Codex, and flash/vision task briefs land on the `luna` tier → [Codex dispatch](codex-delegation.md).

**This was caught by the gate saving the day** (09-11): in a three-route design review, two routes wrote 18KB proposals **without having seen the images**;
without the gate that “looks up isError of `tool/result`”, they would have been taken as normal conclusions and entered the summary (→ [DSH silent failures](dsh-silent-failure.md) ⑤).

### ⛔⛔ Pro is hard-banned; only the author can lift the ban

**The author explicitly ordered on 2026-09-11: “Using Pro is now absolutely not allowed, unless I lift the ban later.”**
This is not a preference of “generally don't use”; it is a **red line**. “This task seems better suited to pro” is not a reason.

The block has four layers (all measured):
1. The `BANNED` alias table in `dsh_task.js` — `--model pro` exits immediately;
2. The `BANNED_ID` regex — also blocks alias-bypassing forms like `--model deepseek-v4-pro` and `DEEPSEEK-V4-PRO`;
3. **After-the-fact verification** — if the real model in the session log hits Pro, it is always judged FAIL.
   This layer cannot be dropped: **switching models in DSH's web UI writes `agent-default-model` back into
   `~/.dsh/settings.yaml`**, and that layer takes priority over this script's `--patch`;
   “blocked at dispatch” ≠ “did not actually run pro”.
4. `allowedModels` in `~/.dsh/settings.yaml` now contains only `deepseek-flash`.

Incidental facts (not the reason for the ban; the reason is the author's decision): Pro does not support image understanding, has concurrency of only 500,
costs 4.5× as much, and after 09-14 12:00 its requests are also routed to V4.1-Flash.

## 2. Vision capability boundaries (measured 2026-09-08, synthetic images with ground truth + real renders)

⚠ The table below was measured on 2026-09-08 on the **old model** `deepseek-v4-flash-vision-exp`.
That model was retired from 09-11 and requests are served by `deepseek-flash` (V4.1-Flash) — **these capability boundaries have not been re-measured on the new model**; treat them as reference, not conclusions.
In that version: **visual input was constantly compressed to 315–396 tokens** —
a 1.5MP render and a 5KB synthetic image cost the same number of tokens, so the precision ceiling is structural; **feeding larger images does not solve it**.

| Capability | Measured | Can it be dispatched |
|---|---|---|
| Small-text OCR (from 10px), Chinese labels, hex printed on the image | All correct | ✅ Reliable |
| Structural semantics (how many panels, which is marked default) | All correct | ✅ Reliable |
| Relative size comparison (5.8% difference) | Correct | ✅ Reliable |
| Color ordering (which is more saturated) | Correct | ✅ Reliable |
| Presence of a local gap | 1px judged absent, 2px judged present (2/2 stable) | ⚠ Threshold ≈ 0.14% of frame |
| Precise color picking | Max single-channel deviation 10/255 (4%) | ❌ Can only determine the color family |
| Precise counting | 23 → 24 | ❌ |
| Cross-region alignment | 6px (0.86% of frame) judged “perfectly aligned”, reproduced 2/2 | ❌ **Deterministic failure** |

**Why it can see a 0.14% gap but not a misalignment 6× larger**: a gap is a local high-contrast feature,
while alignment requires cross-region spatial registration — the visual budget is not enough for the latter. So criteria should be split by this, not by “how large the difference is”.

**Two directly usable rules**

1. **“Is there / is it / which is more X” → let it look at the image. “How much off / how many / is it aligned” → use geometric quantities.**

   Concrete entry points for “use geometric quantities” (not letting it look at images, but letting it **extract numbers**):
   - Blender: `mcp__Blender__execute_blender_code` running `bpy` to read vertices/bones/bounding boxes →
     vertex offsets and blend-shape measurement in [30/facial feature scaling geometry](../30-face-sculpt/facial-feature-scaling-geometry.md)
   - Unity: `mcp__UnityMCP__manage_gameobject` / `find_gameobjects` to read transforms,
     `mcp__UnityMCP__unity_reflect` to read component fields; ring-shaped part pose solving in [55/ring-part pose solving](../55-accessory-placement/ring-part-pose-solving.md)
   - Pure file level: `pwsh` / `read` to parse `.anim`, `.prefab`, `.mat` text directly — criteria must stick to the authoritative artifacts

2. **Print numbers onto the image for it to read; do not let it measure.** It reads hex characters printed on the image 100% accurately,
   but its own color perception is off by 4%. **Method**: after rendering, overlay text with Python + PIL
   (`ImageDraw.text`, following the existing comparison-image generation scripts in `通用工具/`), drawing the numbers to be judged
   (hex, mm, IDs, slot names) directly below the corresponding panel — this is how `_眼色三档对照.png` was made;
   measured, it read all three hex values correctly on the first try. The criterion thus goes from “unreliable” to “reliable”.

## 3. Pricing (official “Model details”, CNY per million tokens)

| | Cache-hit input | Cache-miss input | Output |
|---|---|---|---|
| flash · **off-peak** | 0.02 | 1 | 4 |
| flash · peak | 0.04 | 2 | 8 |
| pro · off-peak | 0.15 | 4.5 | 13.5 |
| pro · peak | 0.30 | 9.0 | 27.0 |

**Peak = Beijing time Monday–Friday 09:00-12:00, 14:00-18:00; everything else is off-peak at half price.**
⇒ Schedule bulk dispatches in off-peak hours whenever possible, directly saving half.

**Usage and cost statistics**: `node 开发工具/通用工具/dsh_usage.js [--since <ISO>] [--dir <过滤>] [--json]`
It takes numbers from `usage` events of `assistant/chunk` in session logs (only the last cumulative value per step),
priced by time period per the table above. **Calibrated against ground truth**: costs estimated from session logs match the backend bill, so they can be used as an estimation basis.

**How valuable caching is**: cache hits can push actual payment far below what pricing everything as cache misses would give —
**factor cache hits into cost estimates and model choice**; do not estimate as if everything missed.
So **don't fear long context; fear repeated ingestion** (this is exactly why `--brief` exists).

## Change log (overturned old conclusions, one line each, do not cite again)

- **09-11 morning** “Uniformly write only `deepseek-flash`; keeping old names makes people think they are different models” — holds for plain text; overturned the same day by the `--images` verification gate: images require `vision` (see section 1). The comment in `~/.dsh/settings.yaml` still has this old wording; this page prevails.
- **09-10** “v4.1 cannot read images” — void: it was the temporary alias `deepseek-v4.1-flash-expires-on-0910` not declaring image input; the same day's note that “v4.1 visual budget is 2.7×, alignment judgments become random” was also an alias-era observation and is voided as well.
- **09-08** The default model was once set to `deepseek-v4-flash-vision-exp` (at the time `deepseek-v4-flash` was a separate model that could not read images) — from 09-11 the models merged, the default went back to `flash`, and images are forced to `vision` by the `--images` gate.
