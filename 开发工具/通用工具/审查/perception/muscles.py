# -*- coding: utf-8 -*-
"""muscles.py — 人形肌肉固定表与姿势元数据（T-26 / 04 第一期开工清单）。
【项目沉淀】通用工具
适用素体：无关
相关素材：无（纯数据表）
工具链　：Python 3（离线）
可复用性：★★★ 换个单子直接能用
用途　　：人形 95 肌肉固定顺序表与部位映射、姿势元数据；pose_frames.py 依赖它。


职责（不读磁盘，纯数据 + 纯函数；`pose_frames.py` 依赖本文件）：
  1. `MUSCLE_NAMES`：`UnityEngine.HumanTrait.MuscleName` 的 **95** 条固定顺序表。
     `HumanPose.muscles[95]` / `HumanPoseHandler.SetHumanPose` 用它，顺序错一位整套失效。
  2. `clip_attr_to_muscle`：把 `.anim` 的 `m_FloatCurves[].attribute` 名翻成表内名。
     身体类名与表内同名；手指类 Unity 在 clip 里写 `LeftHand.Index.1 Stretched`，
     而 HumanTrait 叫 `Left Index 1 Stretched`（03 F16），显式映射。
  3. `MUSCLE_REGIONS`：肌肉 → 部位名（`moved_regions` 用；离线算不出骨骼旋转差，I10）。
  4. `JOINT_SCANS` / `COMBOS`：库 B 的 7 个左右分关节组 × 4 档 × 左右 + 脊柱 4 档 + 6 组合，
     合计 **66** 条（03 §8.1）。
  5. `POSE_META` / `builtin_params_for`：库 A/C 已知姿势的内置参数（`Seated/Upright/Grounded/AFK/VelocityZ`）。

95 名顺序的出处与自证
---------------------
本机 Unity 2022.3.22f1。`HumanTrait.MuscleName` 由原生代码返回，C# 侧拿不到；
但 `.anim` 的 `m_ClipBindingConstant.genericBindings[].attribute` 对肌肉绑定 = `肌肉序号 + 42`
（根曲线是另一段 7..13、手足 T/Q 是 14..41、其它绑定是 CRC 大数）。用 79 个 SDK proxy clip
逐一核对：把 `m_FloatCurves` 的名字按本表查序号、+42，得到的集合与 `genericBindings` 的
{42..136} 子集**逐 clip 完全相等**（`pose_frames.py --selftest` 会重跑这条断言）。
表内容与 Kafe_CVR_Mods `GrabbyBones/MuscleData.cs` 一致；手指段 1,Spread,2,3 的顺序由
`HumanBodyBones`（Proximal/Intermediate/Distal）× `MuscleFromBone` 的 DoF 顺序决定。

    python3 muscles.py --selftest
"""
from __future__ import annotations

