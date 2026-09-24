> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/02_环境准备与人工介入/B850_Linux环境/写脚本的坑.md)

> ← [This machine (Linux) Linux environment](../b850-linux-environment.md) · [00 · Master table](../../00-overview.md)

# Six Pitfalls Hit While Writing Scripts (mainly bash; actually hit from 2026-09-21 while DSH wrote delivery packaging and other scripts)

All six are “the script does not error, but behaves differently from what you think”, with a log full of PASS.
Pitfalls of Blender `bpy`/geometry scripts → [Blender scripting pitfalls](blender-scripting-pitfalls.md); pitfalls of offline csc compilation → [Compile offline before editor scripts](compile-offline-before-editor-scripts.md).

## 1 · Under `set -e`, do not write `[ condition ] && action`

When the condition is false the whole line returns 1, and `set -e` kills the function/script outright.
That is exactly how the preflight of the packaging script did `exit 1`.

```bash
[ -d "$D" ] && echo found        # ✗ the whole script exits when the directory does not exist
if [ -d "$D" ]; then echo found; fi   # ✓
```

## 2 · Under `set -o pipefail`, a grep with no match inside command substitution brings down the whole script

```bash
x="$(grep -o 'MenuItem("[^"]*"' f.cs | sed 's/.*("//')"   # ✗ exits when there is no MenuItem
x="$(grep -o '...' f.cs | sed '...' || true)"              # ✓
```
When extracting things that “may not exist” (MenuItem, the first heading line, version number), always add `|| true`.

## 3 · Do not list zip members with `7z l -ba | awk '{print $NF}'`

When paths in the archive **contain spaces**, `$NF` only takes the last word, and the count of top-level entries comes out wrong.
This workspace has directory names like `Assets/! ピンク♡プリン !/`.

```bash
7z l -slt a.zip | awk '/^Path = /{sub(/^Path = /,""); print}'   # ✓
```

## 4 · `mkdir` and file output in dry-run must also be guarded by DRY_RUN

Otherwise even a “rehearsal only” leaves empty delivery folders in the project, and the next judgment of “has this been done” will be wrong.
**The criterion is “after a dry-run, `git status` should be exactly the same as before”**.

> **Checkable question**: after running my dry-run, did the working tree change at all?
> If it changed, it is not a dry-run.

## 5 · The header of `free` is localized (hit twice on 09-22)
This machine's locale is Chinese, and the second-line header of `free -g` is `内存：` rather than `Mem:` ⇒ `awk '/^Mem:/'` gets no value (the import queue v2 thus misjudged “0 G available” on first start and got stuck). Pick one: `export LC_ALL=C` at the start of the script, or `free -g | awk 'NR==2 {print $NF}'`; most robust is to read `MemAvailable` from `/proc/meminfo` directly.


## 6 · “Read-only reference” and “export target” must be two separate parameters (09-23 tongue-piercing chain L5-7 incident)
- **Trigger moment**: writing any script that “reads a base avatar/reference file, then exports a new file” (Blender exporting FBX, Unity exporting prefabs, 7z repacking).
- **Checkable question**: are the reference path and output path the same parameter, or can they be filled by the same value? Does the output path land under a project's `Assets/` or `/data`?
- **Practice**: use `--ref` for the reference and `--out` for the output; at the start of the script, throw an error if `realpath(out)==realpath(ref)` or out lands inside the reference's directory tree; after running, read back the reference's sha256 and confirm it matches the pre-run value. Mark the reference path “read-only” in the task brief.
- **Origin**: the first version of L5-7 had only one `--fbx`, and overwrote Project A's base-avatar FBX (with the editor open) with a much smaller accessory export; it was restored from a byte-identical face-sculpt backup (sha checked before copying back). The broken file was only not imported because the editor had not refreshed at the time — without a backup, or had a refresh happened, the base avatar would have been destroyed.
- Another pitfall from the same time: `json.dump(obj, open(p,"w"))` does not hold the handle, and breaks halfway when it hits a non-serializable value → `with open(...)` + `default=float`. (The same incident also had a geometric pitfall with triangle normals; see section 3 of [Blender scripting pitfalls](blender-scripting-pitfalls.md).)
