> 🌐 English translation · [中文原文](../../../../../../开发工具/SOP/问题定位/观测口径/渲染与取景/效果读不读得出来怎么量.md)

> ← [Rendering and framing](../rendering-and-framing.md) · [00 · Master table](../../../00-overview.md)

# How to measure "whether this effect reads" (2026-09-21, Project B, in-eye meteor)

**Trigger**: you made an effect layered over someone else's texture (in-eye effect, glowing pattern, decal),
and need to judge whether it can actually be seen, and which of several candidate approaches is stronger.

## 1 · First ask how much headroom the base color has left; don't start by tweaking brightness

Whether an additive-blended effect can be seen depends on **how far the base color is from 255**.

Project B measurement: the iris base color under the meteor had a **median luminance of 208/255** —
the peak of the additively drawn meteor had long since hit 255 and been clipped;
**measured with the brightness cap removed, pixel count and peak were exactly the same (733/100/116); raising brightness gained nothing.**

> **Checkable question**: what is the median luminance of the base color where I'm layering?
> If it's already ≥ 200, **the lightness route is dead** — stop tweaking Intensity / removing the cap / adding Bloom.

## 2 · With lightness maxed out, three routes remain: hue, chroma, form

Only by splitting the metric can you see which route works. Use **CIELAB**, and split the
ΔE (CIE76) of "effect pixel vs. its local background" into `ΔL*` (lightness) and a "chroma + hue" part:

```python
# effect pixels = pixels whose difference from the same frame "with the same settings but the effect off" is >10
# background    = mean of "non-effect" pixels in a 6–14 px square ring around each effect pixel (exclude the effect itself!)
dE = sqrt(sum((Lab_pixel - Lab_bg)**2))
dL = abs(L_pixel - L_bg)
dChromaHue = sqrt(max(dE**2 - dL**2, 0))
```

Project B measurements for seven meteor color schemes (same camera position, same frame):

| Color scheme | Median ΔE | of which ΔL* | of which chroma + hue | Peak ΔE after 4× downsampling |
|---|---|---|---|---|
| Blue-white (same tone as base) | 10.8–12.5 | 9.5–10.6 | **4.2** | 32.7 |
| Warm gold | 15.7 | 9.9 | 15.4 | 52.7 |
| Electric cyan | 16.5 | 10.7 | 14.7 | 44.1 |
| Warm gold + dark rim | **18.7** | 8.2 | **21.1** | **53.6** |

→ **When the base color is a low-saturation cool pink-violet, switching to a high-saturation warm color raises the hue channel from 4.2 to 21.1 (5×)**,
and peak ΔE at social viewing distance (downsampled) rises +64%. The lightness component barely changed — confirming item 1.

## 3 · Techniques like a "dark rim" that create contrast by darkening are often net-negative on their own

Adding opacity around a glowing object to darken the base intuitively raises contrast, but **what matters in measurement is how much of the object itself it eats**:
Project B's dark rim ate the trail's bright pixels from 832 down to 556, and median ΔE actually **dropped** from 12.5 to 10.8.
Only when stacked on top of a high-saturation hue did it turn positive (15.7 → 18.7).

Also, the third-party reviewer (gemini) gave an art criterion worth recording:
**"Nothing in nature glows with its own black outline"** — contrast propped up purely by a dark rim
will be perceived as a texture crack / scratched lens / a hair stuck on top, rather than as glow.

> **Trade-off**: the dark rim is only a **supporting actor**; the lead must be hue or form.
> Enlarging the dark rim alone to rescue visibility = turning the glowing object into a scratch.

## 3.5 · ⚠ d′ can't tell "a conspicuous signal" from "a conspicuous flaw"

**Trigger**: ranking two approaches by a salience metric (d′, ΔE, contrast) when one of them has a **dark rim / outline / hard edge**.