import sys
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 1) 95 名固定表（HumanTrait.MuscleName 顺序）
# ---------------------------------------------------------------------------
MUSCLE_NAMES: List[str] = [
    # 躯干
    "Spine Front-Back", "Spine Left-Right", "Spine Twist Left-Right",
    "Chest Front-Back", "Chest Left-Right", "Chest Twist Left-Right",
    "UpperChest Front-Back", "UpperChest Left-Right", "UpperChest Twist Left-Right",
    "Neck Nod Down-Up", "Neck Tilt Left-Right", "Neck Turn Left-Right",
    "Head Nod Down-Up", "Head Tilt Left-Right", "Head Turn Left-Right",
    "Left Eye Down-Up", "Left Eye In-Out", "Right Eye Down-Up", "Right Eye In-Out",
    "Jaw Close", "Jaw Left-Right",
    # 左腿
    "Left Upper Leg Front-Back", "Left Upper Leg In-Out", "Left Upper Leg Twist In-Out",
    "Left Lower Leg Stretch", "Left Lower Leg Twist In-Out",
    "Left Foot Up-Down", "Left Foot Twist In-Out", "Left Toes Up-Down",
    # 右腿
    "Right Upper Leg Front-Back", "Right Upper Leg In-Out", "Right Upper Leg Twist In-Out",
    "Right Lower Leg Stretch", "Right Lower Leg Twist In-Out",
    "Right Foot Up-Down", "Right Foot Twist In-Out", "Right Toes Up-Down",
    # 左臂
    "Left Shoulder Down-Up", "Left Shoulder Front-Back",
    "Left Arm Down-Up", "Left Arm Front-Back", "Left Arm Twist In-Out",
    "Left Forearm Stretch", "Left Forearm Twist In-Out",
    "Left Hand Down-Up", "Left Hand In-Out",
    # 右臂
    "Right Shoulder Down-Up", "Right Shoulder Front-Back",
    "Right Arm Down-Up", "Right Arm Front-Back", "Right Arm Twist In-Out",
    "Right Forearm Stretch", "Right Forearm Twist In-Out",
    "Right Hand Down-Up", "Right Hand In-Out",
    # 左手 4 指 × (1 Stretched, Spread, 2 Stretched, 3 Stretched)
    "Left Thumb 1 Stretched", "Left Thumb Spread",
    "Left Thumb 2 Stretched", "Left Thumb 3 Stretched",
    "Left Index 1 Stretched", "Left Index Spread",
    "Left Index 2 Stretched", "Left Index 3 Stretched",
    "Left Middle 1 Stretched", "Left Middle Spread",
    "Left Middle 2 Stretched", "Left Middle 3 Stretched",
    "Left Ring 1 Stretched", "Left Ring Spread",
    "Left Ring 2 Stretched", "Left Ring 3 Stretched",
    "Left Little 1 Stretched", "Left Little Spread",
    "Left Little 2 Stretched", "Left Little 3 Stretched",
    # 右手
    "Right Thumb 1 Stretched", "Right Thumb Spread",
    "Right Thumb 2 Stretched", "Right Thumb 3 Stretched",
    "Right Index 1 Stretched", "Right Index Spread",
    "Right Index 2 Stretched", "Right Index 3 Stretched",
    "Right Middle 1 Stretched", "Right Middle Spread",
    "Right Middle 2 Stretched", "Right Middle 3 Stretched",
    "Right Ring 1 Stretched", "Right Ring Spread",
    "Right Ring 2 Stretched", "Right Ring 3 Stretched",
    "Right Little 1 Stretched", "Right Little Spread",
    "Right Little 2 Stretched", "Right Little 3 Stretched",
]

MUSCLE_INDEX: Dict[str, int] = {n: i for i, n in enumerate(MUSCLE_NAMES)}
MUSCLE_COUNT = len(MUSCLE_NAMES)

# 手指肌肉（填缺值时取 proxy_hands_idle，不填 0；03 M1）
FINGER_MUSCLES = set(MUSCLE_NAMES[55:95])
BODY_MUSCLES = set(MUSCLE_NAMES[:55])

# clip genericBindings 里肌肉绑定的 attribute 偏移（见模块 docstring）
CLIP_ATTR_MUSCLE_OFFSET = 42
# 根曲线/手足 T/Q 占用的 attribute 段，用于核对条数
ROOT_ATTR_RANGE = (7, 13)
LIMB_TQ_ATTR_RANGE = (14, 41)

_FINGER_RE = None


def _finger_re():
    global _FINGER_RE
    if _FINGER_RE is None:
        import re
        _FINGER_RE = re.compile(
            r"^(Left|Right)Hand\.(Thumb|Index|Middle|Ring|Little)\.(.+)$")
    return _FINGER_RE


# 非 HumanTrait 拼法的兼容写法（少数工程/厂商 clip 可能已用表内名或其它分隔）
_ALIASES = {
    "Upper Chest Front-Back": "UpperChest Front-Back",
    "Upper Chest Left-Right": "UpperChest Left-Right",
    "Upper Chest Twist Left-Right": "UpperChest Twist Left-Right",
}


