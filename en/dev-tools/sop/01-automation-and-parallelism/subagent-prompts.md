> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/子代理提示词.md)

> ← [Step templates and hard gates](step-templates-and-hard-gates.md) · [Subagent dispatch](subagent-dispatch.md) · [01 · Automation and parallelism](../01-automation-and-parallelism.md)

# How to Write Subagent Prompts · When to Dispatch

Everything on this page comes from measurements over **one entire order, Project C, on 2026-09-06/07**: about 20 dispatch routes,
three models Haiku / Sonnet / Fable, about 5M subagent tokens in total. There is concrete evidence of both successes and failures.

**The only benefit of dispatching a subagent is context isolation**: you pay for one task description + one report, and the intermediate process does not enter the main context.
Every trade-off follows from this.

---

## 1. When to dispatch

### Dispatch (all three must hold)

| Condition | Why |
|---|---|
| **Reaching a conclusion requires going through many files** | This kind of task consumes exactly the context the main agent should least spend (reading SOP pages, traversing directories, getting bitten once by path encoding and switching tools, catching a big blob of json) |
| **A closed-form criterion can be written into the task brief** | Without a criterion there is no acceptance; it just transfers uncertainty elsewhere rather than digesting it |
| **Actions are reversible or read-only** | Do irreversible ones yourself |

Measured: the three most expensive routes (reference-image interpretation 304k / broken-reference classification 289k / blend-shape enumeration 278k) **were all of the first kind**.
Their output compressed into 20–30-line reports, giving the greatest isolation benefit.

### ⚠ Before dispatching, ask: **is there already a shorter path for this task?**

**This was the most expensive lesson of this order.** “For each of ten blend shapes, does it move the outer eye corner up or down” —

| Route | Cost |
|---|---|
| Dispatch a subagent + 11 Unity batchmode renders + cropping + sending for review | **237k tokens, twenty-plus minutes**, and the output was still “descriptions from looking at images”, one of which still conflicts with the numeric conclusion |
| Blender headless reading vertex offsets | **4.4 seconds**, output is numbers |

**Criterion**: first ask “is the answer to this question a **geometric quantity** or a **perceived look**?” —
geometric quantities have closed-form solutions; do not send someone to look at images. See the top of [30 face sculpting](../30-face-sculpt.md).

### Do not dispatch

- **Irreversible actions** — GUID fixes, baking, packaging, deleting files
- **Intermediate evidence the main agent needs later** — e.g. an index table of 90 blend shapes
- **Very short tasks** — description cost > benefit. On this order the four task descriptions totaled about 230 lines of output tokens, all produced by the main agent
- **Needs back-and-forth confirmation with the user** — subagents cannot ask people

### On serial resources, fan-out saves **context**, not **time**

Unity is a single instance and MCP can only be serial. So steps that touch the project **cannot truly run in parallel**.
The only true parallelism on this order was running “design tasks that do not occupy Unity” (recoloring schemes, face-sculpting candidate tables) alongside “fitting that occupies Unity”.
**Do not expect fan-out to compress wall-clock time.**

---

## 2. The eight-section structure of a prompt

Every successful dispatch on this order had this shape. **The order matters**: context before actions, facts before criteria.

```markdown
1. One sentence: what this route is responsible for, which step of the process, whether prerequisites are done
2. [Must read before starting] list SOP pages and memory files in order, explicitly saying "do not skip"
3. [Verified facts] — "use directly, do not re-verify"
4. ⚠ [Measured pitfalls] — specific, with numbers
5. [Post-condition criteria table] expected | how to read
6. [STOP] explicit list + **why for each item**
7. ⚠ [Reporting discipline] — **with specific instances of previous fabrications**
8. [Report] format + **line limit**
```

### Trade-offs of each section

**② Must-read list**: without it, it explores on its own and hits known pitfalls; with too much, it spends its budget on reading.
**Criterion**: list only “what this step will use”; do not dump the whole SOP on it.

