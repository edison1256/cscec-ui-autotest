#!/bin/bash
# 拉取一体化Git代码上传java文件
today=$(date +%Y%m%d)
cp -r irp-service/{business-admin,business-core}/src/main/java .
zip -r -x=*.jar "irp_server_code.zip" ./java || { echo "Failed to zip irp_server_code java code files"; exit 1; }
curl -u "20431644:AP9EZniqgqnuSHqmHM3NtUfUgFT" -T "irp_server_code.zip" "https://devops.cscec.com/repo/repository/jspt-generic/jacoco/exec/${today}/${AGILE_PIPELINE_BUILD_ID}/irp_server_code.zip" || { echo "Failed to upload irp-server java code zip to artifactory"; exit 1; }