#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任务 D2（B-T33d）：R9「不可分辨」分流纯函数离线自检（不起 Unity）。
【项目沉淀】通用工具
适用素体：无关
相关素材：仓库内 R9 样例数据
工具链　：Python 3（离线）
可复用性：★ 针对特定任务的离线自检，主要供参考
用途　　：R9「不可分辨」分流纯函数离线自检（不起 Unity），区分候选真等价与键没写进去。


为什么有这份：B-T08c/CS 让同一状态里六项度量完全一致的候选互标 `indistinguishable_with`，
但**不问读回**就统一报「多半是没清零或键没写进去」、把 `recommended` 置 null——把两类完全不同的
情况混成了一种：
  ① 候选**确实等价**：`applied_readback` 两两不同且都非空（各自的键都真写进去了），只是量出来
     一样。工程B袜组就是这种（`seq_lopear_r9/01_measure/r9_Set05_sock.json` 的 `m_sho_off`：
     `Ankle=100`、`none`、`Ankle+Foot+Toe` 读回各不相同，度量全等）。这种该给「任选其一」，
     `recommended` 不该置 null。
  ② **没清零 / 键没写进去**：读回为空或相同，或清零域里有键没匹配到（`zero_missing` 非空）。
     鞋组人为去掉 `candidates_zero` 后，`none` 与 `current_no_zero` 都不写键、读回都空，
     量到的是服装驱动的同一个姿势——这种才该作废推荐。

本脚本把 `unity/Editor/AuditStateDriver.cs` 里 `R9_INDISTINGUISHABLE_RULES_BEGIN/END` 标记之间的
纯层（只引用 System，不碰 UnityEngine）整段抽出来，裹进一个 wrapper 类，配最小 C# 测试程序，
用 mono 的 mcs 编译后 `mono` 运行——**测的就是生产同一份源码**，不是重新写一份。

覆盖：
  ① 袜组生产夹具（`r9_Set05_sock.json` / `m_sho_off`）→ `candidate_equivalent`；
  ② 鞋组去掉 `candidates_zero` 的夹具（`r9_Set05_shoe.json` / `m_sok_off`，把 zero_applied/zero_missing
     清空、读回只留候选自己的键）里两个「不写键」候选 → `not_zeroed`；
  ③ 抽象边界：读回两两不同=等价；读回相同 / 有写键候选读回为空 / zero_missing 非空 → 没清零；
     `current_no_zero`（keys 与清零域都空）不参与「该写」计数，不能把它的空读回误判成没写进去。

产物落到 `_长程任务_20260918/派工/tmp/d2/`（.cs / .exe / .log），不改任何工程文件。
用法：`python3 开发工具/通用工具/审查/perception/selftest_r9_indistinguishable.py`
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]   # …/perception/selftest_*.py → parents[0]=perception … parents[4]=工作区根
DRIVER = ROOT / "开发工具/通用工具/审查/unity/Editor/AuditStateDriver.cs"
MEASURE = ROOT / "_长程任务_20260918/审查产出/工程B/seq_lopear_r9/01_measure"
SOCK = MEASURE / "r9_Set05_sock.json"
SHOE = MEASURE / "r9_Set05_shoe.json"
OUT = ROOT / "_长程任务_20260918/派工/tmp/d2"

sys.path.insert(0, str(ROOT / "开发工具/通用工具"))
import kit_env  # noqa: E402  mono/mcs 取自 Unity 自带的 MonoBleedingEdge（kit.env 的 UNITY_DATA / UNITY_EDITOR_ROOT+UNITY_VERSION）

UNITY_DATA = kit_env.unity_data()
MONO = UNITY_DATA / "MonoBleedingEdge/bin/mono"
MCS = UNITY_DATA / "MonoBleedingEdge/lib/mono/4.5/mcs.exe"

BEGIN = "// >>> R9_INDISTINGUISHABLE_RULES_BEGIN"
END = "// <<< R9_INDISTINGUISHABLE_RULES_END"


