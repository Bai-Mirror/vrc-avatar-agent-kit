> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/DSH静默失败.md)

# DSH Silent Failures (Six Items)

> Moved down from [DSH dispatch](dsh-delegation.md). **What they have in common: none of them report errors**; the output looks completely normal,
> so “did it run through” cannot tell you; they must be caught by after-the-fact verification. `dsh_task.js` has turned all six into automatic criteria or fixed them outright.
> Also: in the DSH bash sandbox, `/tmp` is a fresh empty directory for every command; whatever is written there is gone by the next command, and it will still report PASS → item 3 of [Sandbox limits](dsh-capability-and-modification/sandbox-limits.md).

| # | Pitfall | Symptom | Criterion | Automated |
|---|---|---|---|---|
| ① | A non-vision alias receiving images **fabricates answers** | The answer is specific, tidy, and entirely made up (measured: 23 dots answered as 22, all six hex values wrong) | Do not look at answer quality; check whether the session log has `read_image` | `--images` refuses aliases not on the vision whitelist |
| ② | Images get in via `read_image`, **not as attachments** | It answers anyway without having read the images | **Count and paths** of `read_image` in `tool/call` | `--images` checks image by image; one missing → FAIL |
| ③ | Chinese paths **get mangled** through cmd.exe (Windows only) | It asks back “please tell me which images to read” — **looks like disobedience, actually the arguments never arrived** | Whether the Chinese in the original `user/message` text in the session log is garbled | Call `lib/bin.js` directly, not through the `.cmd` shim |
| ④ | Old API key left in the process environment | Reports `Insufficient Balance`, while curl with the same new key works fully | `process.env.DEEPSEEK_API_KEY` non-empty in the dispatching shell | Delete that environment variable before spawn |
| ⑤ | A **rejected** `read_image` also counts as “read” | Verification says “image reads 3/3 PASS”, while the model saw none | Look up `isError` of `tool/result` by `callId` | Rejected ones are not counted; direct FAIL |
| ⑥ | `--brief` + concurrency ⇒ verification claims the wrong session | Several routes report the same session id, good answers judged FAIL | FAIL reason is “wrap-up is not completed” while stdout has a complete answer | Embed a one-time nonce at the end of the task for claiming |

## ① A non-vision alias receiving images fabricates answers

**Symptom**: a perfectly normal-looking answer, specific numbers, tidy format, **entirely made up**.

**Measured** (2026-09-08, `deepseek-v4-flash`):
- Fed an image of 23 dots and asked to count → answered **22** (a convincingly plausible error)
- Fed six color swatches with known hex values and asked to read them → all six hex values **fabricated** (unrelated to the ground truth)
- The `prompt_tokens` of the two calls were **20 and 42** — the images never entered the request

**Mechanism**: DeepSeek's non-vision models do not error on `image_url` content blocks; they just drop them.
This is yet another instance of “[absence must not silently become a value](../troubleshooting/observation-criteria.md)”:
“did not see the image” was read as “there is nothing in the image”, and then the model filled the gap with priors.

**Criterion**: do not look at answer quality (you cannot tell); check **whether the session log has `read_image` calls**.
`dsh_task.js` now refuses `--images` with non-`vision` aliases and checks the read path of each image.

**Asymmetric cost**: giving one image to a non-vision alias by mistake is one hallucination, so the gate hard-blocks on “with images ⇒ must be `vision`” rather than relying on the dispatcher to remember.
The current alias table (plain text defaults to `flash`, with images `vision`, both the same V4.1-Flash underneath) is in section 1 of [DSH model and vision capability](dsh-model-and-vision-capability.md);
the old practice from 09-08 of “setting the default model to `deepseek-v4-flash-vision-exp`” has been superseded by that page's change log.

## ② In headless mode images get in via `read_image`, not as attachments

**Why it is easy to get wrong**: DSH's Web UI has an attachment feature (`dsh-attachment`),
and the adapter also supports uploading images via the Files API, so it seems “feeding images” should go through attachments.
**But the headless entry point is only a single string task**, with no attachment channel —
images can only be read from disk by the agent itself calling the `read_image` tool.

**Corollary**: the criterion for “did it really look at the images” is **not the token count** (not visible from the headless side),
but the **number of calls and argument paths** of `read_image` in `tool/call`.

`dsh_task.js --images` automatically prepends mandatory per-image read instructions to the task brief, checks each image after the run, and judges FAIL if one is missing.

## ③ Chinese paths get mangled through cmd.exe (Windows only; this machine (Linux)/Linux is unaffected, but do not revert to shell invocation)

**The symptom is extremely misleading**: DSH replies
“Please tell me explicitly which images need to be read; you can provide the image file paths directly……”
It looks like it is disobeying, lacks permission, or the prompt was unclear —
**in fact the arguments never reached it at all**.

**Mechanism**: `dsh` is a `.cmd` shim. Calling it with `spawn(..., {shell: true})` goes through `cmd.exe`,
and the Windows default code page (GBK on that machine) mangles non-ASCII characters in the task text and paths.
This project's paths are almost all Chinese (`工程C/_渲染/_眼色三档对照.png`), so it is bound to hit.

**Measured**: 2026-09-08, dispatches with Chinese paths **failed to read images 100% of the time**;
after changing to `spawn(process.execPath, [bin.js, ...], {shell: false})` it passed on the first try, all correct in 9.5 seconds.

**Criterion**: when you see DSH asking back “which images to read / file not found”,
**first suspect the arguments did not arrive; do not rush to change the prompt**. How to verify: check the original text of `user/message` in the session log,
and whether the Chinese is garbled.

