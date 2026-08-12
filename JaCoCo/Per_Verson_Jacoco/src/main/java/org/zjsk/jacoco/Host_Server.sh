#!/bin/bash

# 目录
APP_DIR="/app"
APP_JAR="$APP_DIR/app.jar"
APP_EXEC_TAR="$APP_DIR/exec.tar"
APP_SCRIPT="$APP_DIR/jacoco.sh"
JACOCO_CLI_JAR="$APP_DIR/jacococli.jar"
JACOCO_DIR="/data/logs/jacoco"
JACOCO_EXEC_DIR="$JACOCO_DIR/exec"


if [ -f "$JACOCO_DIR/app.jar" ]; then
    rm "$JACOCO_DIR/app.jar"
fi

# 获取docker containerid
# 获取docker ps的输出
output=$(docker ps --format '{{.ID}} {{.Image}} {{.Names}}' | grep irp-business | grep -v harbor)

# 获取行数
line_count=$(echo "$output" | wc -l)

# 判断返回的行数
if [ $line_count -eq 0 ] || [ $line_count -gt 2 ]; then
    echo "Error: No containers found or more than two containers listed."
    exit 0
elif [ $line_count -eq 1 ]; then
    # 只有一行数据，提取第一列和第二列内容
    container_id=$(echo "$output" | awk '{print $1}')
    container_name=$(echo "$output" | awk '{print $2}')
    if [ ! -z "$container_id" ] && [ ! -z "$container_name" ]; then
        if [ $? -ne 0 ]; then echo "docker run Jacoco.sh in container $container_core_id failed, exiting..."; exit 1; fi
        docker exec "$container_id" chmod 777 "$APP_SCRIPT" || exit 1
        docker exec "$container_id" sh "$APP_SCRIPT"
        if [ $? -ne 0 ]; then echo "docker run Jacoco.sh in $container_name $container_id failed, exiting..."; exit 1; fi
        docker exec "$container_id" mkdir -p "$JACOCO_EXEC_DIR"/"$container_id" || exit 1
        docker exec "$container_id" cp "$APP_EXEC_TAR" "$JACOCO_EXEC_DIR"/"$container_id"/exec.tar || exit 1
        docker exec "$container_id" chmod -R 777 "$JACOCO_DIR" || exit 1
        docker cp "$container_id":"$JACOCO_DIR" "$APP_DIR"
        docker cp "$container_id":"$APP_JAR" "$APP_DIR"
        echo "container_id: $container_id"
        echo "container_name: $container_name"
    else
        echo "Error: No container name matched found."
        exit 1
    fi
elif [ $line_count -eq 2 ]; then
    # 有两行数据，提取相应列的内容
    container_admin_id=$(echo "$output" | awk '$2 ~ /irp-business-admin/ {print $1}')
    container_core_id=$(echo "$output" | awk '$2 ~ /irp-business-core/ {print $1}')
    # 检查是否找到匹配的容器
    if [ -z "$container_admin_id" ] && [ -z "$container_core_id" ]; then
        echo "Error: No matching containers found."
        exit 1
    fi
    docker exec "$container_admin_id" chmod 777 "$APP_SCRIPT" || exit 1
    docker exec "$container_admin_id" sh "$APP_SCRIPT"
    if [ $? -ne 0 ]; then echo "docker run Jacoco.sh in admin container $container_admin_id failed, exiting..."; exit 1; fi
    docker exec "$container_core_id" chmod 777 "$APP_SCRIPT" || exit 1
    docker exec "$container_core_id" sh "$APP_SCRIPT"
    if [ $? -ne 0 ]; then echo "docker run Jacoco.sh in core container $container_core_id failed, exiting..."; exit 1; fi
    docker exec "$container_core_id" mkdir -p "$JACOCO_EXEC_DIR"/"$container_core_id" || exit 1
    docker exec "$container_admin_id" mkdir -p "$JACOCO_EXEC_DIR"/"$container_admin_id" || exit 1
    docker exec "$container_admin_id" cp "$APP_EXEC_TAR" "$JACOCO_EXEC_DIR"/"$container_admin_id"/exec.tar || exit 1
    docker exec "$container_core_id" cp "$APP_EXEC_TAR" "$JACOCO_EXEC_DIR"/"$container_core_id"/exec.tar || exit 1
    docker exec "$container_admin_id" chmod 777 -R "$JACOCO_DIR" || exit 1
    docker exec "$container_core_id" chmod 777 -R "$JACOCO_DIR" || exit 1
    docker cp "$container_admin_id":"$JACOCO_DIR" "$APP_DIR"
    docker cp "$container_admin_id":"$APP_JAR" "$APP_DIR"
    # 输出结果（可选，调试用）
    echo "container_admin_id: $container_admin_id"
    echo "container_core_id: $container_core_id"
fi