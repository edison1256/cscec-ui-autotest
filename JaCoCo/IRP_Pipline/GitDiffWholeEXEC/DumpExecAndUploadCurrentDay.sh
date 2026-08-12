#!/bin/bash
set -euo pipefail  # 启用严格模式

# ======================== 配置区域 ========================
APP_DIR="/app"
JACOCO_DIR="/data/logs/jacoco"
ARTIFACTORY_URL="https://devops.cscec.com/repo/repository/jspt-generic/jacoco/exec"
CREDENTIALS="${ARTIFACTORY_USER:-20431644}:${ARTIFACTORY_PASSWORD:-AP9EZniqgqnuSHqmHM3NtUfUgFT}"
today=$(date +%Y%m%d)
start_of_day=$(date +"%Y-%m-%d 00:00:00")  # 当天时间戳起点

# ======================== 日志函数 ========================
log() {
  printf "[%s] %s\n" "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
}

# ======================== 容器操作函数 ========================
process_container() {
  local container_id=$1
  local container_name=$2

  # 容器内操作
  docker exec "$container_id" sh -c "
    chmod 777 $APP_DIR/jacoco.sh &&
    $APP_DIR/jacoco.sh &&
    mkdir -p $JACOCO_DIR/exec/$container_id &&
    cp $APP_DIR/exec.tar $JACOCO_DIR/exec/$container_id/ &&
    chmod -R 777 $JACOCO_DIR
  " || { log "容器操作失败: $container_name"; exit 1; }

  # 复制覆盖率文件
  docker cp "$container_id:$JACOCO_DIR" "$APP_DIR" || { log "复制日志失败: $container_name"; exit 1; }
  docker cp "$container_id:$APP_DIR/app.jar" "$APP_DIR/app_$container_name.jar" || { log "复制JAR失败: $container_name"; exit 1; }
}

# ======================== 主流程 ========================
main() {
  # 清理旧文件
  find "$JACOCO_DIR" -name "app.jar" -delete 2>/dev/null

  # 获取目标容器
  containers=$(docker ps --filter "name=irp-business" --format '{{.ID}} {{.Image}}' | grep -v harbor)
  container_count=$(echo "$containers" | wc -l)

  # 验证容器数量
  case $container_count in
    0) log "未找到有效容器"; exit 0 ;;
    1|2) : ;;
    *) log "发现 $container_count 个容器，超过预期数量"; exit 1 ;;
  esac

  # 处理每个容器
  echo "$containers" | while read -r id image; do
    process_container "$id" "$image"
  done

  # 处理覆盖率文件
  cd "$APP_DIR/jacoco" || { log "目录切换失败"; exit 1; }

  # 仅处理当天生成的exec文件
  log "正在收集当天($today)的覆盖率数据..."
  exec_files=()
  while IFS= read -r -d $'\0' file; do
    if [ "$(date -r "$file" +%Y%m%d)" == "$today" ]; then
      exec_files+=("$file")
    fi
  done < <(find . -name "jacoco*.exec" -print0)

  # 压缩上传
  if [ ${#exec_files[@]} -gt 0 ]; then
    zip -jT "jacoco_exec_${today}.zip" "${exec_files[@]}" || { log "压缩失败"; exit 1; }
    curl --fail --progress-bar \
      -u "$CREDENTIALS" \
      -T "jacoco_exec_${today}.zip" \
      "$ARTIFACTORY_URL/${today}/${AGILE_PIPELINE_BUILD_ID}/jacoco_exec_${today}.zip" || { log "上传失败"; exit 1; }
    log "覆盖率数据上传成功 (文件数: ${#exec_files[@]})"
  else
    log "未找到当天生成的覆盖率文件"
  fi
}

# ======================== 执行入口 ========================
main "$@"