def cs_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def extract_rules(text):
    if BEGIN not in text or END not in text:
        raise SystemExit("AuditStateDriver.cs 里找不到 R9_INDISTINGUISHABLE_RULES 标记，无法抽取纯层。")
    i = text.index(BEGIN)
    j = text.index(END)
    body = text[text.index("\n", i) + 1:j]
    # 纯层不得引用 UnityEngine；抽出来单独编译能过就是证明（注释里提到类型名不算）。
    code_lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith("//")]
    code = "\n".join(code_lines)
    for bad in ("using UnityEngine", "UnityEngine.", "MonoBehaviour", "Vector3", "SkinnedMeshRenderer", "new Mesh"):
        if bad in code:
            raise SystemExit("纯层引用了 Unity 类型 '" + bad + "'，离线自检无法编译。")
    return body.rstrip()


def fmt_num(v):
    """与生产 AuditUtil.F 同为「最多 4 位小数」口径；这里只用于判读回是否相同，格式一致即可。"""
    return ("%.4f" % float(v)).rstrip("0").rstrip(".")


def load_rows(path, state_id):
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    for st in d.get("states", []):
        if st.get("state") == state_id:
            return st.get("rows", [])
    return None


def row_to_input(row):
    """生产 ClassifyR9Indist 的口径：keys→HasKeys；zero_applied/zero_missing→HasZeroDomain。"""
    readback = row.get("applied_readback") or {}
    keys = row.get("keys") or {}
    za = row.get("zero_applied") or {}
    zm = row.get("zero_missing") or []
    sig = ";".join("%s=%s" % (k, fmt_num(readback[k])) for k in sorted(readback))
    return {
        "id": row.get("candidate", "?"),
        "has_keys": len(keys) > 0,
        "has_zero": len(za) > 0 or len(zm) > 0,
        "rb_count": len(readback),
        "sig": sig,
        "zm_count": len(zm),
    }


def shoe_without_zero(path, state_id):
    """去掉 candidates_zero 的鞋组：清零域清空，读回只留候选自己的键（没列键=读回空）。"""
    rows = load_rows(path, state_id)
    if rows is None:
        return None
    out = []
    for r in rows:
        keys = r.get("keys") or {}
        readback = dict(keys)
        sig = ";".join("%s=%s" % (k, fmt_num(readback[k])) for k in sorted(readback))
        out.append({
            "id": r.get("candidate", "?"),
            "has_keys": len(keys) > 0,
            "has_zero": False,          # 没有清零域
            "rb_count": len(readback),
            "sig": sig,
            "zm_count": 0,
        })
    return out


def emit_inputs(name, inputs):
    lines = []
    for it in inputs:
        lines.append(
            '                new R9IndistOfflineRules.R9IndistInput { CandidateId = "%s", HasKeys = %s, '
            'HasZeroDomain = %s, ReadbackCount = %d, ReadbackSignature = "%s", ZeroMissingCount = %d },'
            % (cs_escape(it["id"]), "true" if it["has_keys"] else "false",
               "true" if it["has_zero"] else "false", it["rb_count"], cs_escape(it["sig"]), it["zm_count"]))
    return ("        static List<R9IndistOfflineRules.R9IndistInput> %s()\n"
            "        {\n            return new List<R9IndistOfflineRules.R9IndistInput>\n            {\n%s\n            };\n        }\n"
            % (name, "\n".join(lines)))


