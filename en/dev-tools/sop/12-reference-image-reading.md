> 🌐 English translation · [中文原文](../../../开发工具/SOP/12_参考图解读.md)

# 12 · Reading reference images　🔍 multi-model dispatch

> Reference images provided by the client → **actionable face sculpting direction + recoloring direction**.
> Comes after [10 Order intake](10-order-intake.md) and before [15 Set direction at kickoff](00-overview.md);
> the output feeds [30a-1 Produce candidates](30-face-sculpt.md) and [40 Texture recoloring](40-texture-and-coloring.md).
>
> **Made a standard step by the author on 2026-09-06** (first implemented on Project C).

## ⚠ This page's output **does not constitute a face sculpting plan**

It gives where we **want** to go, but lacks where we **can** go —
i.e. which face-shape blend shapes the base avatar actually provides. **Only the intersection of the two is a plan.**

So this page must be paired with step **20.5 Blend shape enumeration** (see below),
otherwise it produces plans that "invent keys out of thin air". Face sculpting adjusts only the vendor's blend shapes;
free-form vertex editing is not allowed — the hard rules are at the top of [30 Face sculpting](30-face-sculpt.md).

---

## Lineup: five lanes, two methods

| Lane | Who | How it runs | Role |
|---|---|---|---|
| 1 | `claude-opus-4-6-thinking` | `agy_panel.py` | Description |
| 2 | `gemini-3.7-flash-high` | `agy_panel.py`, **one image per batch** | Description |
| 3 | `deepseek-v4-flash-vision-exp` | `agy_panel.py` (included by default) | Description |
| 4 | Local Sonnet subagent | Reads the images directly | Description (**reads first, then looks at the model results**, to avoid being led) |
| 5 | **Local Fable subagent** | Reads the images directly | **Aesthetic judgment**: style mix, face sculpting direction, color hex |

**Lane 5 is independent and doesn't share output files.** It writes its own `参考图解读_Fable路.md`,
and the task description states explicitly "don't go looking for other lanes' output" — otherwise the five lanes degenerate into one.
Measured effective: Fable and the other lanes **independently** reached the same conclusion "the handsomeness isn't in the bone structure",
and the two lanes' measured iris colors `#B7B0BD` / `#B6AEBC` almost coincide, forming a cross-method cross-validation.

---

## Deterministic steps

### Step 1 · Prepare images　🤖

**Execute**
1. Copy reference images to **short ASCII names** `ref01.png`… (agy is unreliable with Chinese/emoji file names)
2. Scale proportionally to a long side of **≤1600px**, and record a mapping table of **short name ↔ original name ↔ whether scaled**

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of mapping table entries == number of original images | Count them |

---

### Step 2 · Write the descriptive schema and system prompt　🤖

`agy_panel.py` has a built-in **defect-review** schema (`findings`/`verdict`);
description tasks must bring their own, using three optional parameters: `--schema` / `--system` / `--raw`.

**Fields the schema requires per image**:
`image_id / hair / eyes / face_shape / makeup / outfit / accessories / mood_keywords / standout_feature`

