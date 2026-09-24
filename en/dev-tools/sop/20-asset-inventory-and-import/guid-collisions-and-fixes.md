> 🌐 English translation · [中文原文](../../../../开发工具/SOP/20_素材清点导入/GUID撞车与修法.md)

# One GUID, multiple paths: how collisions happen and how to fix them (measured 2026-09-06)

> A subpage split out of [`20-asset-inventory-and-import.md`](../20-asset-inventory-and-import.md). It takes over the evidence section from step 3 "five completeness checks"; the hard criterion "one GUID multiple paths == 0" and the false-positive screening remain on the main page.

> ### ⚠ One GUID, multiple paths: hit twice in one day (2026-09-06 Project C)
>
> Unity **does not allow one GUID to map to two paths**. When it does happen, on opening the project it
> **silently reissues GUIDs for some of them**; prefabs referencing them break on the spot and render magenta, **and nothing shows up in the log**.
>
> | How it collides | Example |
> |---|---|
> | **The vendor moved a file in a version bump but kept the GUID** | Two hairstyle packs share a common material with the same GUID, and the vendor moved it to another directory in a newer version; one pack installed at the old version (old path), the other at the new version (new path) → two hairstyle prefabs broke |
> | **An accessory pack bundles a fallback copy of lilToon** | The fox ear pack included 3 files such as `lts.shader`, with the same GUIDs as `Packages/jp.lilxyzw.liltoon` → affected **every lilToon material in the whole project** |
>
> **Both slipped past the per-package clash count of `unpack_unitypackage.py`** — that only checks "same path, different GUID".
>
> **The boundary of shared assets is the "vendor", not the "product"**, and it even spans `Assets/` and `Packages/`.
> So the criterion must **exhaustively cover the whole project**; you can't guard against it grouped by package.
>
> **Fix**: go to the source unitypackage (tar.gz, entries are `<guid>/pathname`) to retrieve the vendor's original GUID,
> **edit the `.meta` in place + delete the duplicate copy**. Don't delete and rebuild — that reissues the GUID again.
> **After fixing, you must reopen Unity once to re-verify the GUID wasn't changed again.**