def build_program(rules_region, sock_inputs, shoe_inputs):
    if sock_inputs is None:
        sock_method = ("        static List<R9IndistOfflineRules.R9IndistInput> SockRows()\n"
                       "        {\n            return new List<R9IndistOfflineRules.R9IndistInput>();\n        }\n")
        sock_note = 'Console.WriteLine("  SKIP  袜组生产夹具不存在：" + SOCK_PATH);'
    else:
        sock_method = emit_inputs("SockRows", sock_inputs)
        sock_note = 'Console.WriteLine("  袜组 m_sho_off 行数=" + SockRows().Count + "（" + SOCK_PATH + "）");'

    if shoe_inputs is None:
        shoe_method = ("        static List<R9IndistOfflineRules.R9IndistInput> ShoeNoZeroRows()\n"
                       "        {\n            return new List<R9IndistOfflineRules.R9IndistInput>();\n        }\n")
        shoe_note = 'Console.WriteLine("  SKIP  鞋组生产夹具不存在：" + SHOE_PATH);'
    else:
        shoe_method = emit_inputs("ShoeNoZeroRows", shoe_inputs)
        shoe_note = ('Console.WriteLine("  鞋组 m_sok_off 去掉 candidates_zero 后「不写键」行数=" + ShoeNoZeroRows().Count'
                     ' + "（" + SHOE_PATH + "）");')

    template = r'''// 任务 D2 离线自检（由 perception/selftest_r9_indistinguishable.py 自动生成）
using System;
using System.Collections.Generic;

namespace AvatarAudit
{
    // 纯层从 AuditStateDriver 类成员里抽出，原样裹进这个 wrapper（代码一字未改）。
    internal static class R9IndistOfflineRules
    {
__RULES__
    }

    internal static class R9IndistOfflineSelfCheck
    {
        static int pass = 0, fail = 0;
        const string SOCK_PATH = "__SOCK_PATH__";
        const string SHOE_PATH = "__SHOE_PATH__";

        static void Check(string name, bool ok) { Check(name, ok, ""); }
        static void Check(string name, bool ok, string detail)
        {
            if (ok) { pass++; Console.WriteLine("  PASS  " + name); }
            else { fail++; Console.WriteLine("  FAIL  " + name + "   " + detail); }
        }

        static string Kind(R9IndistOfflineRules.R9IndistResult r)
        {
            return r.Kind == R9IndistOfflineRules.R9IndistKind.CandidateEquivalent ? "candidate_equivalent" : "not_zeroed";
        }

        static R9IndistOfflineRules.R9IndistResult Classify(List<R9IndistOfflineRules.R9IndistInput> rows)
        {
            return R9IndistOfflineRules.ClassifyR9Indistinguishable(rows);
        }

        static R9IndistOfflineRules.R9IndistInput In(string id, bool hasKeys, bool hasZero, int rb, string sig, int zm)
        {
            return new R9IndistOfflineRules.R9IndistInput
            {
                CandidateId = id, HasKeys = hasKeys, HasZeroDomain = hasZero,
                ReadbackCount = rb, ReadbackSignature = sig, ZeroMissingCount = zm
            };
        }

__SOCK_METHOD__
__SHOE_METHOD__

        static void TestAbstractRules()
        {
            Console.WriteLine("-- ③ 抽象边界：读回两两不同=等价；为空/相同/zero_missing=没清零 --");
            // 两个都写键、读回不同、清零域无缺 → 等价
            var eq = Classify(new List<R9IndistOfflineRules.R9IndistInput>
            {
                In("A=100", true, true, 3, "A=100;F=0;T=0", 0),
                In("A=0",   true, true, 3, "A=0;F=0;T=0", 0),
            });
            Check("③ 两个写键候选、读回不同 → candidate_equivalent",
                Kind(eq) == "candidate_equivalent" && eq.Writers == 2 && eq.DistinctReadbacks == 2,
                "kind=" + Kind(eq) + " writers=" + eq.Writers + " distinct=" + eq.DistinctReadbacks);

            // current_no_zero（keys 与清零域都空）混进来，不影响等价判定
            var eq2 = Classify(new List<R9IndistOfflineRules.R9IndistInput>
            {
                In("A=100", true, true, 3, "A=100;F=0;T=0", 0),
                In("A=0",   true, true, 3, "A=0;F=0;T=0", 0),
                In("current_no_zero", false, false, 0, "", 0),
            });
            Check("③ current_no_zero 的空读回不参与「该写」计数 → 仍判等价",
                Kind(eq2) == "candidate_equivalent" && eq2.Writers == 2,
                "kind=" + Kind(eq2) + " writers=" + eq2.Writers);

            // 读回相同 → 没清零
            var same = Classify(new List<R9IndistOfflineRules.R9IndistInput>
            {
                In("A=100", true, true, 1, "A=100", 0),
                In("A=50",  true, true, 1, "A=50", 0),
                In("A_dup", true, true, 1, "A=50", 0),
            });
            Check("③ 读回相同（A=50 与 A_dup 同读回）→ not_zeroed",
                Kind(same) == "not_zeroed", "kind=" + Kind(same) + " reason=" + same.Reason);

            // 本该写键却读回为空 → 没写进去
            var empty = Classify(new List<R9IndistOfflineRules.R9IndistInput>
            {
                In("A=100", true, true, 1, "A=100", 0),
                In("B=100", true, true, 0, "", 0),
            });
            Check("③ 有写键候选读回为空 → not_zeroed 且点名「键没写进去」",
                Kind(empty) == "not_zeroed" && empty.Reason.Contains("读回为空"),
                "kind=" + Kind(empty) + " reason=" + empty.Reason);

            // zero_missing 非空 → 没清零（即使读回各不相同）
            var missing = Classify(new List<R9IndistOfflineRules.R9IndistInput>
            {
                In("A=100", true, true, 1, "A=100", 0),
                In("A=0",   true, true, 1, "A=0", 1),
            });
            Check("③ zero_missing 非空 → not_zeroed 且点名清零域漏键",
                Kind(missing) == "not_zeroed" && missing.AnyZeroMissing && missing.Reason.Contains("zero_missing"),
                "kind=" + Kind(missing) + " reason=" + missing.Reason);

            // 组里全是「不写键」候选（去掉 candidates_zero 的鞋组形态）→ 没清零
            var nowrite = Classify(new List<R9IndistOfflineRules.R9IndistInput>
            {
                In("none", false, false, 0, "", 0),
                In("current_no_zero", false, false, 0, "", 0),
            });
            Check("③ 组里没有两个读回各异的写键候选 → not_zeroed",
                Kind(nowrite) == "not_zeroed" && nowrite.Writers == 0,
                "kind=" + Kind(nowrite) + " writers=" + nowrite.Writers + " reason=" + nowrite.Reason);
        }

        static void TestSockFixture()
        {
            Console.WriteLine("-- ① 袜组生产夹具：读回各不相同、度量全等 → 候选等价 --");
__SOCK_NOTE__
            var rows = SockRows();
            if (rows.Count == 0) return;
            var r = Classify(rows);
            Console.WriteLine("  kind=" + Kind(r) + " group=[" + string.Join(",", r.Group.ToArray()) + "]");
            Console.WriteLine("  writers=" + r.Writers + " distinct_readbacks=" + r.DistinctReadbacks
                + " any_zero_missing=" + r.AnyZeroMissing);
            Console.WriteLine("  reason=" + r.Reason);
            Check("① 袜组 m_sho_off → candidate_equivalent（recommended 不该作废）",
                Kind(r) == "candidate_equivalent", "kind=" + Kind(r) + " reason=" + r.Reason);
            Check("① 袜组里至少 3 个写键候选、读回两两不同",
                r.Writers >= 3 && r.DistinctReadbacks == r.Writers && !r.AnyZeroMissing,
                "writers=" + r.Writers + " distinct=" + r.DistinctReadbacks);
        }

        static void TestShoeNoZeroFixture()
        {
            Console.WriteLine("-- ② 鞋组去掉 candidates_zero：不写键候选读回都空 → 没清零 --");
__SHOE_NOTE__
            var rows = ShoeNoZeroRows();
            if (rows.Count == 0) return;
            var r = Classify(rows);
            Console.WriteLine("  kind=" + Kind(r) + " group=[" + string.Join(",", r.Group.ToArray()) + "]");
            Console.WriteLine("  writers=" + r.Writers + " distinct_readbacks=" + r.DistinctReadbacks);
            Console.WriteLine("  reason=" + r.Reason);
            Check("② 鞋组不写键候选 → not_zeroed（仍报「没清零」）",
                Kind(r) == "not_zeroed", "kind=" + Kind(r) + " reason=" + r.Reason);
            // 对照：不清零前（生产带 candidates_zero）这里读回非空不同；本夹具已故意清零域清空。
            Check("② 该组里确实有候选「keys 空且清零域空」",
                r.Writers < rows.Count, "writers=" + r.Writers + " rows=" + rows.Count);
        }

        public static int Main(string[] args)
        {
            Console.WriteLine("== R9 不可分辨分流 纯离线自检（perception/selftest_r9_indistinguishable.py）==");
            TestAbstractRules();
            TestSockFixture();
            TestShoeNoZeroFixture();
            Console.WriteLine(string.Format("== {0} PASS / {1} FAIL ==", pass, fail));
            return fail == 0 ? 0 : 1;
        }
    }
}
'''
    prog = template.replace("__RULES__", rules_region)
    prog = prog.replace("__SOCK_PATH__", cs_escape(str(SOCK)))
    prog = prog.replace("__SHOE_PATH__", cs_escape(str(SHOE)))
    prog = prog.replace("__SOCK_METHOD__", sock_method)
    prog = prog.replace("__SHOE_METHOD__", shoe_method)
    prog = prog.replace("__SOCK_NOTE__", sock_note)
    prog = prog.replace("__SHOE_NOTE__", shoe_note)
    return prog


