#!/bin/sh
# 蓝盾 CI 工作区定位诊断（POSIX sh，兼容容器 /bin/sh）
#
# 用途：当 tools/ci_setup.py 报 "can't open file 'tools/ci_setup.py'" 时，
#       先单独跑这个脚本，它会打印完整目录结构并给出可直接粘贴的 cd 命令。
#
# 设计原则：**绝不让诊断脚本自己失败**。因此：
#   - 不用 set -e（诊断要尽可能跑完）
#   - 不依赖 head/sed/grep 等可能缺失的工具（纯 sh 内建 + find/ls）
#   - 每一步都做存在性判断

echo "=============================================================="
echo "蓝盾 CI 工作区定位诊断"
echo "=============================================================="

echo ""
echo "--- 1. 当前工作目录 ---"
pwd

echo ""
echo "--- 2. 当前目录内容 ---"
ls -la 2>/dev/null || echo "  (ls 不可用)"

echo ""
echo "--- 3. 蓝盾内置变量 ---"
echo "WORKSPACE            = ${WORKSPACE:-<空>}"
echo "BK_CI_PROJECT_NAME   = ${BK_CI_PROJECT_NAME:-<空>}"
echo "BK_CI_PIPELINE_ID    = ${BK_CI_PIPELINE_ID:-<空>}"
echo "BK_CI_BUILD_ID       = ${BK_CI_BUILD_ID:-<空>}"
echo "CI_WORKSPACE         = ${CI_WORKSPACE:-<空>}"

echo ""
echo "--- 4. 向上追溯（查找含 run_tests.py + pytest.ini 的层级）---"
found=""
d=$(pwd)
i=0
while [ $i -lt 8 ]; do
  echo "  [$i] $d"
  if [ -f "$d/run_tests.py" ]; then
    if [ -f "$d/pytest.ini" ]; then
      echo "        ^^^ 命中工程根（run_tests.py + pytest.ini 均存在）"
      found="$d"
      break
    else
      echo "        ^^^ 有 run_tests.py 但缺 pytest.ini，可能不是工程根"
    fi
  fi
  parent=$(dirname "$d" 2>/dev/null)
  if [ -z "$parent" ] || [ "$parent" = "$d" ]; then break; fi
  d="$parent"
  i=$((i + 1))
done

echo ""
echo "--- 5. 向下搜索 run_tests.py（最多 5 层）---"
if [ -n "$found" ]; then
  echo "  已在第 4 步命中，跳过向下搜索。"
else
  hits=$(find . -maxdepth 5 -name run_tests.py -not -path "*/.git/*" 2>/dev/null)
  if [ -n "$hits" ]; then
    # 纯 sh 逐行读取，不依赖 head
    first=""
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      echo "  命中: $line"
      if [ -z "$first" ]; then first="$line"; fi
    done <<EOF
$hits
EOF
    cand=$(dirname "$first" 2>/dev/null)
    echo ""
    echo "  首个候选工程根: $cand"
    if [ -f "$cand/pytest.ini" ]; then
      found="$cand"
    else
      echo "  (该候选缺 pytest.ini，继续看下面第 6 步的完整扫描)"
    fi
  else
    echo "  未找到 run_tests.py —— 代码可能未拉取到本 Job 的工作区。"
    echo "  请检查【拉取代码】插件是否已添加并勾选“构建前拉取”。"
  fi
fi

echo ""
echo "--- 6. 完整目录扫描（深度 3，标注哪里是工程根）---"
# 用 python 做扫描（蓝盾镜像基本都有 python），比 shell 递归更可靠
PY=$(command -v python3 || command -v python || true)
if [ -n "$PY" ]; then
  "$PY" - <<'PYEOF'
import os
markers = ("run_tests.py", "pytest.ini")
base = os.getcwd()
count = 0
for root, dirs, files in os.walk(base):
    depth = root[len(base):].count(os.sep)
    if depth >= 3:
        dirs[:] = []
        continue
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
    rel = os.path.relpath(root, base)
    hit = [m for m in markers if m in files]
    flag = "  <== 含 " + ", ".join(hit) if hit else ""
    print(f"  {rel}{flag}")
    count += 1
    if count > 120:
        print("  ... (目录过多，已截断)")
        break
PYEOF
else
  echo "  (无 python，退化为 ls 顶层)"
  for entry in */; do
    [ -d "$entry" ] || continue
    if [ -f "${entry}run_tests.py" ]; then
      echo "  $entry -> 含 run_tests.py，是工程根"
    else
      echo "  $entry"
    fi
  done
fi

echo ""
echo "=============================================================="
if [ -n "$found" ]; then
  # 转成绝对路径，避免相对路径歧义
  abs=$(cd "$found" 2>/dev/null && pwd)
  echo "结论: 工程根目录 = ${abs:-$found}"
  echo ""
  echo "在该 Stage 的每个 Shell Task 开头粘贴以下前导片段："
  echo ""
  echo '  set -e'
  echo '  PY=$(command -v python3 || command -v python)'
  echo '  ROOT=""'
  echo '  for f in $(find . -maxdepth 4 -name run_tests.py 2>/dev/null); do'
  echo '    d=$(dirname "$f")'
  echo '    if [ -f "$d/pytest.ini" ]; then ROOT="$d"; break; fi'
  echo '  done'
  echo '  [ -z "$ROOT" ] && { echo "!! 未找到工程根"; ls -la; exit 1; }'
  echo '  cd "$ROOT" && echo "工程根: $(pwd)"'
  echo ""
  echo "或直接写死（本次诊断结果）："
  echo "  cd \"${abs:-$found}\""
else
  echo "结论: 未定位到工程根。请检查："
  echo "  1. 【拉取代码】插件是否已添加到本 Job"
  echo "  2. 插件的【工作目录】设置（可能指定到了非预期路径）"
  echo "  3. 代码源是否已正确关联到本流水线"
  echo "  4. 上方第 3 节的 WORKSPACE 变量值是否符合预期"
fi
echo "=============================================================="
