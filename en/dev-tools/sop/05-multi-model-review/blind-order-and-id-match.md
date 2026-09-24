> 🌐 English translation · [中文原文](../../../../开发工具/SOP/05_多模型评审规程/盲测图序与指认对照.md)

# Blind tests: how to number the images, and how to map identifications back

> Parent: [05 · Multi-model review procedure](../05-multi-model-review.md).

## `agy_panel.py` renames images in the order passed, **starting from `img00`** (0-based)
- `--images a b c` become `img00.png img01.png img02.png` in the review directory; the model's identifications use these names.
- 2026-09-19 Project E blind test: my own answer key was numbered 1-based (img1…img5); the model identified `img01` and `img04`, and at first glance I read it as "wrong picks"; only after mapping back by hash did I find it pointed exactly at numbers 2 and 5 in the answer key — both correct, zero false positives.
- **How to do it**: write the answer key 0-based directly (consistent with agy_panel), or after the run use `md5sum` to map `/tmp/agypanel_*/imgNN.png` back to the original images before reading the conclusions.
- Related pitfall: the location labels of `agy_review` are occasionally self-contradictory (`img03.png (img4)`, measured in task AE) — for A/B judgments, switch to a forced choice of "first image / second image" and run once with the order swapped.

## How to arrange a blind test
- Mix "before fix / after fix / control" together; the answer key exists only locally (`KEY.txt`), and the prompt doesn't reveal which image is which condition.
- Include at least one image that **should have a problem** and one that **should not**; if the model says "they all have problems" or "none have problems", this blind test doesn't count.
- **Don't write the expected answer in the prompt** (2026-09-19 acceptance BC): writing "my conclusion is X, please overturn it" is fine; writing "you should see Y" is not — that hands over the answer. agy prompts drafted by DSH are reviewed by Claude before being sent.