**Fixed**: `dsh_task.js` calls `lib/bin.js` directly, not through the shim.
⚠ When writing an invocation by hand, do not revert to the `dsh xxx` style.

## ④ Old API key left in the **process environment** overrides the credentials file

**Symptom**: DSH reports `QUOTA: Insufficient Balance` every time, while direct curl with the same new key works fully —
including a large prompt (25K), `max_tokens: 256000`, `reasoning_effort: high`, streaming; **every combination works**,
and `/user/balance` also shows a positive balance, `is_available: true`.

**True cause**: the adapter's credential resolution chain is “`ctx.credentials` → trusted environment-variable layer”.
As long as `DEEPSEEK_API_KEY` is in the environment, it may override the correct key in `~/.dsh/.credentials.yaml`.
This time the leftover was an **already-invalid old key** — lesson: first confirm which key is actually in effect in the process (see the criterion below), before looking at balance.

⚠ **Deleting User / Machine-level environment variables has no effect on processes already running** —
it is inherited all the way down to every child process you start from that process. I really did delete both levels at the time,
but the `Process`-level copy was still there, so DSH kept working with the invalid old key.

**Corroboration**: looking at the usage export per key, the new key showed only my few direct curl tests;
**the dispatched calls were actually all recorded on the old key** — when old and new keys are mixed, checking usage per key pinpoints which one is doing the work.
The phenomenon “why does the new key have almost no usage” is itself a clue.

**Criterion** (check this first when suspecting a credentials problem, not the balance):
```bash
node -e "console.log(process.env.DEEPSEEK_API_KEY)"   # run in **the shell that dispatches**
```
Non-empty output whose last digits are not the key you think → that is it.

**Fixed**: `dsh_task.js` deletes `DEEPSEEK_API_KEY` from env before spawning the child process,
forcing use of the credentials file. **Do the same when writing dsh invocations by hand.**

**A more general lesson**: when rotating keys, “setting the new one” is only half; **the other half is confirming the old one is gone at every layer** —
file, User level, Machine level, and **processes already running**. Missing one layer gives you a situation where
“the configuration looks all correct but the behavior is wrong”, and the error message (insufficient balance) points in a completely wrong direction.

> The following two sections were moved down from [DSH dispatch](dsh-delegation.md) on 2026-09-18.

## ⑤ A **rejected** `read_image` also counts as “read” (added 2026-09-10)

`--images` verification originally only counted the number of `read_image` **tool/call entries** in the session log, without looking at results.
On the day the v4.1 preview expired, all three calls were rejected, yet there were still three calls ⇒ verification printed **“image reads 3/3” and judged ✓ PASS**,
while the model saw none of the images. (It honestly wrote in its answer “I was unable to see these three images”;
otherwise this answer would have been accepted as a normal review.)

A related lesson: **the same model's first dispatch timed out at 900 seconds with zero output**, and at the time it was misjudged as “it disobeyed
and went off to write a pixel-analysis script” — only reviewing the session log revealed that those three `read_image` calls had likewise been rejected;
it was **using python to make up for a capability it did not have**. ⇒ On timeout, check tool results first; do not first blame the model for wandering.

⇒ `dsh_task.js` now looks up `isError` of `tool/result` by `callId`;
rejected ones are not counted in “image reads N/M” and are judged FAIL directly. Regression-verified: the vision-exp run passed 3/3,
and both `expires-on-0910` runs FAILed.
⚠ Correction 09-11: those two FAILs were because **the alias did not declare image input**, not because the model lacked vision capability;
  see the change log at the end of [DSH model and vision capability](dsh-model-and-vision-capability.md). This gate itself must remain — it blocks a pattern, not a particular model.
**Lesson: model capabilities expire; historical conclusions in documents cannot serve as admission criteria — run it for real before adding to the whitelist.**

## ⑥ `--brief` + concurrency ⇒ verification attributes to the wrong session (fixed 2026-09-11)

The fingerprint for claiming a session used to be `task.slice(0, 120)`. But **`--brief` prepends the same
fixed header to every route's task** (“Read this first — this project's fact quick-reference file”…), which is well over 120 characters
⇒ **the fingerprints of all routes were identical**. When dispatching 5 routes concurrently, all five processes claimed the same session,
and the model / tools / wrap-up reported in the verification blocks all belonged to someone else.

**Measured symptom**: three routes reported the same `session id`, all judged `✗ FAIL` (wrap-up `?`),
**while all three answers were actually good and each on topic** — a classic case of “verification breaks before the task does”.
The danger lies in its direction: **misjudging good results as bad** easily leads people to re-run needlessly (paying twice).

⇒ Now a one-time nonce (`dsh-task-<pid>-<base36 time>`) is embedded at the end of the task, and claiming is done by it.
   ⚠ The nonce must be spliced into the task **before** spawn, otherwise the child process never sees it.
   Regression-verified: two concurrent routes + sharing the same `--brief` header, each claimed a different session, both PASS.

**An accompanying interpretation rule**: when verification judges FAIL, first look at the **reason** for the FAIL.
“Wrap-up is not completed” + stdout has a complete answer ⇒ most likely the wrong session was claimed, not a task failure.
What really needs re-running is when stdout is empty or the answer is off-topic.

---

Related: [DSH dispatch](dsh-delegation.md), [Troubleshooting/observation definitions](../troubleshooting/observation-criteria.md), [Troubleshooting/troubleshooting record procedure](../troubleshooting/troubleshooting-log-procedure.md).
