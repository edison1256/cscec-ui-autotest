#!/bin/bash
sleep 20 #等待上一步Artifact上传结束。否则下载文件不完整
today=$(date +%Y%m%d)
if [[ -d ./jacoco ]]; then
    rm -rf ./jacoco
fi
mkdir -p ./jacoco/result && cd ./jacoco || {
    echo "Failed to create directory jacoco"
    exit 1
}
# 下载irp java代码
jar xvf "irp_server_code.zip" || { echo "Failed to download and unzip irp_server_code.zip"; exit 1; }
jar xvf "irp_server_class.zip" || { echo "Failed to download and unzip irp_server_class.zip"; exit 1; }
jar xvf "jacoco_exec.zip" || { echo "Failed to download and unzip jacoco_exec.zip"; exit 1; }
java -jar jacococli.jar merge jacoco_*.exec --destfile merged.exec || { echo "Failed to merge jacoco exec files"; exit 1; }
java -jar jacococli.jar report merged.exec --classfiles BOOT-INF/classes --sourcefiles ./java --html ./result || { echo "Failed to generate jacoco report"; exit 1; }
