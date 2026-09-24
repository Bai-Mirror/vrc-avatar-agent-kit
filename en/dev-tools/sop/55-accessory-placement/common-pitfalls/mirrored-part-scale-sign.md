> 🌐 English translation · [中文原文](<../../../../../开发工具/SOP/55_配饰装位/通用坑/镜像件缩放符号.md>)

# Mirrored parts: the **sign** of the scale must be carried over from the prototype

> Subpage split out of [55 · Accessory placement / Common pitfalls](../common-pitfalls.md). Takes over the mirrored-parts section of the common pitfalls; it doesn't involve the placement algorithm, so it's a page of its own.

## Mirrored parts: the **sign** of the scale must be carried over from the prototype

Vendors' left/right paired pieces often mirror with `localScale = (-1, 1, 1)` (this project's left wrist cuff does).
Placement computes the **magnitude**; the sign has to be taken back from the prototype:

```csharp
var src = PrefabUtility.GetCorrespondingObjectFromSource(obj.gameObject) as GameObject;
Vector3 sgn = 符号(src != null ? src.transform.localScale : obj.localScale);
obj.localScale = new Vector3(s * sgn.x, s * sgn.y, s * sgn.z);
```

Writing `Vector3.one * s` wipes the mirroring — the left wrist wears the right wrist's piece, with ribbon winding direction and frill rotation all reversed.
**And**: when composing the rotation, local directions must also be run through the sign first (`Vector3.Scale(sgn, holeAxis)`),
otherwise the two constraints “where the hole axis points, where the decoration points” get solved reversed in the mirrored dimension.
Self-check criterion: the left and right pieces' `localPosition` should have opposite x signs, and `localEuler.y` should sum to 360°.
Measured before the fix: 57.27° / 46.05° (asymmetric); after the fix: 313.90° / 46.05° (exact mirror).
