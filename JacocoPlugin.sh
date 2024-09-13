#!/bin/bash
sleep 20 #等待上一步Artifact上传结束。否则下载文件不完整
today=$(date +%Y%m%d)
# 下载irp java代码
curl -u "20431644:AP9EZniqgqnuSHqmHM3NtUfUgFT" -O "https://devops.cscec.com/repo/repository/jspt-generic/jacoco/exec/${today}/${AGILE_PIPELINE_BUILD_ID}/irp_server_code.zip" && jar xvf "irp_server_code.zip" || { echo "Failed to download and unzip irp_server_code.zip"; exit 1; }
curl -u "20431644:AP9EZniqgqnuSHqmHM3NtUfUgFT" -O "https://devops.cscec.com/repo/repository/jspt-generic/jacoco/exec/${today}/${AGILE_PIPELINE_BUILD_ID}/irp_server_class.zip" && jar xvf "irp_server_class.zip" || { echo "Failed to download and unzip irp_server_class.zip"; exit 1; }
curl -u "20431644:AP9EZniqgqnuSHqmHM3NtUfUgFT" -O "https://devops.cscec.com/repo/repository/jspt-generic/jacoco/exec/${today}/${AGILE_PIPELINE_BUILD_ID}/jacoco_exec.zip" && jar xvf "jacoco_exec.zip" || { echo "Failed to download and unzip jacoco_exec.zip"; exit 1; }
curl -u "20431644:AP9EZniqgqnuSHqmHM3NtUfUgFT" -O "https://devops.cscec.com/repo/repository/jspt-generic/jacoco/jar/jacococli.jar" || { echo "Failed to download jacococli.jar"; exit 1; }
#java -jar jacococli.jar merge jacoco_*.exec --destfile merged.exec || { echo "Failed to merge jacoco exec files"; exit 1; }
java -jar jacococli.jar report jacoco_*.exec --classfiles BOOT-INF/classes --sourcefiles ./java --html . || { echo "Failed to generate jacoco report"; exit 1; }