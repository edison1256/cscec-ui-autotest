#!/bin/bash

# 基础信息定义
APP_DIR="/app"
APP_JAR="$APP_DIR/app.jar"
JACOCO_CLI_JAR="$APP_DIR/jacococli.jar"
JACOCO_EXEC_DIR="$APP_DIR/exec"

# 检查目录是否正确
if [ ! -d "$APP_DIR" ]; then
    echo "Error: $APP_DIR does not exist."
    exit 1
fi

# 检查jacoco jar是否存在
if [ ! -f "$JACOCO_CLI_JAR" ]; then
    echo "$JACOCO_CLI_JAR does not exist."
    exit 1
fi

# 切换到webapps目录
cd "$APP_DIR" || exit 1

# 查找 .jar 文件
JAR_FILES=$(ls *.jar)

# 检查是否找到 .jar 文件
if [ -z "$JAR_FILES" ]; then
    echo "Error: No .jar files found in ${app:-"the specified location"}."
    exit 1
elif [ $(echo "$JAR_FILES" | tr ' ' '\n' | grep -c '.jar$') -ne 3 ]; then
    # 使用grep -c来计算以.jar结尾的行数，更准确地反映文件数量
    echo "Error: There should be 3 .jar files. Please ensure application and jacoco related .jar files exist."
    exit 1
else
    # 仅提取第一个文件的基本文件名
    first_jar=$(echo "$JAR_FILES" | cut -d' ' -f1)
    fn=$(basename "$first_jar")
    name="${fn%%.*}"
fi

# 创建 jacoco 目录
mkdir -p "$JACOCO_EXEC_DIR" || { echo "Error creating directory $JACOCO_EXEC_DIR"; exit 1; }

# Dump jacoco 数据
if ! java -jar "$JACOCO_CLI_JAR" dump --address 127.0.0.1 --port 30090 --destfile "$JACOCO_EXEC_DIR/jacoco.exec"; then
    echo "Error dumping jacoco data."
    exit 1
fi

# 压缩覆盖率数据文件到 exec.tar
if ! (tar czvf exec.tar "$JACOCO_EXEC_DIR"); then
    echo "Error: Failed to create the archive file exec.tar"
    exit 1
fi

echo 'dump success'