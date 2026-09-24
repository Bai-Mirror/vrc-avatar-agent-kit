> 🌐 English translation · [中文原文](../../../../开发工具/SOP/05_多模型评审规程/选对工具.md)

# 05 · Choosing the right review tool

> A subpage split out of [`05-multi-model-review.md`](../05-multi-model-review.md) (2026-09-20, the parent page exceeded 10 KB).
> The two sections are unchanged line for line: one is about not confusing two **scripts**, the other about not confusing two **MCP tools**.

## Two tools, don't confuse them: `agy_panel.py` and `agy-task.py`

| Tool | Where | What it does |
|---|---|---|
| `开发工具/通用工具/agy_panel.py` | In the project | **Concurrent multi-model review**, with consistency clustering, `--schema`/`--system`/`--raw` |
| **`~/bin/agy-task.py`** | **The user's own bin, not in the project** | **A single reliable subagent call**, wrapping all five pitfalls of agy headless mode |

The five pitfalls `agy-task.py` solves **are the same set listed in the `agy_panel.py` documentation**:
argv ~32KB limit (automatically switches to stream-json above the threshold) · stdin doesn't enter the context (inline via `--context`) ·
the workspace is not the shell CWD (mount explicitly with `--dir`) · `run_command` is refused in headless mode (automatically appends a read-only-tools guidance line) ·
failures take many forms (empty stdout / SUCCESS with empty reply are both retried; permission walls fail fast).

> **Found 2026-09-07**: I spent a whole night repeatedly warning about these five pitfalls in subagent task briefs,
> **while a ready-made wrapper had long been sitting in `~/bin/`** — it just wasn't in the project directory, so it never entered my field of view.
> **Lesson**: tools aren't only in `开发工具/通用工具/`. It's worth a glance at `~/bin/` when starting work.

**When to use which**:
- Need **multi-model cross-checking / consistency clustering / a custom schema** → `agy_panel.py`
- Need **one stable single-model call** (especially with a large prompt, a directory to mount, or risk of hitting permission walls) → `agy-task.py`
- **Since 09-22 `agy_panel.py` also retries once** (69895252): envelope `status=SUCCESS` but `denied_actions` non-empty (the model tried to call the terminal/MCP, was refused, then quit or idled to ≈185s); previously this was reported vaguely as "no structured_output parsed", sending people off to inspect the parser. Now it classifies the error and retries once with the prefix "attachments are inlined, do not call any tools"; the `--raw` json has `attempts`/`first_error`. Re-tested with 3 consecutive runs on the same image: both models returned results 3/3. **Checkable question**: which kind does the failure message say — "hit permission wall / suspected 185s limit / agy returned ERROR / nothing parsed"? Only the last one warrants looking at the parser.
- **Don't expect claude-opus-4-6 to produce results for multi-file text questions (attachments are .txt/.json/.cs excerpts, not images)** (09-22, 12 historical falsification questions): in agy_panel, 10/12 still hit the permission wall after retrying (it wants to run the terminal); re-running 7 of them with `agy-task.py --context`, 5 returned just an opening sentence and quit. Gemini 3.7 produced structured results on the same batch 12/12. **Trade-off**: for text questions, single-model Gemini falsification is sufficient (accepted under rule 1); only "overturn"-type conclusions are worth re-checking with another model — don't burn quota over and over just to get two models.
- **Stuffing 14 part renders into one batch makes gemini-3.7-flash mix things up** (09-22 Velour H-03 batch C, `开发工具/素材包说明/The Velour/_agy/H03_批C_*`): it judged the control claim "the socks are white" as true (sock cuff measured by pixel at RGB 84,84,84), and in the same batch called a glossy black short skirt pink velvet and said blue-and-white piping wasn't there; re-running the same prompt unchanged, the control passed but four verdicts V11–V14 flipped. In the same round claude-opus-4-6 returned `Individual quota reached` on all three batches (reset in about 74 h, still wasting ≈130 s each time). **Trigger moment**: more than 10 images in a batch, or several parts in the same batch with similar colors. **Checkable question**: did this batch's control pass? After one re-run, how many verdicts flipped? **Trade-off**: every batch must include a control with a known answer; if it fails, discard the whole batch rather than cherry-picking; with many images split into small batches (≤7 images), or at least re-run once and accept only verdicts consistent across both runs. Color and presence judgments are cheaper to check first with pixels (mean, saturation, presence/absence diff) than by burning another model round.

