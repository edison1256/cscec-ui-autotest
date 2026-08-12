#!/bin/bash
# 下载覆盖率数据生成报告并展示
set -euo pipefail  # 启用严格错误检查

# 配置环境变量（待优化：在CI/CD环境变量里配置）
CREDENTIALS="20431644:AP9EZniqgqnuSHqmHM3NtUfUgFT"  # 改为从环境变量读取更安全
BASE_URL="https://devops.cscec.com/repo/repository/jspt-generic"
today=$(date +%Y%m%d)

# 检查必要环境变量
[[ -z "${AGILE_PIPELINE_BUILD_ID}" ]] && {
    echo "ERROR: AGILE_PIPELINE_BUILD_ID is not defined"
    exit 1
}

# 带重试的下载解压函数
download_and_unzip() {
    local file_name=$1
    local max_retries=6
    local retry_count=0
    local http_status

    local url="${BASE_URL}/jacoco/exec/${today}/${AGILE_PIPELINE_BUILD_ID}/${file_name}"

    while (( retry_count < max_retries )); do
        http_status=$(curl -u "$CREDENTIALS" -w "%{http_code}" -O "$url" -L -s)

        if [[ "$http_status" == 200 ]]; then
            echo "Successfully downloaded ${file_name}"
            if unzip -o -q "$file_name"; then
                rm "$file_name"  # 解压后清理
                return 0
            else
                echo "Unzip failed for ${file_name}"
                return 1
            fi
        else
            echo "Attempt $((retry_count+1)) failed: HTTP ${http_status}"
            ((retry_count++))
            sleep $((retry_count * 5))
        fi
    done

    echo "ERROR: Failed to download ${file_name} after ${max_retries} attempts"
    return 1
}

# 主执行流程
(
    echo "==== Starting Download Process ===="
    download_and_unzip "irp_server_code.zip" || exit 1
    download_and_unzip "irp_server_class.zip" || exit 1
    download_and_unzip "jacoco_exec.zip" || exit 1

    # 单独处理 jacococli.jar
    if ! curl -u "$CREDENTIALS" -f -L -O "${BASE_URL}/jacoco/jar/jacococli.jar"; then
        echo "ERROR: Failed to download jacococli.jar (HTTP ${http_status})"
        exit 1
    fi
) 2>&1 | tee -a download.log  # 记录完整日志



echo "==== Generating Report ===="


# 将文件路径转换为类名格式
convert_to_classnames() {
  echo "$1" | while read -r file; do
    # 移除.java扩展名
    class_name=${file%.java}
    # 转换路径为包名格式
    class_name=${class_name//\//.}
    # 过滤匿名类和内部类
    grep -vE '\$[0-9]+\$' <<< "$class_name"
  done | sort | uniq
}

java -jar jacococli.jar report jacoco_*.exec \
    --classfiles BOOT-INF/classes \
    --sourcefiles ./java \
    --include "$includes" \
    --html . \
    || {
    echo "ERROR: Failed to generate Jacoco report"
    exit 1
}

echo "==== Operation Completed Successfully ===="
