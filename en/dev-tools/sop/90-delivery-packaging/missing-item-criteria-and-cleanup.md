> 🌐 English translation · [中文原文](../../../../开发工具/SOP/90_交付打包/缺失项判据与清理.md)

> ← [90 · Delivery Packaging](../90-delivery-packaging.md). Trigger: before packing/uploading.

# 90 · Missing-Item Criteria and Cleanup Checklist

**“It compiles after unpacking” is not enough** — `MissingScript`, `InternalErrorShader`, and broken menu references **none of them affect compilation**; a package that compiles can still turn magenta / silently fail on the client's side (F §4, K #1). Before packing you must pass this set of criteria.

| Criterion | How to read |
|---|---|
| Zero `MissingScript` | **Check both kinds**: `m_Script == {fileID: 0}`, and “GUID with no corresponding script”; **also check source prefabs** (they often hide in prefabs) |
| Zero `InternalErrorShader` | File level: map shader GUIDs against `.meta` and built-in IDs (it can't be grepped in `.mat`); runtime level: read the shader name per Renderer on a baked clone |
| All references resolve | Reverse-lookup GUIDs, broken links == 0 ([20 step 3](../20-asset-inventory-and-import.md)) |
| Exactly 1 root selected into this build; descriptors across all Assets and backups recorded in a separate list | Check root name / purpose / blueprintId per [03 avatar-root convention](../03-assembly-and-conflict-rules/avatar-root-conventions.md); keep intentionally delivered multiple roots and verify each one; do not count the number of spare roots as a failure |
| `blueprintId` verified | Matches the online one; report if multiple roots share an ID |
| **Notes match the project** | Check item by item that the `Assets/` paths and purposes in the delivery notes / `来源说明.txt` equal what's actually in the project; **for after-the-fact archiving write only archive notes, do not fabricate the design intent of the time** (see [90 main page “Delivery notes”](../90-delivery-packaging.md)) |

- **If not met**: any hit means no delivery; go back to the corresponding stage; if a criterion can't be checked write “not verified” — do not default to pass.

## Cleanup checklist (two new items, 2026-09-19)

Besides the order-specific scripts in “Must clean before packing” on the [90 main page](../90-delivery-packaging.md), before delivery also clean:

- `Backup/`, `com.vrcfury.temp` (build temp directory)
- `#GENERATED` and other per-avatar generated directories (registered before upgrading vendor packages, see [20 implementation pitfalls](../20-asset-inventory-and-import/implementation-pitfalls.md))
- `unity-mcp` (remove the MCP entry from `Packages/manifest.json`; historically measured 1 line each in 6 COMM orders and Project B)
- Audit code and leftovers — **strip with the tool, not by hand** (B-T23, since 09-22):
  `python3 开发工具/通用工具/审查/perception/strip_audit.py --project <工程根> --check` lists them → **on a project copy** `--apply --baseline <交付基线提交>` → run `--check` again, it must exit 0 (zero leftovers).
  It strips: `Assets/AvatarAudit/` (and the old location `Assets/Editor/AvatarAudit/`), `Assets/ZZZ_GeneratedAssets/`, `Packages/nadena.dev.ndmf/__Generated/`, `Library/AvatarAudit/`, unity-mcp in manifest/packages-lock, and drift in `ProjectSettings/` relative to the baseline; leftover audit components in scenes/prefabs are only listed, not deleted (looked up from the git baseline by script guid; if undecidable it reports `undecidable` and exits non-zero — **must not be treated as zero leftovers**). `Captures/` and `Assets/Editor/AvatarGen/` are only flagged; clean them separately per 90 main page step 1.
  ⚠ Run on a **true copy** (`rsync` without `-H`, no `--link-dest`): `--apply` rewrites `manifest.json` in place, and sharing an inode with the open project would delete its unity-mcp too.
- **Move `旧场景参考/` out of `Assets/`** (F §9: H3-Eku and H9-Sio placed it outside `Assets/` and noted “do not overwrite directly” in `说明.txt` — good practice; An-Labo left backup scenes/prefabs inside `Assets/` with no notes at all — bad practice)

⚠ Before deleting, first confirm these things have a copy elsewhere (see 90 main page “Before cleaning the working directory”).


## Order-specific scripts and intermediate outputs (moved in from the 90 main page, rules unchanged)

### Trigger
**When you are about to pack for delivery.**

### Ask
**“Are there scripts carrying the order number under `Assets/Editor/`? Are there intermediate logs and diagnostic screenshots under `Assets/`?”**

```bash
find Assets -maxdepth 3 \( -name "*<订单号>*" -o -path "*Screenshots*" \) -not -name "*.meta"
find Assets/_Work -name "*.txt" -not -name "*.meta"
```

### If the answer is wrong
Delete them. **Run a compile before deleting** to confirm nothing else references these classes.

### ⚠ Distinguish “intermediate outputs” from “deliverables” — they are mixed in the same directory

Taking `Assets/_Work/` as an example:

| Keep | Delete |
|---|---|
| `*.unity` working scenes | `*.txt` probe logs under `_50装配/` `_55装位/` |
| `_60菜单/*.anim` `*.asset` `*.controller` — **these are the deliverables** | `_60菜单/*_probe.txt` `*_verify.txt` |

**Menu assets and animation clips are generated results, not script runtime outputs** — deleting the scripts does not affect them.

### Evidence (2026-09-07 Project C)
After one night of work, `Assets/Editor/AvatarGen/` had accumulated **5 order-specific scripts totaling 243,639 B**
(the largest 106 KB), plus 7 diagnostic screenshots and 19 intermediate `.txt` files.
**They would be packed with the project and sent to the client.**

**Cause**: multiple subagents each added menu methods to the same directory, and nobody was responsible for cleaning up.
→ **Rule**: order-specific scripts should go in `Assets/Editor/<订单号>/`,
not mixed into `Assets/Editor/AvatarGen/`, which holds general tools; before packing just delete the whole directory.
