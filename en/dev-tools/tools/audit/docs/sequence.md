> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/sequence.md)

# Request sequence `sequence` <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §13 / §13.1 / §13.2. § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous: [T-12 build-time capture · criteria, deployment, requests and acceptance](build-capture-verify.md) · Next: [Request sequence `sequence` · example, acceptance and limitations](sequence-example.md) <!-- nav -->

## 13. Request sequence `sequence` (task BB)

One menu trigger runs several T1/T3/T4/fit sub-requests in order. Batch scenarios — per-outfit "set state → render" ×13,
T-16/T-19 batch runs — no longer require Claude to trigger `Tools/AvatarAudit/Run Request` one by one; just write one `sequence`
request and trigger it once. Implementation: `unity/Editor/AuditSequence.cs`.

```json
{
  "tool": "sequence",
  "out": "/abs/path/outfits_run",
  "stop_on_error": true,
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "steps": [
    { "tool": "state", ...a complete T1 request... },
    { "tool": "turntable", ...a complete T3 request... }
  ]
}
```

| Field | Default | Description |
|---|---|---|
| `out` | — | Required; absolute path of the **summary directory**: writes `sequence_status.json` and the top-level `status.json` / `audit.log` |
| `steps` | — | Required; array whose elements are **complete** T1 (`state`) / T3 (`turntable`) / T4 (`fit`) / `menu` requests, executed in array order |
| `stop_on_error` | `true` | Stop as soon as a step is not `done` (`error` / `aborted`); remaining steps are recorded as `skipped`. With `false`, failed steps are skipped and the run continues; the whole sequence still reports `error`/`aborted` at the end |
| `avatar` | omitted | When `avatar` is set at top level, **steps that omit `avatar` inherit it** (a step's own value is not overridden); saves repeating the avatar name across 13 outfits |
| `timeout_seconds` | sum of steps + 10 s per step | Total timeout for the whole sequence; each step can still loosen its own limit via its own `timeout_seconds` |

Besides each tool's own fields, a step object accepts an extra `id` (optional, defaults to something like `"01_<tool>"`) and an optional `out`:

- `id`: only used to identify the step in `sequence_status.json`.
- `out`: when omitted, derived automatically as `<summary-dir>/<two-digit index>_<id>`; if given it **must be an absolute path** (otherwise Begin errors out immediately,
  so relative paths never land in Unity's current working directory). Each sub-request still writes `status.json`,
  `audit.log` and its tool artifacts into its own `out` as usual, exactly as when triggered alone.

**Nested `sequence` is not supported** (`steps[].tool == "sequence"` errors out): there is no "state machine within a state machine" use case,
and nesting would make timeouts, summaries and cleanup hard to audit.

### 13.1 Behavior essentials

- **Frame-by-frame stepping**: uses exactly the `EditorApplication.update` pump of `AuditRunner`; no new threads, no blocking of the main thread;
  each Tick advances only one step, and the next step starts only after the current sub-tool's `Tick()` returns true and the sub `status.json` is written as `done`.
- **State carry-over**: T1's `Cleanup` deliberately keeps the parameter values of the last state, so when pairing `T1 (set state) → T3 (render)`,
  T3 captures exactly the state T1 set up; for multi-step accumulation, use `"reset": "none"` in the T1 steps. This tool does not transfer state;
  carry-over relies entirely on the sub-tools' own semantics.
- **Whether Play is needed**: if any sub-step needs Play (`state` / `fit` / `menu`), the whole sequence requires Play — same as running
  T1 alone: either already in Play, or set `"auto_play": true` at top level (the whole sequence then runs from the start after entering Play).
- **Each sub-tool's temporary changes** are reverted by calling its `Cleanup` right when that step ends (same timing as a single request's teardown);
  a failed step does not affect artifacts already written by earlier steps.
- **Top-level `status.json`**: `{"state":"running|done|error|aborted","progress":"3/26","tool":"sequence",...}`;
  when a step is `aborted` (T-13 semantics), the top level is written as `aborted` too.

### 13.2 Output `sequence_status.json`

```json
{
  "tool": "sequence", "out": "/abs/path/outfits_run",
  "state": "running|done|error|aborted", "stop_on_error": true,
  "requires_play_mode": true, "step_count": 26,
  "started_at": "...", "finished_at": "...", "current_index": 7, "failure": null,
  "steps": [
    { "index": 1, "id": "o01_t1", "tool": "state", "out": "/abs/.../01_o01_t1",
      "state": "done", "seconds": 12.34, "started_at": "...", "finished_at": "...", "error": null },
    { "index": 2, "id": "o01_t3", "tool": "turntable", "out": "/abs/.../02_o01_t3",
      "state": "running", "seconds": null, "started_at": "...", "finished_at": null, "error": null }
  ]
}
```

`state`: `pending` (not started yet) / `running` / `done` / `error` / `aborted` / `skipped` (skipped because an earlier step failed).
