> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/turntable.md)

# T3 turntable renders · request and output <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §5 / §6. § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous: [T1 output format · states.json field semantics](state-driver-states-fields.md) · Next: [T3 · transparency sorting criteria](turntable-transparency.md) <!-- nav -->

## 5. T3 request format

```json
{
  "tool": "turntable",
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "out": "/abs/path",
  "size": 1024,
  "bg": [0, 1, 0],
  "targets": [ { "bone": "Head", "radius": 0.45 }, { "bone": "LeftFoot", "radius": 0.35 } ],
  "azimuths": 8,
  "elevations": [-20, 0, 35],
  "fov": 30,
  "transparency_check": true,
  "vanish_threshold": 0.05,
  "only_renderers": ["Body", "Glove"],
  "hide_renderers": ["Skirt"]
}
```

| Field | Default | Description |
|---|---|---|
| `size` | 1024 | Side length of the square image, clamped to 64..4096 |
| `bg` | `[0,1,0]` | Solid background color (0–1 space) |
| `targets` | Head 0.45 / Chest 0.8 / LeftFoot 0.4 / RightFoot 0.4 | Each item has `bone` (a `HumanBodyBones` name; if not found, falls back to lookup by hierarchy name) + `radius` (world distance from camera to bone, in meters) |
| `azimuths` | 8 | Number of azimuth angles, counted from the character's **front** (`avatar.transform.forward`), evenly dividing 360° |
| `elevations` | `[-20,0,35]` | Elevation angles (degrees), clamped to ±89 |
| `fov` | 30 | Camera vertical FOV |
| `transparency_check` | true | Whether to run transparency sorting detection |
| `vanish_threshold` | 0.05 | Vanish-ratio threshold, `flagged = vanish_ratio >= vanish_threshold` |
| `only_renderers` | omitted | Optional, array of strings (task U); **only show** renderers matching these strings; the other renderers have `enabled` set to false during rendering. Elements may also be `{name}`/`{path}`/`{renderer}` objects. Matching is by **substring of GameObject name / path relative to the avatar hierarchy / full scene path** (case-insensitive). Use: when a hand is blocked by the skirt, `["Body","Glove"]` renders only the body + gloves. Strings that match nothing record a warning |
| `hide_renderers` | omitted | Optional, array of strings (task U); on top of `only_renderers`, additionally hide renderers matching these strings. Both this and `only_renderers` act on **the visible set before rendering**, so hidden renderers never become transparency-check candidates (they won't appear in `transparency.json.candidates` either) |
| `transparent_queue_min` | 2501 | Only material slots with `renderQueue > this value` are candidates; Opaque 2000 / Cutout 2450 are excluded, and lilToon Transparent · Refraction · Fur are usually ≥ 2460. If a vendor puts a transparent slot at the 2460 tier (Project A's `Tea_GoldenHour(Hair)` is q2460), the default 2501 will not treat it as a candidate — when you suspect such a slot, lower this to 2400 and run again |
| `t_min` | 0.15 | Only count behind / vanished within the mask where the pixel transmittance `t >= t_min` (rationale in §6) |
| Others | | `color_epsilon`(0.03), `min_mask_px`(200), `min_behind_px`(100), `save_flagged_limit`(60), `culling_mask`(if omitted, the scene main camera's is used), `timeout_seconds`(3600); `mask_layer`(31) is kept only for compatibility with old requests — the second version isolates via `renderer.enabled` and no longer uses it |

Full example of `only_renderers` / `hide_renderers` ("when a hand is blocked by the skirt, render only the body + gloves"):

```json
{
  "tool": "turntable",
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "out": "/abs/path",
  "targets": [ { "bone": "Head", "radius": 0.45 }, { "bone": "LeftHand", "radius": 0.25 },
               { "bone": "RightHand", "radius": 0.25 } ],
  "azimuths": 12,
  "elevations": [-20, 0, 35],
  "transparency_check": true,
  "only_renderers": ["Body", "Glove"],
  "hide_renderers": ["Skirt", "Dress"]
}
```

These two lists are applied before every render (including A/B/C0/C1/M) and kept throughout T3; `Cleanup` restores the `enabled` values from before entry.
Which strings actually matched, and how many renderers are visible / hidden after filtering, are written to `shots.json.view_filter`, and a log line is recorded in `status.json`.
**Why substrings rather than exact names**: a model often has several `Body_1/Body_2`, `Glove_L/Glove_R`; writing `Body` hits them all at once.
The side effect is that the same substring also hits other things (e.g. `Glove` also hits props like `GloveBox`); check against `view_filter.only_matched`.

File names: `<bone>_az<azimuth>_el<elevation>.png` (bones with the same name get a `_t<index>` suffix).

---

## 6. T3 output format

### `shots.json`

`{tool, avatar, out, size, bg, fov, culling_mask, targets[{bone,radius,file_base,world}], shot_count, shots[...], view_filter?, warnings}`
Each shot: `{bone, file, az, el, radius, fov, size, target_world, cam_position, cam_rotation_euler}`.
When `only_renderers` / `hide_renderers` were requested there is an extra `view_filter`:
`{only_renderers[], hide_renderers[], only_matched[], hide_matched[], visible_after, hidden_after}`
(`*_matched` are the strings that actually hit a renderer, used to spot patterns that were "written but matched nothing").

### `transparency.json`

```json
{
  "tool": "turntable.transparency", "avatar": "...",
  "model": "per-pixel dot: t=avg(C1-C0); E=C0+t*B; vanished = |A-(C0+t*bg)|<eps && |A-E|>eps",
  "vanish_threshold": 0.05, "color_epsilon": 0.03, "t_min": 0.15,
  "transparent_queue_min": 2501, "color_space": "Linear",
  "min_mask_px": 200, "min_behind_px": 100,
  "candidates": [
    { "path": "Hair/Acc", "submesh": 1, "material": "acc_q3050", "render_queue": 3050,
      "material_names": ["body", "acc_q3050"], "render_queues": [2000, 3050] }
  ],
  "candidate_count": 9, "record_count": 216, "flagged_count": 3,
  "records": [
    { "target": "Head", "az": 45, "el": 0, "shot_file": "Head_az45_el0.png",
      "renderer_path": "Hair/Acc", "submesh": 1, "material": "acc_q3050", "render_queue": 3050,
      "material_names": ["body", "acc_q3050"], "render_queues": [2000, 3050],
      "mask_px": 4210, "behind_px": 3100, "vanished_px": 900,
      "t_p50": 0.82, "model_error_p50": 0.011,
      "vanish_ratio": 0.29, "flagged": true, "skipped": false,
      "vanished_owners": [ { "renderer_path": "Hair/Hair_GoldenHour", "share": 0.91 } ] }
  ],
  "flagged_images": [ { "target": "Head", "az": 45, "el": 0, "renderer_path": "Hair/Acc", "submesh": 1,
                        "material": "acc_q3050", "vanish_ratio": 0.29,
                        "A": "tr_37_A.png", "B": "tr_37_B.png", "C0": "tr_37_C0.png",
                        "C1": "tr_37_C1.png", "M": "tr_37_M.png", "C": "tr_37_C0.png" } ],
  "warnings": []
}
```

- The candidate unit is `(renderer_path, submesh)`; `material` / `render_queue` belong to that slot, while `material_names` / `render_queues`
  are still for the whole renderer (compatible with the first version's reading);
- `skipped: true` means slot k's mask pixels < `min_mask_px` (the slot is too small / occluded in this view) and it takes no part in the verdict;
- `vanish_ratio: null` means `behind_px < min_behind_px` (there is little behind slot k to begin with, so the ratio is meaningless);
- `t_p50` is the median transmittance of mask pixels; `model_error_p50` is the median of `|A−E|` over pixels with "`t >= t_min` and not vanished";
- `vanished_owners` is given only when flagged; it is computed by one ID render over the visible renderers other than R (top 3; the share denominator is the number of vanished pixels that decoded successfully);
- flagged records save five PNGs A/B/C0/C1/M (`tr_<record index>_A|B|C0|C1|M.png`); beyond `save_flagged_limit` only the numbers are kept, noted in
  `flagged_images[].note`. `C` is an alias of `C0`, for the first version's reading.