def main():
    if not MONO.exists() or not MCS.exists():
        raise SystemExit("找不到 mono/mcs：%s / %s（在 kit.env 设 UNITY_DATA）" % (MONO, MCS))
    text = DRIVER.read_text(encoding="utf-8")
    rules = extract_rules(text)

    sock_rows = load_rows(SOCK, "m_sho_off")
    sock_inputs = [row_to_input(r) for r in sock_rows] if sock_rows is not None else None
    shoe_rows = shoe_without_zero(SHOE, "m_sok_off")
    if shoe_rows is not None:
        # 只留「不写键」候选：去掉清零后它们读回都空、量到同一个服装驱动姿势。
        shoe_inputs = [r for r in shoe_rows if not r["has_keys"]]
    else:
        shoe_inputs = None

    prog = build_program(rules, sock_inputs, shoe_inputs)

    OUT.mkdir(parents=True, exist_ok=True)
    cs = OUT / "R9IndistOfflineSelfCheck.cs"
    exe = OUT / "r9_indist_selfcheck.exe"
    log = OUT / "r9_indist_selfcheck.log"
    cs.write_text(prog, encoding="utf-8")

    print("抽取纯层：%d 行，来自 %s" % (len(rules.splitlines()), DRIVER.relative_to(ROOT)))
    print("生成：%s" % cs.relative_to(ROOT))
    compile_cmd = [str(MONO), str(MCS), "-nologo", "-out:" + str(exe), str(cs)]
    cp = subprocess.run(compile_cmd, capture_output=True, text=True)
    if cp.returncode != 0:
        print(cp.stdout)
        print(cp.stderr, file=sys.stderr)
        raise SystemExit("mcs 编译失败 EXIT=%d" % cp.returncode)
    run = subprocess.run([str(MONO), str(exe)], capture_output=True, text=True)
    out = run.stdout + run.stderr
    print(out)
    log.write_text(out, encoding="utf-8")
    print("（日志：%s）" % log.relative_to(ROOT))
    return run.returncode


if __name__ == "__main__":
    sys.exit(main())