## For comparing/interpreting use `agy_ask`; `agy_review` only finds faults

**Trigger moment**: wanting a third-party model to answer "which of these options is better", "what color scheme is this image", "rank these along some dimension".

**Tripped on (2026-09-20 eye texture comparison, twice in the same round)**: I used `agy_review` to ask "① what's the main color of each ② which have pink and blue together ③ which is most lively",
and both times got back only **defect reports** — the first said my collage had "broken layout, inconsistent proportions", the second said "image 6 is not a pupil texture".
None of the questions were answered. Re-asking with `agy_ask` immediately got the per-image main colors, pattern lists and a liveliness ranking.

**The division of labor between the two tools** (it's written in the tools' own descriptions; I just didn't read them):

| Tool | What it does | Output form |
|---|---|---|
| `agy_review` | **Fault-finding**: quality review, picking out defects | findings list + a verdict on whether it can be delivered |
| `agy_ask` | **Non-defect**: interpretation, comparison, summarizing, weighing options | Free-text answer |

**Checkable question**: do I want "**is there a problem**" or "**which is better / what is this**"? The latter always goes to `agy_ask`.

**Trade-off**: `agy_review` is structured and easy to re-check item by item, but it forces "please compare" into "find defects",
and asking the wrong one doesn't raise an error — it just answers off-topic — **and when it answers off-topic it still gives a verdict, looking like a serious answer**.
Conversely `agy_ask` doesn't produce structured findings, so you have to extract conclusions from the text yourself.

**Incidentally**: those two "off-topic" `agy_review` answers still had **usable by-products** — it pointed out that my crop was of the wrong region (it cropped loose atlas parts instead of the iris).
**The locations a review model points to are more trustworthy than its conclusions**; the tool itself says so too — don't throw the whole thing away just because it answered off-topic.


## When sending for falsification, give renders of **all** candidate options at once (2026-09-21 Project B)

**Trigger moment**: you have N candidate presets (a few toggles on/off, several parameter combinations), but rendered only two of them before asking agy.

Example: three toggles for pupil and highlights 1/2; in the first round I rendered only the two columns "all on / all off" and asked.
Based on that it suggested "**keep one of highlight 1 or 2**" — sounds reasonable, but it had never seen what those two presets look like rendered.
After filling in all four columns (all on / all off / only highlight 1 / only highlight 2) and asking again, it found on its own:
① highlight 2 **has no effect at all** (consistent with my measurement "all off vs. only highlight 2 differs by only 706 px");
② the white patch of highlight 1 **sits right on top of the pink heart, covering 1/3–1/2 of it**, and showing the heart was exactly the core reason for switching to this texture;
so it tightened its suggestion to "only highlight 1 is an option, but it's not acceptable", and finally recommended going back to "all off".
In the same round it also **proactively overturned** its previous-round judgment that "all off at long distance makes the pupils look dilated and lifeless" — because this time it was given a long-distance shot.

**How to do it**:
- Render **every candidate you intend it to choose among**, same camera, same lighting, same materials, combined into one image.
- **Give all the relevant scales too**: beyond close-ups, the social-distance preset (shrunk to a few dozen pixels) often reverses the conclusion.
- Attach **objective measurements** (pixel diffs, areas, angles) so it can match "what it sees" with "what was measured".
- Explicitly ask it to **test its own previous-round judgment**, and allow it to say "my previous point doesn't hold".

> **Checkable question**: of the options I'm asking it to choose among, **does every one have an image**? Or do some exist only in my description?
> For options that exist only in the description, its advice is a guess.
- **Quota** (measured 09-22 18:05): `claude-opus-4-6-thinking` reports `Individual quota reached … Resets in 73h30m` (restored around 09-25 19:30). In the meantime falsification relies on Gemini alone; sending Gemini multiple images with multiple claims at once often hits the permission wall or "copies the text to invent counterexamples", so switch to **one image per batch, choosing only claims that this image can decide**.
