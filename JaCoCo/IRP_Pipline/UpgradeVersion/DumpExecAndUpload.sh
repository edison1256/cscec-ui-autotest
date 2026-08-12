#!/bin/bash
# 各个容器Dump覆盖率文件并上传
# 目录
APP_DIR="/app"
APP_JAR="$APP_DIR/app.jar"
APP_EXEC_TAR="$APP_DIR/exec.tar"
APP_SCRIPT="$APP_DIR/jacoco.sh"
JACOCO_CLI_JAR="$APP_DIR/jacococli.jar"
JACOCO_DIR="/data/logs/jacoco"
JACOCO_EXEC_DIR="$JACOCO_DIR/exec"
today=$(date +%Y%m%d)

# 删除旧的app.jar文件
[ -f "$JACOCO_DIR/app.jar" ] && rm "$JACOCO_DIR/app.jar"

# 获取docker containerid
output=$(docker ps --format '{{.ID}} {{.Image}} {{.Names}}' | grep irp-business | grep -v harbor)
line_count=$(echo "$output" | wc -l)

# 判断返回的行数
if [ $line_count -eq 0 ] || [ $line_count -gt 2 ]; then
    echo "Error: No containers found or more than two containers listed."
    exit 0
fi

# 运行脚本并处理容器的函数
run_script_in_container() {
    local container_id=$1
    local container_name=$2
    docker exec "$container_id" chmod 777 "$APP_SCRIPT" || { echo "Failed to chmod $APP_SCRIPT in container $container_name $container_id"; exit 1; }
    docker exec "$container_id" sh "$APP_SCRIPT" || { echo "Failed to run $APP_SCRIPT in container $container_name $container_id"; exit 1; }
    docker exec "$container_id" mkdir -p "$JACOCO_EXEC_DIR/$container_id" || { echo "Failed to mkdir $JACOCO_EXEC_DIR/$container_id in container $container_name $container_id"; exit 1; }
    docker exec "$container_id" cp "$APP_EXEC_TAR" "$JACOCO_EXEC_DIR/$container_id/exec.tar" || { echo "Failed to cp $APP_EXEC_TAR in container $container_name $container_id"; exit 1; }
    docker exec "$container_id" chmod -R 777 "$JACOCO_DIR" || { echo "Failed to chmod $JACOCO_DIR in container $container_name $container_id"; exit 1; }
    docker cp "$container_id":"$JACOCO_DIR" "$APP_DIR" || { echo "Failed to cp $JACOCO_DIR from container $container_name $container_id "; exit 1; }
    docker cp "$container_id":"$APP_JAR" "$APP_DIR" || { echo "Failed to cp $APP_JAR from container $container_name $container_id "; exit 1; }
    echo "container_name: $container_name and container_id: $container_id"
}

# 处理单个容器的情况
if [ $line_count -eq 1 ]; then    # 只有一行数据，提取第一列和第二列内容
    container_id=$(echo "$output" | awk '{print $1}')
    container_name=$(echo "$output" | awk '{print $2}')
    [ -z "$container_id" ] || [ -z "$container_name" ] && { echo "Error: No container name matched found."; exit 1; }
    run_script_in_container "$container_id" "$container_name"

fi

# 处理两个容器的情况
if [ $line_count -eq 2 ]; then
    container_admin_id=$(echo "$output" | awk '$2 ~ /irp-business-admin/ {print $1}')
    container_core_id=$(echo "$output" | awk '$2 ~ /irp-business-core/ {print $1}')
    [ -z "$container_admin_id" ] && [ -z "$container_core_id" ] && { echo "Error: No matching containers found."; exit 1; }
    run_script_in_container "$container_admin_id" "irp-business-admin"
    run_script_in_container "$container_core_id" "irp-business-core"
fi

# 检查变量是否存在且包含"irp-business-admin"
if [[ -n "$container_name" && "$container_name" == *irp-business-admin* ]] || [[ -n "$container_admin_id" ]]; then
    jacoco="/app/jacoco"
    exec_tar="exec.tar"
    jacoco_exec="./app/exec/jacoco.exec"
    cd "$APP_DIR" || { echo "Failed to change directory to $APP_DIR"; exit 1; }
    find ./jacoco -type f -name "$exec_tar" | while read -r file_path; do
        # 获取文件所在的目录
        dir=$(dirname "$file_path")
        # 判断文件大小（单位为字节）
        # file_size=$(stat -c "%s" "$file_path")
        # 如果文件大小小于 1KB（1024字节），删除文件及其所在目录
        # if [ "$file_size" -lt 1024 ]; then
        #     echo "Deleting $file_path and its directory $dir (size: $file_size bytes)"
        #     rm -rf "$dir"
        #     continue  # 跳过后续操作
        # fi
        # 进入文件所在的目录
        cd "$dir" || { echo "Failed to change directory to $dir"; exit 1; }
        # 解压 exec.tar 文件
        tar -xf $exec_tar || { echo "Failed to extract $exec_tar"; exit 1; }
        # 处理名称重复的文件
        spec_name=$(basename "$dir")
        base_name=$(basename "$jacoco_exec")
        extension="${base_name##*.}"
        file_name="${base_name%.*}"
        mv "$jacoco_exec" "$jacoco/${file_name}_${spec_name}.${extension}" || { echo "Failed to move $jacoco_exec"; exit 1; }
        cd - > /dev/null || { echo "Failed to return to previous directory"; exit 1; }
    done

    # jacococli合并数据文件&生成报告
    cd "$jacoco" || { echo "Failed to change directory to $jacoco"; exit 1; }
    jacoco_exec_files=$(echo `find . -type f -name "jacoco*.exec" -print0 | xargs -0 -I{} basename {} | tr '\n' ' '`)

    # 压缩&上传制品库
    ls -A1 $APP_JAR 2>/dev/null || { echo "Error: No files $APP_JAR found."; exit 1; }
    unzip -o $APP_JAR -d ./ || { echo "Failed to unzip app.jar"; exit 1; }
    zip -r "irp_server_class.zip" ./BOOT-INF/classes
    zip "jacoco_exec.zip" ./jacoco_*.exec || { echo "Failed to zip jacoco exec files"; exit 1; }
    curl -u "20431644:AP9EZniqgqnuSHqmHM3NtUfUgFT" -T "irp_server_class.zip" "https://devops.cscec.com/repo/repository/jspt-generic/jacoco/exec/${today}/${AGILE_PIPELINE_BUILD_ID}/irp_server_class.zip" || { echo "Failed to upload class file to artifactory"; exit 1; }
    curl -u "20431644:AP9EZniqgqnuSHqmHM3NtUfUgFT" -T "jacoco_exec.zip" "https://devops.cscec.com/repo/repository/jspt-generic/jacoco/exec/${today}/${AGILE_PIPELINE_BUILD_ID}/jacoco_exec.zip" || { echo "Failed to upload jacoco exec files to artifactory"; exit 1; }
    echo "上传覆盖率数据文件 ${today} ${AGILE_PIPELINE_BUILD_ID} jacoco_exec 成功"
else
    echo "当前服务器不是部署admin模块的服务器，正常退出"
    exit 0
fi