def clip_attr_to_muscle(attr: str) -> Optional[str]:
    """`.anim` 曲线属性名 → HumanTrait 肌肉名；不是肌肉返回 None（RootT/RootQ/形态键等）。"""
    if not attr:
        return None
    if attr in MUSCLE_INDEX:
        return attr
    if attr in _ALIASES:
        return _ALIASES[attr]
    m = _finger_re().match(attr)
    if m:
        name = "%s %s %s" % (m.group(1), m.group(2), m.group(3))
        if name in MUSCLE_INDEX:
            return name
        # 极少数写 `LeftHand.Index.1`（无 Stretched）——补后缀再试
        name2 = "%s %s %s Stretched" % (m.group(1), m.group(2), m.group(3))
        if name2 in MUSCLE_INDEX:
            return name2
    # `Left Index 1 Stretched` 这类已经合格但带 `Hand` 的写法
    for pref in ("LeftHand.", "RightHand."):
        if attr.startswith(pref):
            cand = attr.replace(pref, pref[:-1] + " ", 1)
            if cand in MUSCLE_INDEX:
                return cand
    return None


# ---------------------------------------------------------------------------
# 2) 肌肉 → 部位（moved_regions；部位名进 T-29 的 covers 交集）
# ---------------------------------------------------------------------------
MUSCLE_REGIONS: Dict[str, str] = {}


def _reg(names: Sequence[str], region: str) -> None:
    for n in names:
        MUSCLE_REGIONS[n] = region


_reg(["Spine Front-Back", "Spine Left-Right", "Spine Twist Left-Right"], "spine")
_reg(["Chest Front-Back", "Chest Left-Right", "Chest Twist Left-Right"], "chest")
_reg(["UpperChest Front-Back", "UpperChest Left-Right", "UpperChest Twist Left-Right"],
     "upperchest")
_reg(["Neck Nod Down-Up", "Neck Tilt Left-Right", "Neck Turn Left-Right"], "neck")
_reg(["Head Nod Down-Up", "Head Tilt Left-Right", "Head Turn Left-Right"], "head")
_reg(["Left Eye Down-Up", "Left Eye In-Out", "Right Eye Down-Up", "Right Eye In-Out"], "eye")
_reg(["Jaw Close", "Jaw Left-Right"], "jaw")
for side in ("Left", "Right"):
    _reg(["%s Upper Leg Front-Back" % side, "%s Upper Leg In-Out" % side,
          "%s Upper Leg Twist In-Out" % side], "thigh")
    _reg(["%s Lower Leg Stretch" % side, "%s Lower Leg Twist In-Out" % side], "knee")
    _reg(["%s Foot Up-Down" % side, "%s Foot Twist In-Out" % side], "ankle")
    _reg(["%s Toes Up-Down" % side], "toe")
    _reg(["%s Shoulder Down-Up" % side, "%s Shoulder Front-Back" % side], "shoulder")
    _reg(["%s Arm Down-Up" % side, "%s Arm Front-Back" % side,
          "%s Arm Twist In-Out" % side], "upperarm")
    _reg(["%s Forearm Stretch" % side, "%s Forearm Twist In-Out" % side], "elbow")
    _reg(["%s Hand Down-Up" % side, "%s Hand In-Out" % side], "hand")
for n in FINGER_MUSCLES:
    MUSCLE_REGIONS[n] = "finger"

# moved_regions 阈值：肌肉 |Δ vs 基线| > 0.1（03 §8.1 / I10）
MOVE_EPS = 0.1


def moved_regions(values: Dict[str, float],
                  base: Optional[Dict[str, float]] = None) -> List[str]:
    """肌肉值相对基线（默认全 0，用于 additive 增量）差 > `MOVE_EPS` 的部位，去重排序。"""
    ref = base or {}
    out = set()
    for name, v in values.items():
        b = ref.get(name, 0.0)
        if abs(float(v) - float(b)) > MOVE_EPS:
            r = MUSCLE_REGIONS.get(name)
            if r:
                out.add(r)
    return sorted(out)


