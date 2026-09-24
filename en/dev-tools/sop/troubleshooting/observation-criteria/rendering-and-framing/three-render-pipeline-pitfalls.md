> 🌐 English translation · [中文原文](../../../../../../开发工具/SOP/问题定位/观测口径/渲染与取景/出图管线三个坑.md)

# Three pitfalls of the render pipeline: solid color · `-nographics` · duplicate images

> A subpage split out of [`rendering-and-framing.md`](../rendering-and-framing.md). It takes over the main page's former sections 1–3; the main page's remaining "master copy vs. project copy divergence" and "zoned criteria" have been renumbered as sections 1 and 2.

## 1 · The log is all PASS, but the image is a solid color

### Trigger
**When you are about to send a batch of renders to review, or to the user/client.**

### Question
**"What are the pixel extrema of these PNGs?"**

```python
from PIL import Image
im = Image.open(p).convert("RGB")
print(im.size, im.getextrema())   # ((205,205),(205,205),(205,205)) = solid color = nothing was rendered
```
A cheaper approximate criterion: **compare the byte size against a known-good image from the same camera position**. A blank image is one to two orders of magnitude smaller.

### If the answer is wrong
**Don't send it for review; go back and check the framing.** If you send a batch of blank images to review, the model will earnestly comment on the background color,
and you will misread "zero findings" as "pass".

### Evidence (2026-09-06, Project C)
- The log was **all PASS from start to finish**: blend shape index check PASS, cleared 526/526, all 12 keys read back correctly one by one,
  `wrote cand1_1正面.png 1500x1500`, final restore PASS
- **The RGB extrema of all three candidate images were `(205,205)`**, 17–31 KB; the baseline image from the same camera position was 1019 KB with extrema `(2,255)`
- The divergence was in auto-framing: the good run had the probe line `[probe] attempt=0 o=1.150 bg%=91.8 bbox=(90,59)-(293,286)`
  and converged to `ortho=0.717`; the bad run **had no probe line** and went straight to `ortho=4.946` —
  putting a 1.18 m avatar into a ten-meter field of view

> **"wrote xxx.png 1500x1500" only proves the file was written, not that anything was drawn on it.**

---

## 2 · Batchmode runs that render images **must not add `-nographics`**

### Trigger
**When you are about to assemble a Unity batchmode command that renders images.**

### Question
**"Does this command have `-nographics`? Does it need to render images?"**

### If the answer is wrong
For rendering, **remove** `-nographics` and keep only `-batchmode`.
For work that **doesn't render** — compiling, asset import, reading the console — adding it is harmless (and faster).

### Evidence and reservations
A subagent's test report: with `-nographics`, **the camera output was a constant color unrelated to the scene content**
(obtained by sampling the camera's RenderTexture directly).

⚠ **I have not independently reproduced this experiment**, so the mechanism is marked "not reproduced".
But the rule itself is **zero-cost and semantically what it should be**: `-nographics` is defined as not initializing the graphics device,
and rendering must go through the graphics device. **Not adding it by default** is the cheap, correct choice; no need to wait for the experiment.

---

## 3 · When shooting several sets in a row, reusing the same loaded scene produces **duplicate images**

### Trigger
**When you are going to render several sets with different parameters in a row within one Unity session (multiple face sculpting candidates, multiple color schemes, multiple accessory combinations).**

### Question
**"Did I reload the scene between the two sets?"**

### If the answer is wrong
**Call `EditorSceneManager.OpenScene` again between every set**; don't just change parameters and keep shooting.

### Criterion (mandatory; cannot rely on eyeballing)
After the run, **do a pairwise pixel diff**; any pair with zero difference is a duplicate:

```python
from PIL import Image, ImageChops
d = ImageChops.difference(Image.open(a).convert("RGB"), Image.open(b).convert("RGB"))
print(d.getbbox())        # None = the two images are identical
```

### Evidence (2026-09-06)
Three candidate sets shot in a row: **cand2 and cand3 came out byte-for-byte identical the first time** (same MD5).
Parameter application was clearly correct (read-back check PASS); the **render state was stale**.
After reloading the scene and shooting again, the pairwise sumdiff among the three sets was 400k–1M — not noise.

> This belongs to the same family as "1 · solid color": **correct parameters ≠ correct image.**
> For any "shoot N sets in one session" workflow, a pairwise pixel diff is a **mandatory closing criterion**.

---