**Four things the system prompt must include** (each one a pitfall we've hit)
1. "**Describe only the images actually attached; don't write a word about images not attached**" — DeepSeek was measured reviewing 8 when sent 2
2. **Don't list "which images there are"** — the model will make things up following the list
3. "This is **a description task, not a fault-finding task**; don't give improvement suggestions"
4. "Read files only with view_file / list_dir; **don't use any terminal commands**" — otherwise it hits the permission wall and returns empty

---

### Step 3 · Dispatch　🤖

```bash
# opus and deepseek: feeding five images at once is fine
python 开发工具/通用工具/agy_panel.py --task t.md --system s.txt --schema sc.json --raw \
  --models claude-opus-4-6-thinking --images refs/ref0*.png --out panel.json

# ★ gemini must be batched one image at a time
for n in 01 02 03 04 05; do
  python 开发工具/通用工具/agy_panel.py --task t.md --system s.txt --schema sc.json --raw \
    --no-deepseek --models gemini-3.7-flash-high --images refs/ref$n.png --out g$n.json
done
```

> ### ⚠ gemini always times out with multiple images at once (measured 2026-09-06)
>
> | Feeding | Result |
> |---|---|
> | 5 images (27 MB) | `status:ERROR` / `timeout waiting for response` / **185s** |
> | 5 images scaled to 1600px (8 MB) | Same timeout / **212s** — **scaling doesn't solve it** |
> | **1 image** | **Returns a full description normally** |
>
> The driving factor is **the number of images**, not size. On timeout, `response` is an empty string, and the tail of stdout has only
> the `json_schema` echo + `usage`, **very easy to misdiagnose as a parsing bug** —
> a subagent and the lead agent both fell for this in turn, and even wrote a useless patch.
>
> The tool has been changed: on failure it saves the raw stdout to `%TEMP%/agy_raw_<model>.txt`,
> and distinguishes "agy reported an error" from "couldn't parse". **When you see "nothing parsed", read that raw stdout first.**

**Post-criteria**

| Expected | How to read |
|---|---|
| Every lane is clearly marked **success/failure** | Failures must state the reason; don't silently drop a lane |
| **Don't treat** a failed lane **as "no problem"** | Zero flags ≠ pass |

---

### Step 4 · Consolidate　🤖

Write `<订单目录>/参考图解读.md`, structured as:

1. **Image mapping table** (short name ↔ original name ↔ whether scaled)
2. **Per-image descriptions**: lanes side by side, **bold what multiple lanes agree on**, **flag disagreements separately and explain where they differ**
3. **Face sculpting direction suggestions**: written as actionable directions (part + which way + magnitude),
   **not just "a bit cuter"**; each item marks which feature of which image it's based on; give **2–3 mutually exclusive candidate groups**
4. **Recoloring direction suggestions**: give concrete **hex**, not color adjectives
5. **Converged style keywords**
6. **Summary of disagreements between lanes** — a separate section listing conclusions stated by only one lane, each re-checked yourself

---

## Reading the results: only cross-method agreement counts as confirmed

- **The same conclusion reached independently by both methods, "agy model" and "local subagent"** → highest credibility
- Single-lane conclusions always go to "to be checked" — **neither discarded nor trusted outright**
- **Zero disagreements ≠ pass**. First ask: is there really no disagreement, or did the images I fed make things invisible to them?

### Three measured mistakes we've made (all reported up by subagents)

| Mistake | Example |
|---|---|
| **Using an unused asset as evidence** | Inferring style from "the client bought a certain eye texture pack" — while that pack was marked **not installed** at intake (doesn't support this base avatar) |
| **Conflicting with intake without self-checking** | Reported "choose one of two hairstyles", while at intake the user had decided **install both** |
| **Right observation, wrong conclusion** | Reported "all three levels of JSON fallback came up empty" (observation right), concluded it was a parsing bug (wrong; it was actually a timeout) |

**Rule: for every conclusion a subagent reports, first ask whether its tool calls can support it.**
Listing a directory can't establish "equivalent content", reading file names can't establish "equivalent function", and a truncated log tail can't establish a root cause.

---

## 20.5 Blend shape enumeration (a required companion to this page)

After importing assets and before producing face sculpting candidates, **dump all of the base avatar's blend shapes and separate out the "face-shape adjustment" ones (non-expression)** —
that is the **full set of options** for candidate values.

The original SOP didn't have this step, because the old way was "a person opens Blender and sees them".
Once the Agent produces candidates, **this enumeration becomes a necessity**.

| Expected | How to read |
|---|---|
| The key name list has > 0 entries and distinguishes "face shape / expression" | `AvatarDump.cs`·DumpBlendShapes, or parse the FBX directly |
| **Every key name** referenced in the face sculpting plan is in the list | grep each one |

## Related

- Lineup, image granularity, quota → [05 Multi-model review procedure](05-multi-model-review.md)
- Hard limits on face sculpting methods → top of [30 Face sculpting](30-face-sculpt.md)
- Finalizing the color scheme → [40 Texture recoloring](40-texture-and-coloring.md)
- Criteria and observation conventions → [Troubleshooting/Observation conventions](troubleshooting/observation-criteria.md)
