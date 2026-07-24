#!/bin/bash
set -e

# 配置阿里云 Maven 镜像
mkdir -p /root/.m2
cat > /root/.m2/settings.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd">
  <mirrors>
    <mirror>
      <id>aliyun</id>
      <mirrorOf>central</mirrorOf>
      <name>Aliyun Maven Mirror</name>
      <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
  </mirrors>
</settings>
EOF

echo "编译项目..."
cd /app
mvn clean package -Dmaven.test.skip=true -pl sample -am

echo "启动应用..."
java -Xmx512m -Xms256m -XX:MaxMetaspaceSize=128m -XX:ReservedCodeCacheSize=64m \
  -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
  -jar /app/sample/target/sample-1.10.0.jar \
  --spring.config.location=file:/app/sample/src/main/resources/application.yml
