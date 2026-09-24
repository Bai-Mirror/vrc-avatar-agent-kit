> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/主理代理的交互规矩.md)

> ← [01 · Automation and parallelism](../01-automation-and-parallelism.md)

# Lead Agent Interaction Rules

> Moved on 2026-09-25 from the end of the 01 main page: these are rules for how the agent interacts with the user, unrelated to orchestration. Corresponds to mandatory rule 4 [Pacing] in the workspace `CLAUDE.md`.

## 1. Anything needing the user's decision always goes through AskUserQuestion; **do not ask in the body text and then end the turn** (corrected 2026-09-21)

**Trigger moment**: a round is done, you have accumulated one or two items “for the user to decide”, and you casually ask about them at the end of the reply.

Rule 4 states in black and white: “raise questions with AskUserQuestion and continue with the parts that do not depend on the answer; **do not ask in the body text and then end the turn**”,
yet I still did it: on whether to keep the three simultaneous `_MLBurstWeights`, I asked in the last paragraph of the body “should I go with this compromise?” and ended the turn.
**Consequence**: the user has to type out a paragraph to reply instead of clicking once; and such questions buried at the end of a long report are easily missed.

**Criterion (self-check)**: does my reply this round contain a question mark, “should I”, “what do you think”, “waiting for your word” or similar wording?
If so, that item **should be an AskUserQuestion option**, not a sentence in the body.

**Practice**:
- It is fine to accumulate them and raise them all at once at the end of the turn, but you **must use the tool**, with the options and their respective costs spelled out.
- After raising them, **continue with the parts that do not depend on the answer**; do not stop and wait.
- The body may **mention** “I have raised this to you as options”, but must not leave the question itself in the body.