# ---------------------------------------------------------------------------
# 3) 库 B：关节扫掠
# ---------------------------------------------------------------------------
# direction = +1/-1：从 stand_still 值向该方向的库 A 包络极值插值（agy D5；不用 ±1）。
# 若该方向在库 A 里没有位移，pose_frames 会退到反方向并在报告里写 `envelope_fallback`。
JOINT_SCANS: List[dict] = [
    {"id": "hip_fb", "region": "thigh", "sided": True, "dir": -1,
     "muscles": {"L": ["Left Upper Leg Front-Back"], "R": ["Right Upper Leg Front-Back"]}},
    {"id": "hip_io", "region": "thigh", "sided": True, "dir": +1,
     "muscles": {"L": ["Left Upper Leg In-Out"], "R": ["Right Upper Leg In-Out"]}},
    {"id": "knee", "region": "knee", "sided": True, "dir": -1,
     "muscles": {"L": ["Left Lower Leg Stretch"], "R": ["Right Lower Leg Stretch"]}},
    {"id": "shoulder_up", "region": "shoulder", "sided": True, "dir": +1,
     "muscles": {"L": ["Left Arm Down-Up"], "R": ["Right Arm Down-Up"]}},
    {"id": "shoulder_fb", "region": "shoulder", "sided": True, "dir": -1,
     "muscles": {"L": ["Left Arm Front-Back"], "R": ["Right Arm Front-Back"]}},
    {"id": "elbow", "region": "elbow", "sided": True, "dir": -1,
     "muscles": {"L": ["Left Forearm Stretch"], "R": ["Right Forearm Stretch"]}},
    {"id": "ankle", "region": "ankle", "sided": True, "dir": -1,
     "muscles": {"L": ["Left Foot Up-Down"], "R": ["Right Foot Up-Down"]}},
    # 脊柱前屈不分左右，4 档
    {"id": "spine_fb", "region": "spine", "sided": False, "dir": +1,
     "muscles": {"C": ["Spine Front-Back", "Chest Front-Back"]}},
]

DOSE_STEPS: Tuple[int, ...] = (25, 50, 75, 100)

# 6 个组合（03 §8.1）；doses 里的键是 JOINT_SCANS.id，值是该关节剂量%
COMBOS: List[dict] = [
    {"id": "combo_sit", "label": "坐", "doses": {"hip_fb": 100, "knee": 100}},
    {"id": "combo_deep_squat", "label": "深蹲",
     "doses": {"hip_fb": 100, "knee": 100, "spine_fb": 50}},
    {"id": "combo_kneel_sit", "label": "跪坐", "doses": {"knee": 100, "ankle": 100}},
    {"id": "combo_arms_crossed", "label": "抱胸",
     "doses": {"shoulder_fb": 75, "elbow": 100}},
    {"id": "combo_arms_up", "label": "高举",
     "doses": {"shoulder_up": 100, "elbow": 25}},
    {"id": "combo_cross_legged", "label": "盘腿",
     "doses": {"hip_io": 100, "knee": 100}},
]


def joint_scan_count() -> int:
    n = 0
    for s in JOINT_SCANS:
        sides = ("L", "R") if s["sided"] else ("C",)
        n += len(sides) * len(DOSE_STEPS)
    return n + len(COMBOS)


# ---------------------------------------------------------------------------
# 4) 内置参数（库 A/C 已知姿势；T-27 施加时经 GM 设上 + 回读断言 I9）
# ---------------------------------------------------------------------------
BUILTIN_PARAM_KEYS = ("Seated", "Upright", "Grounded", "AFK", "VelocityZ")

_SEATED_TOKENS = ("sit", "seated", "laydown", "sleep", "prone", "supine")
_CROUCH_TOKENS = ("crouch", "crawl", "kneel")
_MOVE_TOKENS = ("walk", "run", "sprint", "strafe", "shuffle", "turn", "jump",
                "fall", "land", "dash", "fly", "hover")