Counterexample measured in Project B on 2026-09-21: the old version with dark flanks did catch the eye more in **close-up**,
but a third-party blind test called it "an eyelash" — the human eye's edge detectors are extremely sensitive to high-frequency black-white boundaries;
**what it caught was the flaw, not the effect**. After removing the dark flanks d′ actually went up (33.62 vs 30.31),
and the blind test read it as a "glowing meteor" for the first time.

> **Checkable question**: the part of d′ that went up — was it contributed by **light**, or by **edges**?
> Break out `darkflux` (net darkening) separately — if it grows faster than `flux`, you're heading toward a flaw.
> Trade-off: **numeric criteria can only rule out "invisible"; they can't prove "looks good"**;
> form and categorization must rely on blind-test retelling (no hints; ask what they see at first glance);
> any of the words "hair / eyelash / scratch / crack / smudge" means fail, no matter how good the numbers are.

**Mechanism (from the third party, worth recording)**: eyelashes and scratches physically **must have a dark rim** —
only an occluder darkens the base. So whenever an effect carries its own dark rim, the brain tends to categorize it as "foreign object on top" rather than "light".
Conversely, pure additive color + an outer glow that widens toward the head has no negative-space dip and is directly categorized as an optical effect.

## 4 · Measure social viewing distance separately: recompute after downsampling

Good close-up ΔE doesn't mean others can see it. Standard practice: **downsample the render 4×** (760→190) and recompute peak ΔE.
Thin line-like effects get averaged away by anti-aliasing at this step; the downsampled number is "what others actually see".

> Related: [Taking photos of a part in the Editor](photographing-parts-in-editor.md) · [Zero and identical both ≠ pass](../zero-and-same-arent-pass.md)

## ⚠ Sign-off on macro renders doesn't count: re-measure at the real pixel size for the target viewing distance

**Trigger: before finalizing any "small-scale effect on the body" (in-eye, nails, earrings, tattoos).**

Real collision in Project B on 2026-09-21: the in-eye meteor lens passed agy review on 900×900 macro renders and GIFs framing a single eye, and the user approved it too;
after upload it was **completely invisible in game, even face to face**. Debugging ruled out every structural cause one by one (build, shader compilation,
AAO, vertex-color mask, UV, FX animation, LLC's MaterialPropertyBlock — all fine); finally a 24-frame time sweep measured it:
across the whole cycle **pixels with motion energy > 30 were only 0.71%**, max energy 147 (full scale 765). The effect was indeed rendering and moving;
it was just **too thin and too faint**.

### Criterion: do the viewing-distance math first, then talk about looks

```
角尺寸 = 物体尺寸 / 观看距离
屏幕像素 = 角尺寸(度) × (屏幕竖向像素 / 竖向FOV度数)
```
(angular size = object size / viewing distance; screen pixels = angular size (degrees) × (vertical screen pixels / vertical FOV in degrees))

VRChat face to face (about 0.5 m, 1080p, vertical FOV 60°): **≈18 px/degree**; a 12 mm iris ≈ **25 px**.
In a macro render the iris can occupy 500 px — **a 20× difference**. A 2 px-wide trail in macro is **0.1 px** in game.

**So: downsample the render to the real pixel size for the target viewing distance, then run the readability metrics; macro is only for tuning shape, never for sign-off.**

### What if it doesn't reach the bar
- Don't rely on "raising brightness" alone: on a high-lightness base, brightness hits the ceiling quickly (see the earlier sections on this page).
  Prioritize adding **size** (trail width, head size) and **frequency of appearance** (a transient effect shows nothing on screen most of the time).
- The finalized version must leave a comparison image **downsampled to the target viewing distance** in the delivery record, or the same mistake will happen again.

### Side note: transient effects can't be judged from a single frame
For effects like the meteor that "appear only a few times per cycle", a single frame most likely shows nothing.
Measuring it requires **a sweep over a fixed timeline** (`_TimeScale=0` + stepping `_TimeOffset` cell by cell), looking at the motion-energy map over the whole cycle.
