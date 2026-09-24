> ← [本机(Linux) Linux 环境](../B850_Linux环境.md) · [写脚本的坑](写脚本的坑.md)

# Blender 脚本的坑（bpy 5.2 / 无头渲染 / 几何量）

2026-09-25 从「写脚本的坑」页尾的附录移来。共同点同那页：脚本不报错，读数却不是你以为的那个量。

## 1 · Blender 5.2 的骨骼 API（09-22 舌钉链 L5-1，DSH 报）

- `bpy.types.Bone` **已没有 `roll`**：要在编辑模式读 `EditBone.roll`，或由 `bone.matrix_local` 反算。
- `Bone.x_axis/y_axis/z_axis` 实测是**父骨空间**（同一世界朝向，根骨与子骨读数不同）。核「骨的局部轴朝世界某轴」一律用 `bone.matrix_local.col[i]`，否则判据会被静默地自证成立。
**可查问句**：我读的骨轴/roll 是哪个空间、哪个版本的属性？在 5.2 上跑过一次反例吗？

## 2 · 无头 EEVEE 的假警报（09-22 L5-4f）
`blender --background` 渲 EEVEE 会打 `amdgpu_device_initialize failed / failed to load driver: radeonsi`，小物体在大画幅里时整帧均值看着像全背景，容易误判「EEVEE 不可用」。判据用**非背景像素计数**（或遮罩渲量物体像素宽），实测照样渲得出来。

## 3 · 几何脚本的量纲、精度与判据坑（09-22 舌钉链 L5-5、09-23 L5-7）
- `mathutils.Vector` 是 **float32**：在 Blender 外用 numpy float64 重写同一算法，逐点会差 ~1e-6；要「逐点一致」就回 Blender 里用 mathutils 跑，或按对方存盘精度（如 round 8 位）比。
- `BVHTree.find_nearest/ray_cast` 返回**场景单位**（本工作区的 .blend 多为米）：写报告前 ×1000，否则「0.0039 mm」其实是 3.9 mm。
- 开口子网格（从大网格里抠出来的一块）上用法线符号判「穿进去没有」会**假负**：边附近 signed 为负、实际分离 1.5 mm。穿透一律用 `BVHTree.overlap` 判，signed 只作深度诊断。
- 只转根骨＋平移一根子骨的姿态族里，同一骨刚性驱动的两块几何相对距离恒定——扫掠读数不随参数变化时先查这条，不是脚本坏了。
- 「单个三角面法线」在窄化/剪切下给假转角（09-23 L5-7：8.27° vs 邻域加权 0.47°）→ 曲面法线判据用邻域面积加权。
