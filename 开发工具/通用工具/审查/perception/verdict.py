#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verdict.py —— T-14 校验器：声明（应该怎样）× T1/geo/写者（实际怎样）→ 对账并归因。
【项目沉淀】通用工具
适用素体：无关
相关素材：声明 decl.json + T1/geo/写者输出
工具链　：Python 3（离线）
可复用性：★★ 审查工具链的一环
用途　　：T-14 校验器：声明（应该怎样）× T1/geo/写者（实际怎样）→ 对账并归因。


用法（详见 README「T-14 校验器」节）：
  python3 perception/verdict.py --selftest
  python3 perception/verdict.py --decl <工程>/_感知/decl.json --t1 <T1 输出目录> \
      [--profile 开发工具/素体档案/Kaguya.yaml] [--geo <目录>] \
      [--writers writers.json] [--ma-analysis ma_analysis.json] \
      [--fx-final fx_final.json] [--mapping mapping.json] \
      [--inventory inventory.json] [--pb pb.json] [--key-follow key_follow.json] \
      [--out verdicts.json]
  python3 perception/verdict.py --diff a.json b.json

输入缺席时的降级（规格硬要求）：截获类输入（writers/ma_analysis/fx_final/mapping/geo）
缺席时，依赖它们的判定降级为 `no_data` 并在报告里列出——**不许报 pass**。
不启动 Unity、不进 Play、不 git 提交、不改工程文件。
"""

import argparse
import glob
import hashlib
import json
import os
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import decl_validate as dv          # noqa: E402
import rules_universal as ru        # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
TOOL = "verdict.py"
SCHEMA = "perception/verdicts/0.1"

# 判定结果分类
JUDGED = ("pass", "violation")
UNDECIDED = ("no_data", "undecidable", "unmatched")
EXCLUDED = ("dont_care",)


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_json_opt(path):
    if path and os.path.exists(path):
        try:
            return load_json(path)
        except Exception:
            return None
    return None


def load_thresholds(path):
    if path and os.path.exists(path):
        return dv.load_yaml_file(path)
    return {}


def compute_tool_version():
    """工具版本戳 = 源文件 hash 前缀（与 T1 的 VERSION 对账口径一致）。"""
    files = [os.path.abspath(__file__),
             os.path.join(HERE, "rules_universal.py"),
             os.path.join(HERE, "thresholds.yaml")]
    h = hashlib.sha256()
    for p in files:
        if os.path.exists(p):
            h.update(os.path.basename(p).encode("utf-8"))
            h.update(sha256_file(p).encode("ascii"))
    return "%s@%s" % (TOOL, h.hexdigest()[:8])


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 判定器
# ---------------------------------------------------------------------------

class Verdict:
    def __init__(self, args):
        self.args = args
        self.decl = load_json(args.decl)
        self.decl_hash = "sha256:" + sha256_file(args.decl)
        self.tool_version = compute_tool_version()
        self.profile = dv.load_yaml_file(args.profile) if args.profile and os.path.exists(args.profile) else {}
        th = load_thresholds(args.thresholds)
        self.thresholds = th
        self.ctx = self._build_ctx(th)
        self.geo = {}
        self.writers = load_json_opt(getattr(args, "writers", None))
        self.ma = load_json_opt(getattr(args, "ma_analysis", None))
        self.fx = load_json_opt(getattr(args, "fx_final", None))
        self.mapping = load_json_opt(getattr(args, "mapping", None))
        self.inventory = load_json_opt(getattr(args, "inventory", None))
        self.pb = load_json_opt(getattr(args, "pb", None))
        self.key_follow = load_json_opt(getattr(args, "key_follow", None))
        self._key_follow_path = getattr(args, "key_follow", None)
        if self.key_follow is None and isinstance(self.inventory, dict):
            avs = self.inventory.get("avatars")
            if avs and isinstance(avs[0], dict) and (avs[0].get("key_follow")):
                self.key_follow = self.inventory
                self._key_follow_path = getattr(args, "inventory", None)
        self._map_index = {}
        self._map_unrecognized = False
        self._index_mapping()
        self.states = []
        self.batches = []
        self.part_smr_paths = {}
        self.alt_children = {}
        self._index_decl()
        self.rows = []
        self.findings = []
        self.universal = []
        self.universal_no_data = []
        self.unmatched = []
        self.waivers = []

    # -- 上下文 ----------------------------------------------------------
    def _build_ctx(self, th):
        def g(section, key, default):
            s = th.get(section) or {}
            return s.get(key, default)
        return {
            "value_tol": g("value", "tol", 0.5),
            "baseline_tol": g("baseline", "tol", 0.5),
            "sync_tol": g("sync", "tol", 0.5),
            "U1": th.get("U1") or {},
            "U2": th.get("U2") or {},
            "U3": th.get("U3") or {},
            "U4": th.get("U4") or {},
            "U5": th.get("U5") or {},
            "U6": th.get("U6") or {},
            "U7": th.get("U7") or {},
            "U_KF": th.get("U_KF") or {},
        }

    def _index_decl(self):
        for p in (self.decl.get("parts") or []):
            pid = p.get("id")
            self.part_smr_paths.setdefault(pid, [])
            for obj in (p.get("objects") or []):
                if obj.get("renderer") == "smr":
                    self.part_smr_paths[pid].append(obj.get("path"))
            alt = p.get("alt_of")
            if alt:
                self.alt_children.setdefault(alt, []).append(pid)

    def _index_mapping(self):
        """把 T-12 mapping.json 展平成 (mesh,key)→信息。

        T-12 未交付、schema 未定；这里做成宽容读取：任何含 'key' 的 dict 或
       「键名 → {status|target|targets}」的映射都收。完全认不出时记 no_data 提示，不猜。
        """
        self._map_index = {}
        self._map_unrecognized = False
        if not self.mapping:
            return

        def walk(node, mesh=None):
            if isinstance(node, dict):
                m = node.get("mesh") or node.get("renderer") or node.get("path") or mesh
                if isinstance(node.get("key"), str):
                    info = {k: node[k] for k in ("status", "target", "targets", "mapped", "reason")
                            if k in node}
                    self._map_index[(m, node["key"])] = info
                for k, v in node.items():
                    if k in ("mesh", "renderer", "path", "key", "status", "target",
                             "targets", "mapped", "reason"):
                        continue
                    if isinstance(v, dict) and any(
                            x in v for x in ("status", "target", "targets", "mapped")):
                        self._map_index[(m, k)] = v
                    else:
                        walk(v, m)
            elif isinstance(node, list):
                for x in node:
                    walk(x, mesh)

        walk(self.mapping)
        if not self._map_index:
            self._map_unrecognized = True

    def _mapping_lookup(self, mesh, key):
        if not self._map_index or not key:
            return None
        for (m, k), info in self._map_index.items():
            if k != key:
                continue
            if m is None or m == mesh:
                return info
            if mesh and ru.norm_path(m) and ru.norm_path(mesh) and \
                    ru.norm_path(m)[-1:] == ru.norm_path(mesh)[-1:]:
                return info
        return None

    def key_state(self, sv, mesh, key):
        """冻结四分（03 §3）：写 0 / 不存在 / frozen / frozen_meaningless。

        没有 mapping.json 时只能分出「存在（值>0）/ 写 0 / 网格在但键不存在 / 网格名解析不上」；
        frozen 两分标 no_data 由 mapping.json 提供。
        """
        info = self._mapping_lookup(mesh, key)
        actual, p, ak, un = sv.value(mesh, key)
        if un == "ambiguous":
            return "ambiguous"
        if p is None:
            return "mesh_absent"
        if info:
            st = info.get("status")
            if st in ("removed_frozen", "frozen"):
                return "frozen"
            if st == "frozen_meaningless":
                return "frozen_meaningless"
            targets = info.get("targets") or ([info["target"]] if info.get("target") else [])
            if not targets and st == "removed":
                return "absent"
            if actual == 0:
                return "written_zero"
            return "present"
        if ak is None:
            return "absent"
        return "present" if actual != 0 else "written_zero"

    # -- 状态载入 --------------------------------------------------------
    def load_states(self, dirs, globs=None):
        files = []
        for d in dirs or []:
            if os.path.isdir(d):
                files.extend(sorted(glob.glob(os.path.join(d, "state_*.json"))))
                self._load_batch(d)
            elif os.path.isfile(d):
                files.append(d)
        for pat in (globs or []):
            files.extend(sorted(glob.glob(pat)))
        files = list(OrderedDict.fromkeys(files))
        catalog = []
        raw_by_id = {}
        for f in files:
            try:
                raw = load_json(f)
            except Exception:
                continue
            sid = os.path.basename(f)[len("state_"):-len(".json")]
            raw_by_id[sid] = raw
            for r in (raw.get("renderers") or []):
                p = r.get("path")
                if p and p not in catalog:
                    catalog.append(p)
        for sid, raw in raw_by_id.items():
            sv = ru.StateView(sid, raw, self.decl, catalog)
            sv.expected_E = ru.compute_expected_visibility(self.decl, sv.st)
            self.states.append(sv)
        return files

    def _load_batch(self, d):
        """读 T1 批次头（states.json/status.json），用于哨兵与完整性提示。"""
        b = {"dir": d,
             "states_json": False,
             "status": None,
             "state_files": len(glob.glob(os.path.join(d, "state_*.json"))),
             "sentinels": None,
             "tool": None,
             "tool_version": None}
        sj = load_json_opt(os.path.join(d, "states.json"))
        stj = load_json_opt(os.path.join(d, "status.json"))
        if stj:
            b["status"] = stj.get("state")
        if sj:
            b["states_json"] = True
            b["tool"] = sj.get("tool")
            b["tool_version"] = sj.get("tool_version")
            b["sentinels"] = sj.get("sentinels")
            if sj.get("state_files"):
                b["state_files"] = len(sj.get("state_files"))
        self.batches.append(b)

    def load_geo(self, patterns):
        for pat in patterns or []:
            for f in sorted(glob.glob(pat)):
                sid = os.path.basename(f)
                for pre in ("geo_",):
                    if sid.startswith(pre):
                        sid = sid[len(pre):]
                if sid.endswith(".json"):
                    sid = sid[:-5]
                data = load_json_opt(f)
                if data is not None:
                    self.geo[sid] = data
            if os.path.isdir(pat):
                for f in sorted(glob.glob(os.path.join(pat, "geo_*.json"))):
                    sid = os.path.basename(f)[len("geo_"):-len(".json")]
                    data = load_json_opt(f)
                    if data is not None:
                        self.geo[sid] = data

    # -- 目标展开 --------------------------------------------------------
    def dep_targets(self, dep):
        out = []
        tgs = dep.get("targets") if "targets" in dep else ([dep["target"]] if "target" in dep else [])
        for t in tgs:
            if not isinstance(t, dict):
                continue
            if "part" in t and "mesh" not in t:
                pid = t["part"]
                if "key" in t:
                    for m in self.part_smr_paths.get(pid, []):
                        out.append({"kind": "key", "part": pid, "mesh": m, "key": t["key"]})
                elif "keys" in t:
                    for k in t["keys"]:
                        for m in self.part_smr_paths.get(pid, []):
                            out.append({"kind": "key", "part": pid, "mesh": m, "key": k})
                elif "submesh" in t:
                    out.append({"kind": "grab", "part": pid, "submesh": t["submesh"]})
                else:
                    out.append({"kind": "part", "part": pid})
            else:
                mesh = t.get("mesh")
                if "key" in t:
                    out.append({"kind": "key", "mesh": mesh, "key": t["key"]})
                elif "keys" in t:
                    for k in t["keys"]:
                        out.append({"kind": "key", "mesh": mesh, "key": k})
                else:
                    out.append({"kind": "values", "mesh": mesh})
        return out

    # -- 主流程 ----------------------------------------------------------
    def run(self):
        deps = [d for d in (self.decl.get("deps") or []) if not d.get("superseded_by")]
        for sv in self.states:
            E = sv.eval_vis()
            pbk = sv.parts_by_kind
            unknown = set(sv.vis_unknown())   # B-补-12：归属不了的件，when 走三值求值
            for dep in deps:
                exp = ru.eval_decl_dep(dep, sv.st, E, pbk, unknown)
                for tgt in self.dep_targets(dep):
                    f = self.judge(sv, dep, tgt, exp)
                    self.rows.append(f)
        self.findings = self.rows
        # 通用规则
        self._run_universal()
        # 豁免
        self.waivers = self._apply_waivers()
        return self

    def _run_universal(self):
        sts = self.states
        ctx = self.ctx
        u1 = ru.rule_u1(self.geo, ctx)
        u2 = ru.rule_u2(sts, ctx)
        u3 = ru.rule_u3(sts, self.writers, self.profile, ctx)
        u4 = ru.rule_u4(sts, ctx)
        u5 = ru.rule_u5(sts, ctx)
        u6 = ru.rule_u6(sts, ctx)
        u7 = ru.rule_u7(self.pb, ctx)
        kf = ru.key_follow_verdict(sts, self.key_follow, self.decl, self.profile, ctx,
                                   t1_dirs=self.args.t1,
                                   key_follow_path=self._key_follow_path)
        for fs, nd in (u1, u2, u3, u4, u5, u6, u7):
            self.universal.extend(self._norm_univ(fs))
            self.universal_no_data.extend(nd)
        self.universal.extend(self._norm_univ(kf[0]))
        self.universal_no_data.extend(kf[1])
        self.unmatched.extend(kf[2])

    @staticmethod
    def _norm_univ(fs):
        """通用规则输出用 severity；统一补 status 供汇总使用。"""
        out = []
        for f in fs:
            if "status" not in f:
                f["status"] = f.get("severity") or "info"
            out.append(f)
        return out

    # -- 单条判定 --------------------------------------------------------
    def _base(self, sv, dep, tgt, status, message, **kw):
        d = {
            "status": status,
            "rule": kw.pop("rule", None),
            "dep": dep.get("id") if dep else kw.pop("dep", None),
            "state": sv.id if sv else None,
            "kind": tgt.get("kind") if tgt else None,
            "target": self._target_name(tgt),
            "metric": None,
            "actual": None,
            "expected": None,
            "message": message,
            "advisory": False,
            "writer_blamed": None,
        }
        d.update(kw)
        return d

    @staticmethod
    def _target_name(tgt):
        if not tgt:
            return None
        if tgt.get("part"):
            return tgt["part"]
        return tgt.get("mesh")

    def judge(self, sv, dep, tgt, exp):
        if exp == "dont_care":
            return self._base(sv, dep, tgt, "dont_care", "dont_care")
        if exp == "baseline":
            return self._judge_baseline(sv, dep, tgt)
        if exp is ru.UNDECIDABLE:
            unk = sorted(sv.vis_unknown()) if sv else []
            return self._base(sv, dep, tgt, "undecidable",
                              "when 依赖归属不了的件可见性（%s）；期望无从谈起，判不了"
                              % ("、".join(unk) or "unknown"))
        if not isinstance(exp, dict):
            return self._base(sv, dep, tgt, "undecidable", "期望形式无法解释：%r" % (exp,))
        if "pending" in exp:
            return self._base(sv, dep, tgt, "undecidable", "期望待人判：%s" % (dep.get("human"),))
        if "value" in exp or "range" in exp or "values" in exp:
            return self._judge_numeric(sv, dep, tgt, exp)
        if "hidden" in exp or "shown" in exp:
            return self._judge_visibility(sv, dep, tgt, bool(exp.get("hidden")))
        if "sync" in exp:
            return self._judge_sync(sv, dep, tgt, exp)
        if "variant" in exp:
            return self._judge_variant(sv, dep, tgt, exp)
        if "grab" in exp:
            return self._judge_grab(sv, dep, tgt, exp)
        if "not_written" in exp:
            return self._judge_not_written(sv, dep, tgt, exp)
        if "no_writer_other_than" in exp:
            return self._judge_no_writer_other(sv, dep, tgt, exp)
        if "deleted" in exp:
            return self._judge_deleted(sv, dep, tgt, exp)
        if "geo" in exp:
            return self._judge_geo(sv, dep, tgt, exp)
        if "class" in exp:
            return self._judge_class(sv, dep, tgt, exp)
        return self._base(sv, dep, tgt, "undecidable", "期望里没有可判主形式")

    # -- 各期望形式 ------------------------------------------------------
    def _judge_numeric(self, sv, dep, tgt, exp):
        tol = _num(exp.get("tol"), self.ctx["value_tol"])
        if "values" in exp:
            worst = None
            for k, ev in (exp["values"] or {}).items():
                mesh = tgt.get("mesh")
                actual, p, ak, un = sv.value(mesh, k)
                diff = abs(actual - _num(ev))
                if worst is None or diff > worst[0]:
                    worst = (diff, k, actual, _num(ev), un)
            if worst is None:
                return self._base(sv, dep, tgt, "undecidable", "expect.values 为空")
            diff, k, actual, ev, un = worst
            if un == "ambiguous":
                return self._base(sv, dep, tgt, "unmatched", "键名多义：%s" % k)
            st = "pass" if diff <= tol else "violation"
            return self._base(sv, dep, tgt, st,
                              "values[%s] 实测 %.3f 期望 %.3f（tol %.2f，差 %.3f）" % (k, actual, ev, tol, diff),
                              metric="value_abs_diff", actual=actual, expected=ev,
                              writer_blamed=self.blame(tgt.get("mesh"), k))
        mesh = tgt.get("mesh")
        key = tgt.get("key")
        actual, p, ak, un = sv.value(mesh, key)
        if un == "ambiguous":
            return self._base(sv, dep, tgt, "unmatched", "键名多义：%s" % key)
        if un == "mesh":
            return self._base(sv, dep, tgt, "unmatched", "网格名解析不上：%s" % mesh)
        if "value" in exp:
            ev = _num(exp.get("value"))
            diff = abs(actual - ev)
            st = "pass" if diff <= tol else "violation"
            return self._base(sv, dep, tgt, st,
                              "%s 实测 %.3f 期望 %.3f（tol %.2f，差 %.3f%s）"
                              % (key, actual, ev, tol, diff,
                                 "" if ak == key else "，构后键=%s" % ak),
                              metric="value_abs_diff", actual=actual, expected=ev,
                              key_state=self.key_state(sv, mesh, key),
                              writer_blamed=self.blame(mesh, key))
        lo, hi = exp.get("range") or [0, 100]
        st = "pass" if _num(lo) - 1e-9 <= actual <= _num(hi) + 1e-9 else "violation"
        return self._base(sv, dep, tgt, st,
                          "%s 实测 %.3f 期望区间 [%.2f, %.2f]" % (key, actual, _num(lo), _num(hi)),
                          metric="value_abs_diff", actual=actual,
                          expected=[_num(lo), _num(hi)], writer_blamed=self.blame(mesh, key))

    def _judge_baseline(self, sv, dep, tgt):
        tol = self.ctx["baseline_tol"]
        if tgt.get("kind") == "part":
            pid = tgt["part"]
            if pid in sv.vis_unknown():
                return self._base(sv, dep, tgt, "undecidable",
                                  "%s 实测可见性归属不了；按不可见判会误判，落 undecidable" % pid)
            actual = sv.visible(pid)
            exp = bool((sv.expected_E or {}).get(pid, False))
            st = "pass" if actual == exp else "violation"
            return self._base(sv, dep, tgt, st,
                              "%s 实测可见=%s 期望可见=%s" % (pid, actual, exp),
                              metric="visibility_mismatch", actual=actual, expected=exp)
        mesh, key = tgt.get("mesh"), tgt.get("key")
        actual, p, ak, un = sv.value(mesh, key)
        if un == "ambiguous":
            return self._base(sv, dep, tgt, "unmatched", "键名多义：%s" % key)
        base = ru.baseline_value(self.profile, key)
        diff = abs(actual - base)
        st = "pass" if diff <= tol else "violation"
        return self._base(sv, dep, tgt, st,
                          "%s 实测 %.3f 期望基线 %.3f（tol %.2f）" % (key, actual, base, tol),
                          metric="value_abs_diff", actual=actual, expected=base,
                          key_state=self.key_state(sv, mesh, key),
                          writer_blamed=self.blame(mesh, key))

    def _judge_visibility(self, sv, dep, tgt, want_hidden):
        if tgt.get("kind") not in ("part", None) or not tgt.get("part"):
            return self._base(sv, dep, tgt, "undecidable", "hidden/shown 只对 {part} 目标可判")
        pid = tgt["part"]
        if pid in sv.vis_unknown():
            return self._base(sv, dep, tgt, "undecidable",
                              "%s 实测可见性归属不了；hidden/shown 判不了" % pid)
        actual = sv.visible(pid)
        want = (not actual) if want_hidden else actual
        st = "pass" if want else "violation"
        return self._base(sv, dep, tgt, st,
                          "%s 实测可见=%s 期望%s" % (pid, actual, "隐藏" if want_hidden else "显示"),
                          metric="visibility_mismatch", actual=actual,
                          expected=("hidden" if want_hidden else "shown"))

    def _judge_sync(self, sv, dep, tgt, exp):
        sync = exp.get("sync") or {}
        frm = sync.get("from") or {}
        src, _p, _k, _u = sv.value(frm.get("mesh"), frm.get("key"))
        mesh, key = tgt.get("mesh"), tgt.get("key")
        actual, _p2, _k2, un = sv.value(mesh, key)
        if un == "ambiguous":
            return self._base(sv, dep, tgt, "unmatched", "键名多义：%s" % key)
        if "map" in sync and sync["map"]:
            ev = _piecewise(sync["map"], src)
        else:
            scale = _num(sync.get("scale"), 1.0)
            offset = _num(sync.get("offset"), 0.0)
            ev = max(0.0, min(100.0, scale * src + offset))
        tol = _num(sync.get("tol"), self.ctx["sync_tol"])
        diff = abs(actual - ev)
        st = "pass" if diff <= tol else "violation"
        return self._base(sv, dep, tgt, st,
                          "%s 实测 %.3f 期望 sync=%.3f（源 %s.%s=%.3f，tol %.2f）"
                          % (key, actual, ev, frm.get("mesh"), frm.get("key"), src, tol),
                          metric="value_abs_diff", actual=actual, expected=ev,
                          writer_blamed=self.blame(mesh, key))

    def _judge_variant(self, sv, dep, tgt, exp):
        var = exp.get("variant") or {}
        pid = tgt.get("part")
        if not pid:
            return self._base(sv, dep, tgt, "undecidable", "variant 只对 {part} 目标可判")
        group = [pid] + list(self.alt_children.get(pid, []))
        unknown = set(sv.vis_unknown())
        unk = [g for g in group if g in unknown]
        if unk:
            return self._base(sv, dep, tgt, "undecidable",
                              "variant 组内 %s 可见性归属不了；exclusive/option 判不了" % unk)
        visible = [g for g in group if sv.visible(g)]
        problems = []
        if var.get("exclusive") and len(visible) > 1:
            problems.append("exclusive 但可见 %s" % visible)
        opts = var.get("options") or []
        chosen = None
        # B-补-12：option 的 when 也按**实测可见性**三值求值（与 dep.when 同口径），
        # 不用声明模型推出来的 expected_E；依赖归属不了的件时落 undecidable。
        E = sv.eval_vis()
        for o in opts:
            if not isinstance(o, dict):
                continue
            try:
                ast = dv.parse_cond(o.get("when"))
            except Exception:
                continue
            cw = ru.eval_cond_3(ast, sv.st, E, sv.parts_by_kind, unknown)
            if cw is None:
                return self._base(sv, dep, tgt, "undecidable",
                                  "variant option when 依赖归属不了的件；判不了")
            if cw:
                chosen = o
                break
        if chosen is not None:
            use = chosen.get("use")
            extra = [v for v in visible if v != use]
            if extra:
                problems.append("option use=%s 但还可见 %s" % (use, extra))
        st = "pass" if not problems else "violation"
        return self._base(sv, dep, tgt, st,
                          "variant %s：可见 %s%s" % (pid, visible,
                                                     "" if not problems else "；" + "；".join(problems)),
                          metric="visibility_mismatch", actual=visible,
                          expected=[o.get("use") for o in opts if isinstance(o, dict)])

    def _judge_grab(self, sv, dep, tgt, exp):
        gc = sv.probes.get("grab_chain")
        if not gc:
            return self._base(sv, dep, tgt, "no_data", "无 probes.grab_chain；抓屏链判不了")
        pid = tgt.get("part")
        gexp = exp.get("grab") or {}
        point_min = gexp.get("point_min")
        if point_min is None:
            point_min = ((self.decl.get("render") or {}).get("grab_point_min")
                         or self.ctx["U4"].get("point_min", 3050))
        hidden_max = gexp.get("hidden_behind_max")
        if hidden_max is None:
            hidden_max = self.ctx["U4"].get("hidden_max", 0)
        mats = [m for m in (gc.get("grab_materials") or [])
                if pid and self._part_owns(sv, pid, m.get("renderer"))]
        if not mats:
            return self._base(sv, dep, tgt, "no_data",
                              "%s 在状态 %s 没有抓屏材质（grab_point_queue=%s）"
                              % (pid, sv.id, gc.get("grab_point_queue")))
        q = gc.get("grab_point_queue")
        if q is None or q < _num(point_min):
            return self._base(sv, dep, tgt, "violation",
                              "%s 抓取点 %s < 期望 %s" % (pid, q, point_min),
                              metric="grab.point_queue", actual=q, expected=point_min,
                              writer_blamed=self._blame_material(sv, pid, tgt.get("submesh")))
        hidden = [h for h in (gc.get("hidden_materials") or [])
                  if self._part_owns(sv, pid, h.get("renderer"))]
        if len(hidden) > _num(hidden_max):
            return self._base(sv, dep, tgt, "violation",
                              "%s 抓取点之后有 %d 个非抓屏可见材质（上限 %d）"
                              % (pid, len(hidden), hidden_max),
                              metric="grab.hidden_count", actual=len(hidden), expected=hidden_max)
        return self._base(sv, dep, tgt, "pass",
                          "%s 抓取点 %s ≥ %s，抓取点之后无非抓屏材质" % (pid, q, point_min),
                          metric="grab.point_queue", actual=q, expected=point_min)

    def _part_owns(self, sv, pid, renderer):
        if not renderer:
            return False
        for p in sv.part_paths.get(pid, []):
            if p == renderer:
                return True
        # 构后改名：声明路径与实测路径都归一后比较
        for p in sv.part_paths.get(pid, []):
            if ru.norm_path(p) == ru.norm_path(renderer):
                return True
        return False

    def _judge_not_written(self, sv, dep, tgt, exp):
        if not self.writers:
            return self._base(sv, dep, tgt, "no_data",
                              "无 writers.json（T-11）；not_written 判不了")
        key = tgt.get("key")
        mesh = tgt.get("mesh")
        entries = self._writer_entries(mesh, key)
        if entries:
            return self._base(sv, dep, tgt, "violation",
                              "%s 声明不应被写，但 writers.json 有 %d 个写者：%s"
                              % (key, len(entries), [e.get("source") for e in entries]),
                              metric="value_abs_diff",
                              writer_blamed=self.blame(mesh, key))
        return self._base(sv, dep, tgt, "pass", "%s 无写者" % key)

    def _judge_no_writer_other(self, sv, dep, tgt, exp):
        if not self.writers:
            return self._base(sv, dep, tgt, "no_data",
                              "无 writers.json（T-11）；no_writer_other_than 判不了")
        allowed = set(exp.get("no_writer_other_than") or [])
        key = tgt.get("key")
        mesh = tgt.get("mesh")
        entries = self._writer_entries(mesh, key)
        bad = [e for e in entries if e.get("source") not in allowed]
        st = "pass" if not bad else "violation"
        return self._base(sv, dep, tgt, st,
                          "%s 写者 %s（允许 %s）" % (key, [e.get("source") for e in entries],
                                                    sorted(allowed)),
                          writer_blamed=self.blame(mesh, key))

    def _judge_deleted(self, sv, dep, tgt, exp):
        return self._base(sv, dep, tgt, "no_data",
                          "Delete 比例需 T1 v4 的 V4 桶/键存在表（T-13），当前状态文件没有")

    def _judge_geo(self, sv, dep, tgt, exp):
        if not self.geo:
            return self._base(sv, dep, tgt, "no_data",
                              "无 geo_*.json（T-10/T-28a）；几何度量判不了")
        g = self.geo.get(sv.id) or {}
        sets = ru._collect_patches(g)
        if not sets:
            return self._base(sv, dep, tgt, "no_data",
                              "geo 数据存在但 schema 未识别（T-10 交付后补读）")
        keys = tgt.get("keys") or [tgt.get("key")]
        bad = [p for p in sets if p.get("area_cm2") is not None
               and p["area_cm2"] >= self.ctx["U1"].get("min_area_cm2", 0.5)]
        st = "pass" if not bad else "violation"
        return self._base(sv, dep, tgt, st,
                          "几何斑块 %d 个（阈值 %.2f cm²）"
                          % (len(bad), self.ctx["U1"].get("min_area_cm2", 0.5)),
                          metric="poke.area_cm2",
                          actual=(bad[0]["area_cm2"] if bad else 0.0),
                          expected="0 个斑块", advisory=True)

    def _judge_class(self, sv, dep, tgt, exp):
        want = exp.get("class")
        key = tgt.get("key")
        classes = ru._profile_key_classes(self.profile)
        if key not in classes:
            return self._base(sv, dep, tgt, "no_data",
                              "键 %s 不在素体档案 key_classes 里；类别判不了（E5/T-17）" % key)
        got = classes.get(key)
        st = "pass" if got == want else "violation"
        return self._base(sv, dep, tgt, st, "%s 实测类别 %s 期望 %s" % (key, got, want))

    # -- 归因 ------------------------------------------------------------
    def _writer_entries(self, mesh, key):
        if not self.writers or not key:
            return []
        we = self.writers.get("writers") or {}
        for cand in ("%s::%s" % (mesh, key), "%s::%s" % (key, mesh)):
            if cand in we:
                return we[cand] or []
        # 构后键名后备
        for wk, entries in we.items():
            if "::" not in wk:
                continue
            _m, _k = wk.split("::", 1)
            if ru.key_match_score(key, _k) >= 70 or _k == key:
                return entries or []
        return []

    def blame(self, mesh, key):
        if not key:
            return None
        entries = self._writer_entries(mesh, key)
        if not entries:
            return None
        sources = sorted({e.get("source") for e in entries if e.get("source")})
        rule = (self.writers or {}).get("winner_rule") or {}
        order = [rule.get("ours"), rule.get("ma"), rule.get("vendor_sc"), rule.get("vendor_clip")]
        order = [o for o in order if o]
        winner = None
        for o in order:
            if o in sources:
                winner = o
                break
        return {"sources": sources, "winner": winner or (sources[0] if sources else None),
                "confidence": "low" if len(sources) > 1 else "mid",
                "ma_captured": bool(self.ma), "fx_captured": bool(self.fx),
                "mapping": bool(self.mapping)}

    def _blame_material(self, sv, pid, submesh):
        """抓屏链违例归因到写该材质槽 ObjectReference 的 clip（需 writers.json）。"""
        if not self.writers or submesh is None:
            return None
        want = "m_Materials.Array.data[%d]" % submesh
        for p in sv.part_paths.get(pid, []):
            entries = self._writer_entries(p, want)
            if entries:
                return {"sources": sorted({e.get("source") for e in entries if e.get("source")}),
                        "winner": (entries[0].get("source") if entries else None),
                        "detail": entries[:4], "metric_key": want,
                        "confidence": "mid" if len(entries) == 1 else "low"}
        return None

    # -- 豁免 ------------------------------------------------------------
    def _apply_waivers(self):
        out = []
        for w in (self.decl.get("waivers") or []):
            rec = dict(w)
            eff = []
            if rec.get("decl_hash") not in (self.decl_hash, None):
                eff.append("decl_hash 不符（%s ≠ %s）" % (rec.get("decl_hash"), self.decl_hash))
            if rec.get("tool_version") not in (self.tool_version, None):
                eff.append("tool_version 不符（%s ≠ %s）" % (rec.get("tool_version"), self.tool_version))
            rec["effective"] = not eff
            rec["expired_reasons"] = eff
            rec["current_decl_hash"] = self.decl_hash
            rec["current_tool_version"] = self.tool_version
            rec["suppressed"] = 0
            if not eff:
                rec["suppressed"] = self._suppress(rec)
            out.append(rec)
        return out

    def _suppress(self, w):
        rule = w.get("rule")
        dep = w.get("dep")
        parts = set(w.get("parts") or [])
        limit = w.get("limit") or {}
        metric = limit.get("metric")
        mx = limit.get("max")
        n = 0
        for f in self.findings:
            if f["status"] != "violation":
                continue
            if rule and f.get("rule") != rule:
                continue
            if dep and f.get("dep") != dep:
                continue
            if parts and f.get("target") not in parts and not any(
                    p in str(f.get("target")) for p in parts):
                continue
            if metric and f.get("metric") != metric:
                continue
            if mx is not None and f.get("actual") is not None and _num(f["actual"]) > _num(mx):
                continue
            f["waived"] = w.get("rule") or w.get("dep")
            f["status"] = "pass"
            f["waived_note"] = "waiver 生效（metric ≤ %s）" % mx
            n += 1
        return n


def _compact(d):
    """落盘时去掉 None / 空串 / 空列表，控体积；False 保留（有语义）。"""
    out = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, str) and v == "":
            continue
        if isinstance(v, (list, dict)) and not v:
            continue
        out[k] = v
    return out


def _piecewise(map_pts, src):
    pts = sorted([(_num(a), _num(b)) for a, b in map_pts], key=lambda x: x[0])
    if src <= pts[0][0]:
        return pts[0][1]
    if src >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 <= src <= x1:
            if x1 == x0:
                return y1
            t = (src - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return pts[-1][1]


# ---------------------------------------------------------------------------
# 汇总与报告
# ---------------------------------------------------------------------------

def summarise(v):
    rows = v.rows
    st = Counter(f["status"] for f in rows)
    judged = sum(st[s] for s in JUDGED)
    undecided = sum(st[s] for s in UNDECIDED)
    excluded = sum(st[s] for s in EXCLUDED)
    denom = judged + undecided
    coverage = (judged / denom) if denom else 0.0

    def cluster(keyfn):
        c = Counter()
        for f in rows:
            if f["status"] in JUDGED:
                c[keyfn(f)] += 1
        return OrderedDict(sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0]))))

    by_dep = {}
    for f in rows:
        dep = f.get("dep")
        if not dep:
            continue
        d = by_dep.setdefault(dep, Counter())
        d[f["status"]] += 1
    by_part = {}
    for f in rows:
        part = f.get("target")
        if not part:
            continue
        by_part.setdefault(part, Counter())[f["status"]] += 1

    # no_data 清单（按 dep + 原因聚类）
    nd = Counter()
    nd_example = {}
    for f in rows + v.universal:
        if f["status"] not in ("no_data", "undecidable"):
            continue
        k = (f.get("dep") or f.get("rule"), (f.get("message") or "")[:120])
        nd[k] += 1
        nd_example.setdefault(k, f.get("state"))
    for n in v.universal_no_data:
        k = (n.get("rule"), (n.get("reason") or "")[:120])
        nd[k] += 1
        nd_example.setdefault(k, None)
    if not v.mapping:
        k = ("mapping.json", "缺席；源名→构后名按 AAO 模式后备匹配；冻结四分（frozen/frozen_meaningless）判不了")
        nd[k] += 1
        nd_example.setdefault(k, None)
    elif v._map_unrecognized:
        k = ("mapping.json", "存在但 schema 未识别（T-12 交付后补读）；冻结四分退化")
        nd[k] += 1
        nd_example.setdefault(k, None)
    for b in v.batches:
        if b.get("status") and b["status"] != "done":
            k = ("status.json", "批次状态 %s（非 done）" % b["status"])
            nd[k] += 1
            nd_example.setdefault(k, b["dir"])
        if b.get("states_json") and not b.get("sentinels"):
            k = ("sentinels", "T1 状态头无 sentinels 字段（03 §4.4①）；本批未做哨兵校验")
            nd[k] += 1
            nd_example.setdefault(k, b["dir"])
    for axis in ((v.decl.get("body_axes") or {})):
        k = ("body_axes." + axis, "T1 状态头不带体型轴实测值；按档案 baseline 0 判")
        nd[k] += 1
        nd_example.setdefault(k, None)
    part_unmatched = Counter()
    for sv in v.states:
        for u in sv.unmatched:
            part_unmatched[u] += 1
    for u, n in part_unmatched.items():
        k = ("件名解析", "%s %r 匹配不上（%d 状态）；该件按不可见/零值处理"
             % (u[0], u[1], n))
        nd[k] += 1
        nd_example.setdefault(k, None)
    expected = sum(b.get("state_files") or 0 for b in v.batches)
    if expected and expected != len(v.states):
        k = ("t1 批次", "state_files 列出 %d 个，实际载入 %d 个" % (expected, len(v.states)))
        nd[k] += 1
        nd_example.setdefault(k, None)
    for u in v.unmatched:
        k = ("unmatched", json.dumps(u, ensure_ascii=False)[:120])
        nd[k] += 1
        nd_example.setdefault(k, None)

    univ = {}
    for f in v.universal:
        r = f.get("rule") or "?"
        d = univ.setdefault(r, Counter())
        d[f["status"]] += 1
    for n in v.universal_no_data:
        r = n.get("rule") or "?"
        univ.setdefault(r, Counter())["no_data"] += 1

    # B-补-12：undecidable 明细（判不了的 dep×target）与逐状态「归属不了」件清单。
    # 这两张表就是「判不了清单」，禁止把归属不了的件按不可见塞回 pass 后在这里查无此人。
    und_rows = Counter()
    for f in rows:
        if f["status"] == "undecidable":
            und_rows[(f.get("dep"), f.get("target"))] += 1
    vis_unknown_states = []
    for sv in v.states:
        u = sorted(sv.vis_unknown())
        if u:
            vis_unknown_states.append({"state": sv.id, "parts": u})
    vis_unknown_parts = Counter()
    for sv in v.states:
        for p in sv.vis_unknown():
            vis_unknown_parts[p] += 1

    return {
        "states": len(v.states),
        "rows": len(rows),
        "status_counts": dict(st),
        "judged": judged,
        "undecided": undecided,
        "dont_care": excluded,
        "coverage": round(coverage, 4),
        "violations": st.get("violation", 0),
        "by_status_dep": {k: dict(c) for k, c in list(by_dep.items())},
        "by_part": {k: dict(c) for k, c in list(by_part.items())},
        "universal": {k: dict(c) for k, c in univ.items()},
        "no_data": [{"dep": k[0], "count": n, "reason": k[1], "example_state": nd_example.get(k)}
                    for k, n in sorted(nd.items(), key=lambda kv: (-kv[1], str(kv[0])))],
        "unmatched": v.unmatched,
        "part_unmatched": [{"kind": k[0], "declared": k[1], "states": n}
                           for k, n in part_unmatched.most_common()],
        "undecidable": [{"dep": k[0], "target": k[1], "count": n}
                        for k, n in sorted(und_rows.items(), key=lambda kv: (-kv[1], str(kv[0])))],
        "visibility_unknown": vis_unknown_states,
        "visibility_unknown_parts": [{"part": k, "states": n}
                                     for k, n in sorted(vis_unknown_parts.items(),
                                                        key=lambda kv: (-kv[1], str(kv[0])))],
        "waivers": v.waivers,
    }


def selftest_checks(v, summary):
    """规格验收：外套关闭 14 状态三键 pass；MMN 修后四组合 pass；U2/U4 0 命中。"""
    checks = []
    three = {"kaguya.body_under_outer", "kaguya.sailor_under_outer", "kaguya.hair_outer_on"}
    coat0 = [sv.id for sv in v.states if _num(sv.params.get("A2_Coat"), 1) == 0]
    rel = [f for f in v.rows if f.get("dep") in three and f.get("state") in coat0
           and f["status"] in JUDGED]
    bad = [f for f in rel if f["status"] != "pass"]
    checks.append({
        "name": "外套关闭 14 状态三键 pass",
        "ok": len(coat0) == 14 and len(rel) > 0 and not bad,
        "detail": "外套关闭状态 %d 个；三键已判 %d 条、pass %d、违例 %d"
                  % (len(coat0), len(rel), len(rel) - len(bad), len(bad)),
    })
    combos = ["MMN__all", "MMN__Sok_off", "MMN__Sho_off", "MMN__naked"]
    rel = [f for f in v.rows if f.get("dep") == "MMN.foot_flat" and f.get("state") in combos
           and f["status"] in JUDGED]
    bad = [f for f in rel if f["status"] != "pass"]
    checks.append({
        "name": "MMN 修后四组合 pass",
        "ok": len(rel) == 4 and not bad,
        "detail": "已判 %d 条（应 4）、pass %d、违例 %d" % (len(rel), len(rel) - len(bad), len(bad)),
    })
    u2 = [f for f in v.universal if f.get("rule") == "U2" and f["status"] == "violation"]
    u4 = [f for f in v.universal if f.get("rule") == "U4" and f["status"] == "violation"]
    checks.append({
        "name": "抓取点/重合 U2/U4 0 命中",
        "ok": not u2 and not u4,
        "detail": "U2 违例 %d、U4 违例 %d（探针命中数）" % (len(u2), len(u4)),
    })
    checks.extend(_visibility_semantics_checks(v, summary))
    return checks


def _visibility_semantics_checks(v, summary):
    """B-补-12：归属不了 → `undecidable`（不再退 else 判 pass）。

    * Kitty 全脱态：`Kitty.shirt_a/b` 只命中 AAO 合并网格且两合并块可见性不一致
      → 归属不了，`when` 依赖它们即判不了；三乳头键应落 `undecidable`。
    * RePoppin 全脱态：`RePoppin.parker` 多物体结论不一致（(A)Parker 不可见、领带可见）
      → 整件 unknown；同上判不了。

    判据：三行全 `undecidable`；实测无 outer/top 件可见；归属不了的件要出现在
    `summary.visibility_unknown` 这张「判不了清单」里（不是查无此人）。任何一行又变回
    pass（说明被按不可见处理）或违例都算 FAIL。
    """
    by_id = {sv.id: sv for sv in v.states}
    unknown_list = {x["state"]: set(x["parts"]) for x in (summary or {}).get("visibility_unknown", [])}
    targets = {
        "KittyA__naked": ("Kitty.shirt_a", "Kitty.shirt_b"),
        "KittyB__naked": ("Kitty.shirt_a", "Kitty.shirt_b"),
        "RePoppin__naked": ("RePoppin.parker",),
        "RePoppinHood__naked": ("RePoppin.parker",),
    }
    details, ok = [], True
    for sid, unknown_want in targets.items():
        sv = by_id.get(sid)
        if sv is None:
            ok = False
            details.append("%s 缺状态" % sid)
            continue
        rows = [f for f in v.rows if f.get("dep") == "kaguya.nipple_hidden_when_chest_covered"
                and f.get("state") == sid]
        vis = sv.eval_vis()
        outer_top = sorted(p for kind in ("outer", "top")
                           for p in sv.parts_by_kind.get(kind, [])
                           if vis.get(p))
        unknown = sv.vis_unknown()
        miss_unknown = [p for p in unknown_want if p not in unknown]
        # 相关件必须出现在 undecidable（visibility_unknown）清单里
        listed = unknown_list.get(sid, set())
        miss_listed = [p for p in unknown_want if p not in listed]
        bad_rows = [f for f in rows if f.get("status") != "undecidable"]
        vals = sorted({round(_num(f.get("actual")), 3) for f in rows})
        this_ok = (len(rows) == 3 and not bad_rows and not outer_top
                   and not miss_unknown and not miss_listed)
        ok = ok and this_ok
        details.append("%s: 行 %d、undecidable %d、实测可见 outer/top %s、"
                       "归属不了 %s、undecidable 清单 %s、实测值 %s"
                       % (sid, len(rows), len(rows) - len(bad_rows),
                          outer_top or "无", sorted(unknown) or "无",
                          sorted(listed) or "无", vals))
    return [{
        "name": "B-补-12 归属不了落 undecidable（Kitty/RePoppin 全脱态乳头键）",
        "ok": ok,
        "detail": "；".join(details),
    }]


def negative_sample_checks(v):
    """03 §4.5「负样本清单（工程A 一期可跑）」逐条，用实测数据独立核算。

    这些负样本与声明解耦：即使声明写得过宽（如把领带算进 parker 件），
    也不能把它们误报成缺陷。
    """
    checks = []
    body = (v.decl.get("avatar") or {}).get("body") or (v.profile or {}).get("mesh")

    # ① 鞋袜全关 → 脚型键不写
    foot_keys = set()
    for dep in (v.decl.get("deps") or []):
        for t in ([dep["target"]] if "target" in dep else (dep.get("targets") or [])):
            if not isinstance(t, dict) or t.get("mesh") != body:
                continue
            ks = [t["key"]] if "key" in t else (t.get("keys") or [])
            for k in ks:
                if "Foot" in k or "foot" in k:
                    foot_keys.add(k)
    n_off, bad = 0, 0
    for sv in v.states:
        if _num(sv.params.get("A2_Sho"), 1) != 0 or _num(sv.params.get("A2_Sok"), 1) != 0:
            continue
        n_off += 1
        for k in foot_keys:
            val, _p, _ak, _un = sv.value(body, k)
            if abs(val - ru.baseline_value(v.profile, k)) > 1e-9:
                bad += 1
    checks.append({
        "name": "负样本①鞋袜全关脚型键不写",
        "ok": bad == 0,
        "detail": "鞋袜全关状态 %d 个、脚型键 %d 个，非基线写 %d" % (n_off, len(foot_keys), bad),
    })

    # ② RePoppin：Parker 物体不可见时写 100 无害
    #
    # B-补-13：旧实现只遍历「status=violation 且 actual=100」的行（本批 0 条），
    # 于是无论 Parker 可不可见都恒 OK——空转。改成直接遍历**实测样本**：
    # 在全部状态里找 Parker_on==100 且 Parker 实测不可见的态，再看这些态有没有被误报。
    # 同时构造一条合成违例行，证明判据能报出来（不是恒真）。
    def _parker_bad(rows, parker_visible):
        if parker_visible:
            return 0
        return sum(1 for f in rows if f["status"] == "violation"
                   and f.get("dep") == "RePoppin.shirt_under_parker"
                   and _num(f.get("actual"), 0) == 100)

    samples, bad = [], 0
    shirt_meshes = v.part_smr_paths.get("RePoppin.shirt") or []
    for sv in v.states:
        on = False
        for m in shirt_meshes:
            val, _p, _ak, _u = sv.value(m, "Parker_on")
            if abs(_num(val) - 100) < 1e-9:
                on = True
                break
        if not on:
            continue
        pvis = sv.visible("RePoppin.parker")
        if pvis:
            continue
        rows = [f for f in v.rows
                if f.get("dep") == "RePoppin.shirt_under_parker" and f.get("state") == sv.id]
        samples.append((sv.id, rows))
        bad += _parker_bad(rows, pvis)
    # 合成样本：Parker 不可见 + 写 100，且被报成违例 → 判据应当数出来
    synthesized = _parker_bad(
        [{"status": "violation", "dep": "RePoppin.shirt_under_parker", "actual": 100}],
        False)
    checks.append({
        "name": "负样本②Parker 不可见时写 100 无害（B-补-13 非空转）",
        "ok": bad == 0 and len(samples) > 0 and synthesized == 1,
        "detail": "实测样本 %d 态（Parker_on=100 且 Parker 不可见）、误报 %d；"
                  "合成样本判据命中 %d（应为 1）" % (len(samples), bad, synthesized),
    })

    # ③ Kitty/RePoppin 无身体键（件上不与身体同名键重叠）
    body_norm = set()
    for sv in v.states:
        for k in (sv.by_mesh.get(body) or {}):
            m = ru._AAO_KEY_RE.match(k)
            body_norm.add(m.group(1) if m else k)
    overlap = 0
    for sv in v.states:
        for p, ks in sv.blendshapes.items():
            if "Kitty" not in p and "RePoppin" not in p:
                continue
            for k in ks:
                m = ru._AAO_KEY_RE.match(k)
                if (m.group(1) if m else k) in body_norm:
                    overlap += 1
    checks.append({
        "name": "负样本③Kitty/RePoppin 无身体键",
        "ok": overlap == 0,
        "detail": "Kitty/RePoppin 件上与身体同名的键 %d 个" % overlap,
    })

    # ④ 83 状态抓取点/重合命中均为 0
    gh = sum((sv.probes.get("grab_chain") or {}).get("hits", 0) for sv in v.states)
    ch = sum((sv.probes.get("coincident") or {}).get("hits", 0) for sv in v.states)
    checks.append({
        "name": "负样本④83 状态抓取点/重合命中 0",
        "ok": gh == 0 and ch == 0,
        "detail": "grab hits=%d、coincident hits=%d（%d 状态）" % (gh, ch, len(v.states)),
    })
    return checks


def print_report(v, summary, checks=None):
    print("=" * 72)
    print("verdict.py  %s   decl_hash=%s" % (v.tool_version, v.decl_hash[:19]))
    print("=" * 72)
    print("状态 %d 个，期望行 %d 条" % (summary["states"], summary["rows"]))
    print("判定：pass %d / violation %d；判不了 %d；dont_care %d"
          % (summary["status_counts"].get("pass", 0), summary["violations"],
             summary["undecided"], summary["dont_care"]))
    print("判定覆盖率 = 已判 %d / (已判 %d + 判不了 %d) = %.1f%%"
          % (summary["judged"], summary["judged"], summary["undecided"],
             summary["coverage"] * 100))
    print()
    print("-- 按规则/依赖的违例 --")
    any_v = False
    for f in v.rows + v.universal:
        if f["status"] != "violation":
            continue
        any_v = True
        print("  [%s] %s @%s :: %s" % (f.get("rule") or f.get("dep"), f.get("dep") or f.get("rule"),
                                       f.get("state"), f.get("message")))
    if not any_v:
        print("  （无）")
    print()
    print("-- 通用规则 --")
    for r, c in sorted(summary["universal"].items()):
        print("  %-5s %s" % (r, dict(c)))
    print()
    print("-- 豁免 --")
    for w in summary["waivers"]:
        print("  %s %s effective=%s suppressed=%d %s"
              % (w.get("rule") or w.get("dep"), w.get("parts"),
                 w.get("effective"), w.get("suppressed"), w.get("expired_reasons") or ""))
    print()
    print("-- no_data 清单 --")
    for n in summary["no_data"]:
        print("  [%s] ×%d %s（例：%s）" % (n["dep"], n["count"], n["reason"], n["example_state"]))
    print()
    print("-- undecidable 清单（判不了；归属不了的件只在这里，不许当不可见判 pass）--")
    if summary.get("undecidable"):
        for n in summary["undecidable"]:
            print("  [%s] target=%s ×%d" % (n["dep"], n["target"], n["count"]))
    else:
        print("  （无）")
    if summary.get("visibility_unknown_parts"):
        print("  归属不了的件（按状态数）：%s"
              % "、".join("%s×%d" % (x["part"], x["states"])
                          for x in summary["visibility_unknown_parts"]))
    for x in summary.get("visibility_unknown", [])[:20]:
        print("    %s: %s" % (x["state"], "、".join(x["parts"])))
    if summary["unmatched"]:
        print("-- unmatched（不猜）--")
        for u in summary["unmatched"][:40]:
            print("  %s" % json.dumps(u, ensure_ascii=False))
    if summary.get("part_unmatched"):
        print("-- 件名 unmatched（构后改名后备也匹配不上，按不可见/零值处理）--")
        for u in summary["part_unmatched"]:
            print("  %s %r ×%d 状态" % (u["kind"], u["declared"], u["states"]))
    if checks is not None:
        print()
        print("-- selftest --")
        for c in checks:
            print("  [%s] %s :: %s" % ("OK" if c["ok"] else "FAIL", c["name"], c["detail"]))
        print("ALL PASS" if all(c["ok"] for c in checks) else "SELFTEST FAIL")


def to_json(v, summary):
    return {
        "schema": SCHEMA,
        "tool": {"name": TOOL, "version": v.tool_version},
        "decl_hash": v.decl_hash,
        "project": (v.decl.get("avatar") or {}).get("project"),
        "inputs": {
            "decl": v.args.decl,
            "profile": v.args.profile,
            "t1": list(v.args.t1 or []),
            "geo": list(getattr(v.args, "geo", []) or []),
            "writers": bool(v.writers),
            "ma_analysis": bool(v.ma),
            "fx_final": bool(v.fx),
            "mapping": bool(v.mapping),
            "inventory": bool(v.inventory),
            "pb": bool(v.pb),
            "key_follow": bool(v.key_follow),
        },
        "batches": v.batches,
        "summary": summary,
        "findings": [_compact(f) for f in v.rows
                     if f["status"] in ("violation", "no_data", "undecidable", "unmatched")],
        "universal": [_compact(f) for f in v.universal],
        "pass_index": sorted(
            "%s|%s|%s|%s|%s" % (f.get("dep") or f.get("rule"), f.get("state"),
                                f.get("kind"), f.get("target"), f.get("metric"))
            for f in v.rows if f["status"] == "pass"),
    }


def do_diff(a_path, b_path):
    a = load_json(a_path)
    b = load_json(b_path)
    print("diff %s → %s" % (a_path, b_path))
    sa, sb = a.get("summary", {}), b.get("summary", {})
    for k in ("rows", "judged", "undecided", "violations", "coverage"):
        if sa.get(k) != sb.get(k):
            print("  %s: %s → %s" % (k, sa.get(k), sb.get(k)))
    pa = set(a.get("pass_index") or [])
    pb = set(b.get("pass_index") or [])
    if pa or pb:
        added = pb - pa
        removed = pa - pb
        print("  新增 pass %d、丢失 pass %d" % (len(added), len(removed)))
        for x in sorted(removed)[:40]:
            print("    - %s" % x)
        for x in sorted(added)[:40]:
            print("    + %s" % x)
    else:
        def keys(doc):
            return {"%s|%s|%s" % (f.get("dep"), f.get("state"), f.get("target"))
                    for f in doc.get("findings", []) if f.get("status") == "violation"}
        va, vb = keys(a), keys(b)
        print("  新增违例 %d、消失违例 %d" % (len(vb - va), len(va - vb)))
        for x in sorted(va - vb):
            print("    - %s" % x)
        for x in sorted(vb - va):
            print("    + %s" % x)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SELFTEST_DEFAULTS = {
    "decl": "工程A/_感知/decl.json",
    "profile": "开发工具/素体档案/Kaguya.yaml",
    "t1": ["_长程任务_20260918/审查产出/工程A/t1_full_probes"],
    "inventory": "工程A/_感知/out/inventory.json",
    "pb": "工程A/_感知/out/pb.json",
    "key_follow": "_长程任务_20260918/审查产出/key_follow/工程A.json",
    "thresholds": "开发工具/通用工具/审查/perception/thresholds.yaml",
}


def build_parser():
    p = argparse.ArgumentParser(description="T-14 校验器 verdict.py")
    p.add_argument("--decl", help="decl.json（T-02 展开产物）")
    p.add_argument("--profile", help="素体档案 YAML")
    p.add_argument("--t1", action="append", default=[], help="T1 状态输出目录（可多次）")
    p.add_argument("--geo", action="append", default=[], help="geo_*.json 文件或目录（可多次）")
    p.add_argument("--writers", help="writers.json（T-11）")
    p.add_argument("--ma-analysis", dest="ma_analysis", help="ma_analysis.json（T-12）")
    p.add_argument("--fx-final", dest="fx_final", help="fx_final.json（T-12）")
    p.add_argument("--mapping", help="mapping.json（T-12）")
    p.add_argument("--inventory", help="inventory.json（T-05，含 key_follow 段）")
    p.add_argument("--pb", help="pb.json（T-30）")
    p.add_argument("--key-follow", dest="key_follow", help="key_follow JSON（T-05/AK）")
    p.add_argument("--thresholds", help="thresholds.yaml")
    p.add_argument("--out", help="写 verdicts.json")
    p.add_argument("--diff", nargs=2, metavar=("A", "B"), help="比对两份 verdicts.json")
    p.add_argument("--selftest", action="store_true", help="用仓库内 工程A 数据自验")
    return p


def apply_selftest_defaults(args):
    d = SELFTEST_DEFAULTS

    def abspath(x):
        return x if os.path.isabs(x) else os.path.join(ROOT, x)
    if not args.decl:
        args.decl = abspath(d["decl"])
    if not args.profile:
        args.profile = abspath(d["profile"])
    if not args.t1:
        args.t1 = [abspath(x) for x in d["t1"]]
    else:
        args.t1 = [abspath(x) for x in args.t1]
    if not args.inventory:
        args.inventory = abspath(d["inventory"])
    if not args.pb:
        args.pb = abspath(d["pb"])
    if not args.key_follow:
        args.key_follow = abspath(d["key_follow"])
    if not args.thresholds:
        args.thresholds = abspath(d["thresholds"])
    return args


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.diff:
        return do_diff(args.diff[0], args.diff[1])
    if args.selftest:
        args = apply_selftest_defaults(args)
    if not args.decl:
        print("需要 --decl（或用 --selftest）", file=sys.stderr)
        return 2
    if not os.path.isabs(args.decl):
        args.decl = os.path.abspath(args.decl)
    if args.profile and not os.path.isabs(args.profile):
        args.profile = os.path.abspath(args.profile)
    if args.thresholds and not os.path.isabs(args.thresholds):
        args.thresholds = os.path.abspath(args.thresholds)
    args.t1 = [x if os.path.isabs(x) else os.path.abspath(x) for x in (args.t1 or [])]

    v = Verdict(args)
    v.load_states(args.t1)
    v.load_geo(getattr(args, "geo", []))
    v.run()
    summary = summarise(v)
    checks = selftest_checks(v, summary) if args.selftest else None
    if checks is not None:
        checks.extend(negative_sample_checks(v))
    print_report(v, summary, checks)
    if args.out:
        doc = to_json(v, summary)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, sort_keys=True, indent=2)
        print("\n写出 %s（%d 字节）" % (args.out, os.path.getsize(args.out)))
    if checks is not None:
        return 0 if all(c["ok"] for c in checks) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
