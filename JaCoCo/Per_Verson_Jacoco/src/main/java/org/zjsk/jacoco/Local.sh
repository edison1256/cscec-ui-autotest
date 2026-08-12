#!/bin/bash
i=1
jacoco_exec="./app/report/jacoco.exec"
cd D:/jacoco || exit 1
mkdir -p ./result
tar zxvf ./app.jar
unzip app.jar || exit 1

# 使用 find 命令获取所有 report.tar 文件的路径，并逐行处理
find . -type f -name "report.tar" | while read -r file_path; do
    # 获取文件所在的目录
    dir=$(dirname "$file_path")

    # 进入文件所在的目录
    cd "$dir" || exit 1

    # 解压 report.tar 文件
    tar -xvf report.tar

    # 处理名称重复的文件
    base_name=$(basename "$jacoco_exec")
    extension="${base_name##*.}"
    file_name="${base_name%.*}"

    mv "$jacoco_exec" "D:/jacoco/${file_name}_${i}.${extension}"
    i=$((i + 1))
    # 删除已解压的 report.tar 文件
    # rm -f report.tar
    # 返回原来的目录
    cd - > /dev/null || exit 1
done

cd D:/jacoco || exit 1
jacoco_exec_files=$(echo `find . -maxdepth 1 -type f -name "jacoco*.exec" -print0 | xargs -0 -I{} basename {} | tr '\n' ' '`)
java -jar jacococli.jar merge $jacoco_exec_files --destfile D:/jacoco/merged.exec || exit 1
java -jar jacococli.jar report D:/jacoco/merged.exec --classfiles /BOOT-INF/classes/com/cscec/ccdt/resource/ --html ./result