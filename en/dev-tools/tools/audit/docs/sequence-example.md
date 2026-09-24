> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/sequence-example.md)

# Request sequence `sequence` · Example, acceptance, and limitations <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §13.3–13.5. § numbers follow the original; for cross-page § references see [Documentation index](../README.md). <!-- nav -->
> Previous: [Request sequence `sequence`](sequence.md) · Next: [Single-button dialog suppression AuditDialogGuard](dialog-guard.md) <!-- nav -->

### 13.3 Example: 13 outfits, one by one “T1 fully dressed → T3 torso four sides”

Milfy's `RJ_Outfit` is a **13-gear** radial (0 base avatar default outfit /1 beast-paw bikini /2 tsundere maid /3 bunny angel /
4 bunny loungewear /5 lop-eared bunny /6 snowflake romance /7 misty knit /8 Petal Drape /9 LUNALICE /10 Rogue Noir /
11 NOEM hoodie /12 Peridot — not 26 gears, evidence `工程B/_审查准备_20260918.md:28`).
The radial selects a gear by `i/n` (`n=13`); the 13-step example takes the midpoint of each gear, **`(i+0.5)/13`** (`i=0..12`, i.e.
`1/26, 3/26, …, 25/26`); **step 1 is gear 0 “base avatar default outfit”, not a purchased outfit**.
Two steps per outfit: T1 uses `reset:none` to switch only this outfit's gear (continuing from the previous step's state), T3 shoots the torso (Chest) from four azimuths, with no transparency check.
`out` is omitted everywhere and automatically lands in `01_…`, `02_…` under the summary directory; `avatar` is inherited from the top level. **Values/gears follow the actual gears in that project's
`params.json` / `gear_slots`**.

```json
{
  "tool": "sequence",
  "out": "/abs/path/audit/milfy_outfits_13_run",
  "stop_on_error": true,
  "avatar": "Milfy",
  "steps": [
    { "id": "o01_t1", "tool": "state", "reset": "none", "states": [ { "id": "o01_on", "params": { "RJ_Outfit": 0.0384615385 } } ] },
    { "id": "o01_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o02_t1", "tool": "state", "reset": "none", "states": [ { "id": "o02_on", "params": { "RJ_Outfit": 0.1153846154 } } ] },
    { "id": "o02_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o03_t1", "tool": "state", "reset": "none", "states": [ { "id": "o03_on", "params": { "RJ_Outfit": 0.1923076923 } } ] },
    { "id": "o03_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o04_t1", "tool": "state", "reset": "none", "states": [ { "id": "o04_on", "params": { "RJ_Outfit": 0.2692307692 } } ] },
    { "id": "o04_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o05_t1", "tool": "state", "reset": "none", "states": [ { "id": "o05_on", "params": { "RJ_Outfit": 0.3461538462 } } ] },
    { "id": "o05_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o06_t1", "tool": "state", "reset": "none", "states": [ { "id": "o06_on", "params": { "RJ_Outfit": 0.4230769231 } } ] },
    { "id": "o06_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o07_t1", "tool": "state", "reset": "none", "states": [ { "id": "o07_on", "params": { "RJ_Outfit": 0.5 } } ] },
    { "id": "o07_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o08_t1", "tool": "state", "reset": "none", "states": [ { "id": "o08_on", "params": { "RJ_Outfit": 0.5769230769 } } ] },
    { "id": "o08_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o09_t1", "tool": "state", "reset": "none", "states": [ { "id": "o09_on", "params": { "RJ_Outfit": 0.6538461538 } } ] },
    { "id": "o09_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o10_t1", "tool": "state", "reset": "none", "states": [ { "id": "o10_on", "params": { "RJ_Outfit": 0.7307692308 } } ] },
    { "id": "o10_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o11_t1", "tool": "state", "reset": "none", "states": [ { "id": "o11_on", "params": { "RJ_Outfit": 0.8076923077 } } ] },
    { "id": "o11_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o12_t1", "tool": "state", "reset": "none", "states": [ { "id": "o12_on", "params": { "RJ_Outfit": 0.8846153846 } } ] },
    { "id": "o12_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o13_t1", "tool": "state", "reset": "none", "states": [ { "id": "o13_on", "params": { "RJ_Outfit": 0.9615384615 } } ] },
    { "id": "o13_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false }
  ]
}
```

If T1 also uses probes/sentinels, write `probes`/`sentinels`/`gear_slots` etc. in the corresponding `state` step as usual; if T3 should show only hands/feet,
write that step's own `only_renderers`. All steps run in the same Play session; T1's `reset:none` makes the 13 gears switch cumulatively in real operating order.

### 13.4 Unity acceptance steps for Claude

1. After deploying with `sync_audit.py <工程>`, `Assets/AvatarAudit` compiles with 0 errors, and `AuditSequence.cs` is among them.
2. Write a **2-step** mini sequence (1×T1 + 1×T3) to `Library/AvatarAudit/request.json`, **press Play first**, then
   `Tools/AvatarAudit/Run Request`: in `<汇总>/sequence_status.json`, step 2 appears as `running` only after step 1 is `state=done`;
   the image rendered by T3 is indeed the outfit set by T1 (compare with running T1→T3 separately).
3. Check that `<汇总>/status.json` is `state=running` with `progress` increasing while running, and `done` when finished;
   each sub `out/status.json` matches running that request on its own.
4. Deliberately give step 2 a nonexistent `tool`: with `stop_on_error=true`, the step before it is still `done`, it is `error`, the ones after are `skipped`,
   the summary is `state=error` and `failure` points to it; with `stop_on_error=false`, the steps after it keep running and the final summary is still `error`.
5. A sequence with only T3 steps **does not require Play** (can run directly in Edit mode); a sequence containing T1 should be blocked in Edit mode with a prompt to enter Play.
6. Click `Abort Current Run` midway: the current step is `error`, later ones `skipped`, and devices/scene can be restored by each step's `Cleanup`
   (check item by item against the “temporary change → restore” table in §8).

### 13.5 Known limitations

- Only offline compilation + pure-logic tests were done (`_长程任务_20260918/派工/tmp/bb/seqtest/`, all 33 assertions passed);
  **never run in Unity** — state continuity between steps (especially multiple T1 steps with `reset:none`, and
  “the scene has no GM originally, and T1 temporarily creates/destroys `__AvatarAudit_GM` at each step”) must be measured per §13.4.
- No support for conditions/parallelism/nesting; runs serially in array order only.
- The top-level `status.json` cannot express “which step it's on”; for precise location look at `steps[]` in `sequence_status.json`.

---