def builtin_params_for(pose_id: str) -> Dict[str, float]:
    """按姿势名给内置参数默认值。确定性；未知姿势取站立默认。"""
    p = {"Seated": 0.0, "Upright": 1.0, "Grounded": 1.0, "AFK": 0.0, "VelocityZ": 0.0}
    s = (pose_id or "").lower()
    if any(t in s for t in _SEATED_TOKENS):
        p["Seated"] = 1.0
        p["Upright"] = 0.0
    if any(t in s for t in _CROUCH_TOKENS):
        p["Upright"] = 0.0
    if "afk" in s:
        p["AFK"] = 1.0
    if any(t in s for t in _MOVE_TOKENS):
        p["VelocityZ"] = 1.0
    if "tpose" in s or "ikpose" in s:
        p["VelocityZ"] = 0.0
    return p


# ---------------------------------------------------------------------------
# 自验
# ---------------------------------------------------------------------------
def _selftest() -> int:
    fails: List[str] = []
    if MUSCLE_COUNT != 95:
        fails.append("MUSCLE_NAMES 应 95 条，实际 %d" % MUSCLE_COUNT)
    if len(set(MUSCLE_NAMES)) != MUSCLE_COUNT:
        dup = [n for n in MUSCLE_NAMES if MUSCLE_NAMES.count(n) > 1]
        fails.append("肌肉名有重复：%r" % sorted(set(dup)))
    if MUSCLE_INDEX.get("Left Upper Leg Front-Back") != 21:
        fails.append("Left Upper Leg Front-Back 序号应 21，实际 %r"
                     % MUSCLE_INDEX.get("Left Upper Leg Front-Back"))
    if MUSCLE_INDEX.get("Left Little 3 Stretched") != 74:
        fails.append("Left Little 3 Stretched 序号应 74，实际 %r"
                     % MUSCLE_INDEX.get("Left Little 3 Stretched"))
    if MUSCLE_INDEX.get("Right Little 3 Stretched") != 94:
        fails.append("Right Little 3 Stretched 序号应 94，实际 %r"
                     % MUSCLE_INDEX.get("Right Little 3 Stretched"))
    if MUSCLE_INDEX.get("Spine Front-Back") != 0:
        fails.append("Spine Front-Back 序号应 0，实际 %r"
                     % MUSCLE_INDEX.get("Spine Front-Back"))

    cases = {
        "LeftHand.Index.1 Stretched": "Left Index 1 Stretched",
        "RightHand.Little.Spread": "Right Little Spread",
        "LeftHand.Thumb.3 Stretched": "Left Thumb 3 Stretched",
        "Left Hand Down-Up": "Left Hand Down-Up",
        "UpperChest Front-Back": "UpperChest Front-Back",
        "Chest Front-Back": "Chest Front-Back",
        "RootT.y": None,
        "blendShape.mood_happy": None,
    }
    for raw, want in cases.items():
        got = clip_attr_to_muscle(raw)
        if got != want:
            fails.append("clip_attr_to_muscle(%r)=%r，应 %r" % (raw, got, want))

    if set(MUSCLE_REGIONS) != set(MUSCLE_NAMES):
        missing = set(MUSCLE_NAMES) - set(MUSCLE_REGIONS)
        fails.append("MUSCLE_REGIONS 未覆盖：%r" % sorted(missing)[:8])
    if MUSCLE_REGIONS.get("Left Upper Leg Front-Back") != "thigh":
        fails.append("髋前屈应映射 thigh")
    if MUSCLE_REGIONS.get("Left Lower Leg Stretch") != "knee":
        fails.append("膝应映射 knee")

    if joint_scan_count() != 66:
        fails.append("库 B 应 66 条，实际 %d" % joint_scan_count())
    if len(JOINT_SCANS) != 8 or len(COMBOS) != 6:
        fails.append("关节组应 8 项（7 左右分 + 1 脊柱）、组合应 6 项")

    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        return 1
    print("[selftest] muscles OK（95 肌肉名 / 手指映射 / 部位 / 库 B 66 条）")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
