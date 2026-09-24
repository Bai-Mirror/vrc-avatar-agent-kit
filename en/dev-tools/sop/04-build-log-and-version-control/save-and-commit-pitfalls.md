> 🌐 English translation · [中文原文](../../../../开发工具/SOP/04_施工记录与版本管理/落盘与提交的坑.md)

> ← [04 · Work log and version control](../04-build-log-and-version-control.md)

# Pitfalls in writing to disk and committing

This page collects "concrete incidents that keep recurring when writing logs / committing"; each entry comes with a trigger moment and a checkable question.

## When appending logs by script, don't use `%` for string formatting (2026-09-21)

**Trigger moment**: using python inside a bash heredoc to append a chunk of markdown to `_施工记录.md`, where it contains percent signs
(`5.47%`, a `p99` table, `100%` and the like).

`"...%s..." % ts` treats every `%` in the body as a format specifier → `TypeError: not enough arguments for format string`.
**The consequence is worse than the error itself**: in that round I had put the write and `ws_git.py commit` in the same command;
**the write failed but the commit still ran**, so the commit message described a log entry that didn't exist on disk at all.

**How to do it**: use placeholder replacement `body.replace("@TS@", ts)`, or an f-string (but likewise be careful with `{}` in f-strings).
**And split writing and committing into two steps**: write first, confirm it's on disk with `grep`, then commit.
> **Checkable question**: is this command "generate content + commit" chained together? Is there a step in between that verifies it landed on disk?


## When creating a new **directory**, the directory's own `.meta` must also be committed (2026-09-21, third time tripping on .meta)

**Trigger moment**: creating one or more new directory levels under `Assets/` for new assets.

The first two times a file's `.meta` was missed (`Foo_heels50.anim.meta`, `CommC_Fix60V.cs.meta`);
this time it was a **directory's** `.meta`: I created `Assets/Nymiro/MeteorLens/`; the inner `MeteorLens.meta` and
`MeteorLens.shader.meta` were both committed, **but the outermost `Assets/Nymiro.meta` was missed**.
Unity also generates a `.meta` for **every directory**; without it, when someone else pulls, that directory level gets a newly issued guid.

**How to do it**: before committing new assets, run
```bash
git status --porcelain <工程> | grep '\.meta$'
```
and include **all** the listed files; pay special attention that **every newly created directory level** in the path has its own `.meta`.
> **Checkable question**: how many directory levels did I create this time? Is each level's `.meta` in the staging area?

## Telling DSH in a task brief to commit by "directory" sweeps in files that concurrent tasks are writing (09-22 H-06)

**Trigger**: two or more DSH dispatched at the same time, and they write to the same directory (e.g. in `开发工具/通用工具/部件图鉴/`, one changes the lookup script and another changes the capture tool).
**Question**: does the `ws_git.py commit -- <路径>` I wrote include a directory? Is any other task writing to that directory right now?
**How to do it**: the commit line in the task brief **names only files**, not directories; if you really must name a directory, write "before committing run `git status -- <目录>`; don't include files you didn't change". On 09-22, DSH committing by directory swept `PartAtlasCapture.cs`, written by the capture task 30 seconds earlier, into `32b19400`; after its self-check it did `reset --soft` and recommitted as `db0fe8c2`.

- **09-22 repeat offense**: the python heredoc that edited the master ledger had an indentation error and didn't run, and the `ws_git.py commit` chained after it with `;` still ran, committing only the dispatch log while the commit message said "H-03 acceptance complete" (edf68893, corrected by 812a6578). **Always use `&&` between an edit command and a commit**; have the edit script `print` a confirmation value at the end, and see it before committing.

## Committing by name can also sweep in files someone else staged — an implementation pitfall in ws_git (fixed 09-22)

**Trigger**: during parallel dispatch, a commit made with `ws_git.py commit -m … -- <我的文件>` contains extra files belonging to someone else.
**Cause**: the old implementation was "`git add -- <点名路径>` → `git commit` (the whole staging area)"; files DSH had already `git add`-ed were in the staging area and got committed along with it (09-22 49384441 took two L5-4c files with it). The "commit by directory" entry above is just one trigger of the same pitfall.
**Fix** (ws_git 09-22): when paths are named, take only the staged files within the named paths and use `git commit -- <这些文件>` (--only semantics), leaving others' staged files in the staging area; naming an ignored png only warns rather than aborting; when `index.lock` is held, retry 10 times.
**Checkable question**: does `git show --stat HEAD` contain any files I didn't name? If so, note in the work log "commit X also picked up whose which files"; don't reset other people's work.

## With an unquoted heredoc, backticks in the body get executed by the shell (09-22)
**Trigger**: the body written with `cat >> 记录.md <<EOF` (unquoted, in order to interpolate the `$T` time) contains backtick code such as `` `路径` ``.
**Consequence**: the backticks are executed as command substitution and the text is swallowed (on 09-22 in Project A's log, the two names `TimerMat` and `Advanced/AvatarHight` vanished, and the screen only reported "command not found").
**How to do it**: always use `<<'EOF'` (quoted, written verbatim); write a placeholder for the timestamp first, then use `sed` to replace it with the measured value from `date +%H:%M`; or write the file with python. After writing, `tail` it to read back once.

## After `git mv`, naming the old path makes `ws_git.py commit` abort entirely (09-22 W4)
**Trigger**: the task first moved files with `git mv` (W4 merged `_派工/*` into a new directory), and at commit time also wrote the old path into `ws_git.py commit -- …`.
**Symptom**: `git add -A -- <路径>` reports "pathspec did not match" for the old path that no longer exists on disk and aborts, committing only files that were already staged (`c0429fdc` carried only 5 new files); DSH only made it complete with a second commit (`1a9c67fe`), and in the meantime other parallel commits had landed, so it couldn't be merged by rebase.
**How to do it**: in mv scenarios name only the **new path**; the deletion of the old path is already staged by `git mv` and will be carried along with `--only`; before committing, check with `git status --porcelain -- <旧目录> <新目录>` that the `R`/`D` lines are all in the staging area.
> **Checkable question**: among the paths I named, are there any that no longer exist on disk right now?
