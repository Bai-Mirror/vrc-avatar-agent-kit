> 🌐 English translation · [中文原文](../../../../开发工具/SOP/30_捏脸/硬规矩的依据与例外.md)

# The basis for the hard rule and its exceptions (adjust only vendor blend shapes)

> A subpage split out of [`30-face-sculpt.md`](../30-face-sculpt.md). It takes over the measured basis from the "hard rule" block, the downgrade note on facial-feature scaling geometry, and the exception for closed-form-transform custom keys; the allowed/forbidden comparison and the extrapolation rules remain on the main page.

> Set by the author on 2026-09-06, based on one measured trial: having Opus sculpt the face in Blender by **directly moving the mesh**
> **produced something not remotely humanoid**. The conclusion isn't that the prompt was badly written —
> **the model's representation of 3D space is itself unreliable, and no amount of detailed instruction can rescue it.**
> ⚠ This **downgrades** the [Facial-feature scaling geometry](facial-feature-scaling-geometry.md) route (geometric scaling of layered cards):
> it counts as "sculpting by moving the mesh" and is **not used by default**. It is enabled only when the vendor blend shapes genuinely lack the needed direction
> and the user explicitly agrees, and the user must judge the shape.
> ### Exception: custom keys from **closed-form transforms** (user agreed 2026-09-07; used once)
>
> What's forbidden is "sculpting vertices by feel", not "computing displacements by formula". When **the vendor keys genuinely lack the needed direction (with measured evidence)
> + the user explicitly agrees**, you may build a custom key. That's how the outer eye corners were "rotated flat" in this order:
> the vendor key ceiling was −13%, and the custom closed-form rotation key achieved −36%.
> **Layered-card base avatars must be rotated around the depth axis** (the depth component of the displacement is always 0, so layer spacing stays unchanged).
> The four rules and acceptance criteria → [Route selection and aesthetic calibration](approach-selection-and-aesthetic-calibration.md) §2.
