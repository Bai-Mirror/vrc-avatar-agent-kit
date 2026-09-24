#!/bin/bash
# 【项目沉淀】通用工具
# 适用素体：无关          相关素材：无
# 可复用性：★★★ 换个单子直接能用
# 用途　　：崩溃 / 上下文压缩 / 新会话之后的「基线重核」：内存、Unity 与 DSH 进程、锁、各工程未提交改动与状态头、进行中待办。只读，不改任何东西。
# 为什么（工作流审理 2026-09-23 根因 6）：错时间戳、卷文件、19 分钟失效的计划都出在 OOM 之后、压缩之中、无人交互地连续重试。
#   缺的是「灾后先对一次现实再继续」。由 .claude/hooks/session-start.js 在 compact/resume/startup 时自动跑并注入；也可手动跑。
. "$(dirname "${BASH_SOURCE[0]}")/kit_env.sh"   # W＝工作区根
# 工程目录：COMM-*/ 加 kit.env 的 EXTRA_PROJECT_GLOBS（空格分隔的 glob，如 "私单_*/ 工程B/"）
PROJECT_GLOBS="COMM-*/ ${EXTRA_PROJECT_GLOBS:-}"
cd "$W" || exit 1
echo "【基线重核 $(date '+%m-%d %H:%M')】"
echo "内存 available: $(LC_ALL=C free -g | awk '/^Mem:/{print $7}') GB（<8 不起新 DSH/批处理）"
echo "-- Unity 进程（匹配 …/Editor/Unity 可执行文件）:"
found=0
while read -r pid rest; do
  [ -z "$pid" ] && continue; found=1
  et=$(ps -o etime= -p "$pid" | tr -d ' '); rss=$(( $(ps -o rss= -p "$pid" 2>/dev/null || echo 0) / 1024 ))
  proj=$(echo "$rest" | grep -oE -- '-projectPath "?[^" ]+' | sed 's/-projectPath "\?//' | xargs -r basename 2>/dev/null)
  mode=$(echo "$rest" | grep -q -- '-batchmode' && echo 批处理 || echo 交互)
  echo "  pid $pid  $mode  $proj  etime $et  rss ${rss}MB"
done < <(pgrep -af 'Editor/Unity( |$)' | grep -v -e 'pgrep' -e 'UnityShaderCompiler' -e 'UnityPackageManager')
[ $found = 0 ] && echo "  无"
echo "-- DSH 会话: $(pgrep -fc '^[^ ]*node [^ ]*/bin\.js --profile headless') 个（上限 4，与 dsh_task.js 同口径）"
pgrep -af 'dsh_task\.js' | grep -oE -- '--task-file [^ ]+' | sed 's/--task-file //' | xargs -r -n1 basename 2>/dev/null | sed 's/^/    /'
echo "-- 锁:"
if [ -f "$HOME/.dsh/handoff.lock" ]; then
  h=$(python3 -c "import json;d=json.load(open('$HOME/.dsh/handoff.lock'));print(d.get('kind'),d.get('holder'),d.get('pid'),d.get('since'))" 2>/dev/null)
  pid=$(echo "$h" | awk '{print $3}'); alive=死; [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && alive=活
  echo "  handoff.lock: $h → 持有者进程$alive$( [ $alive = 死 ] && echo '（可删）')"
else echo "  handoff.lock: 无"; fi
for d in $PROJECT_GLOBS; do
  [ -d "$d" ] || continue
  n=${d%/}
  if [ -f "$n/Temp/UnityLockfile" ]; then
    if pgrep -f "Editor/Unity.*-projectPath.*$n" >/dev/null; then echo "  $n: UnityLockfile 在，进程在（不许删锁、不许另起实例）"
    else echo "  $n: UnityLockfile 在，无对应 Unity 进程（陈旧锁，可删）"; fi
  fi
done
echo "-- 各工程未提交 / 最近提交 / 状态头摘要:"
for d in $PROJECT_GLOBS; do
  [ -d "$d" ] || continue
  n=${d%/}; c=$(git -c core.quotepath=false status --porcelain -- "$n" | wc -l)
  last=$(git -c core.quotepath=false log -1 --format='%h %ad' --date=format:'%m-%d %H:%M' -- "$n")
  echo "  $n: 未提交 $c；最近提交 $last"
  awk '/状态头:BEGIN/{f=1;next}/状态头:END/{f=0}f' "$n/_施工记录.md" 2>/dev/null | grep -E '当前状态|阶段 / 交付状态|最近一步|^  1\.' | cut -c1-150 | sed 's/^/     /'
done
echo "-- 进行中 [~]（账本）:"
grep -h '^\s*- \[~\]' */_任务账本.md _长程任务_*/账本_*.md _长程任务_*/任务账本.md 2>/dev/null | head -10 | cut -c1-140 | sed 's/^/  /'
n=$(cat */_施工记录.md _长程任务_*/施工记录.md 2>/dev/null | grep -c '待蒸馏'); echo "-- 待蒸馏标签: $n 条（收尾蒸馏代理处理）"