**③ Verified facts**: the section with the greatest measured benefit on this order. Given the ready-made menu structure and scene state for stage 60,
it started work immediately; the routes without it each spent 10–20 calls re-exploring.
⚠ **Cost**: **facts you write wrongly will be executed as written, not questioned.**
This order stumbled here twice: the “brow region y300–380” I gave was actually the forehead (the agent complied and got a meaningless 0);
the `-nographics` I gave made two routes render blank images. **Numbers in the task brief must be ones you have verified.**

**⑥ STOP**: writing only “when to stop” is not enough; **write “why”**.
Measured: the probe route hit a boundary I had not anticipated (an item under judgment was judged “can't tell” rather than “lowered”),
and **correctly judged that the literal condition was not triggered, yet still reported it truthfully** — it navigated correctly by understanding intent, not by matching the literal text.

**⑧ Line limit**: **this is the key knob of the whole thing.** Without a limit, the subagent pastes the entire report back, which amounts to no isolation.
On this order it was uniformly 20–30 lines, and all complied.

---

## 3. Four measured-effective ways of writing

### 1. Write **specific instances of previous fabrications** into “reporting discipline”

Abstractly writing “do not fabricate” is ineffective. Change it to:

> The previous subagent reported “the two zips have identical content” — it never opened the zips; that was fabricated, and wrong (they differ by 376 KB).
> - Listing a directory → can only yield “which files exist, how big”
> - Unpacking → only then can yield “what is inside”
> **Do not draw that conclusion without performing that action**; write “unverified”.

**After adding this, subsequent routes all proactively marked uncertain items as “unverified”** — an observable behavior change.

### 2. When sending Haiku, **hard-code which kinds of judgment are forbidden**

For each conclusion ask “for this conclusion to hold, what action must it have **performed**?” If the action exceeds its tool capability, forbid it.
**Asymmetric cost**: forbidding too much costs one more round (small) · forbidding too little lets it fabricate conclusions that you accept directly (large) → **err on forbidding too much**.

### 3. Explicitly write “after starting, you must poll and wait for it to exit before reading the results”

**Subagents do not wait for background tasks** (reproduced 3/3 on this order): after starting batchmode they hand back the turn. This is not laziness; it is turn semantics.
All three routes without this sentence handed back midway; the one route with it correctly waited until the end.
**And the main agent must verify the final state itself** — do not accept “still running”.

### 4. **After STOP, narrow the scope and re-dispatch; do not simply redo it**

The fox ears on this order took three rounds: `55 placement` → `diagnosis` → `precise fix`, **each round with a narrower task surface**.
The third round succeeded because I **wrote the fileID we had found directly into the task brief**.

> **Rule**: when a subagent STOPs, what it hands back is “a problem”, not “a failure”.
> The main agent's job is to **turn the problem into a narrower task**, not to try again with a different model.

---

## 4. Three acceptance rules

1. **Any “conclusion that could not be reached without performing that action” is not accepted** —
   how to tell: check whether its tool calls can support the conclusion
2. **When it reports “the X you gave has a problem”, first assume it is right and then verify** —
   it has no reason to fabricate a conclusion that makes things harder for itself. Conversely, it is when it reports “I'm done, no problems” that you should review most carefully
3. **Criteria like counting “how many” should count by structure, not by string** —
   I counted the menu controls as 10 (the regex also counted the nested `name:` in parameter blocks); recounting by control structure gave the correct 7

---

## 5. Cost observations (this order, for estimation)

| Task type | Typical tokens | Tool calls |
|---|---|---|
| Pure enumeration (reconciling directory listings, Haiku) | 85k | 14 |
| Aesthetic design (Fable, no file browsing) | 158k–406k | 14–78 |
| Going through many files to reach a conclusion (Sonnet) | 280k–550k | 64–218 |

**Fable's tool-call count is clearly lower** — aesthetic tasks do not need file browsing to begin with; it spends its budget on judgment rather than searching.

⚠ **This is not a strictly controlled experiment**: there is no control group of “doing the same thing again in a single context”,
so only directional conclusions can be drawn. To get multiples, pick a specific stage and do an A/B.
