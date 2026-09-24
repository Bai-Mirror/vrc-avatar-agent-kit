> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/问题定位/观测口径/日志说落盘了不等于真的落盘了.md)

> ← [The criterion itself may be broken](criterion-may-be-broken.md) · [00 · Master table](../../00-overview.md)

# The log says it was saved ≠ it was actually saved (2026-09-21, Project B, 80-texture tiering)

## `JsonUtility` **silently** writes nothing: a `List<T>` whose element type lacks `[Serializable]`

**Trigger**: any tool that uses `JsonUtility.ToJson` to persist a "rollback log / backup / manifest".

**Self-check question**:

> The "wrote N entries" I printed — does it read the **in-memory Count**, or **a count taken by reading the file back**?

Hit before (Project B 80-texture tiering, 2026-09-21; cost: one batch change with no restore path):
`OrigList` had `[Serializable]`, but the **element type `Orig`** of the `List<Orig>` inside it **did not**.
In this case `JsonUtility.ToJson` **throws no exception, logs no warning, and simply drops the whole field**.
All that remained on disk was:

```json
{ "savedAt": "2026-09-21 08:49:55", "updatedAt": "2026-09-21 08:49:55" }
```

Yet the log still printed "Appended **127** original settings… (127 total; saved to disk before changes)" —
that 127 was `data.entries.Count`, the real count in memory. **The log said it was saved; it was not.**
Then 127 textures were changed, and the tool's own "Restore" menu became useless from that point on.

**Fix** (apply both; neither is optional):
1. Add `[Serializable]` to the element type;
2. **Immediately after writing, read the file back and count; if it doesn't match, throw and abort** — never continue with destructive changes without a restore path:

```csharp
File.WriteAllText(path, JsonUtility.ToJson(data, true));
var verify = JsonUtility.FromJson<OrigList>(File.ReadAllText(path));
int onDisk = verify?.entries?.Count ?? 0;
if (onDisk != data.entries.Count) throw new Exception("原设置没写全，不改。");
```

**Trade-off**: item 2 looks redundant, but it is the only guardrail that catches this whole class of "silent serialization failure" —
a missing `[Serializable]` is just one case; a member that is a `property` rather than a `field`, a `Dictionary` type,
or nesting deeper than 7 levels all produce the same "silent empty file".

**Fallback**: for this kind of batch import-settings change, **commit it as a separate commit immediately after it's done**;
the real restore path is `git revert` of that one commit — don't bet everything on the tool's own backup.
