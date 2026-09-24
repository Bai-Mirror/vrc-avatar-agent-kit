> 🌐 English translation · [中文原文](../../../../开发工具/SOP/90_交付打包/归档与存档.md)

# Archiving and Backups

> ← [90 · Delivery Packaging](../90-delivery-packaging.md). Trigger: archiving after delivery, or when the user asks to put a project away.

```
7z/zip directly into $ARCHIVE_ROOT/<个人存档|交付文件>/ → run 7z t on that copy → delete local → update ../../_服务器备份名册.md
```
`ARCHIVE_ROOT` is a setting in `kit.env` at the repository root (the archive directory; see `kit.env.example`); a local disk or a network share both work, and the rest of this page only refers to the variable.
**Before deleting the local source you must verify the copy in the archive directory**, not the source before packing.
**Division of labor**: packing, cleanup, Windows-specific checks, and unpack-and-compile verification can be dispatched to DSH; **the step of copying into `$ARCHIVE_ROOT/` is done by Claude** — in DSH's sandbox the archive directory is mounted read-only (on 09-22 it falsely reported on that basis “OS-level ro, can't change it even with privilege escalation”; on Claude's side `mount` is actually rw). For Windows usability criteria see Project B's 09-22 work log (illegal names / case-colliding names / path ≤259 / symlinks / file and git dependencies all 0, unpacked batchmode compile 0 errors).
Production results like menus, animators, and materials **have no second authoritative copy**.

**Archive with 7z/LZMA2, not zip/deflate** — measured on the same source it saves about **8.5%** more (deflate can do almost nothing for Unity projects).

**First distinguish what the output is for**: the previous sentence refers to archive files of project files; the full delivery package the client receives, “project zip + asset zip + notes”, still uses store ZIP per [90 step 5](../90-delivery-packaging.md). Placing it in the server's `交付文件/` directory does not automatically turn it into an archive file, and the extension must not be changed just because of the path. The 09-23 F08 dispatch confused the two; at acceptance it was changed back to the client ZIP; the 7z trial output is only an intermediate.

**Concurrency limit is set by memory, not CPU** — LZMA2 uses about **500 MB** per thread; thread count ≈ available memory ÷ 0.5 GB; going higher causes paging and throughput falls off a cliff.
