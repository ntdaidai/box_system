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

JAR_PATH="/app/sample/target/sample-1.10.0.jar"

# 只在 jar 不存在时才编译，避免每次启动都重新编译
if [ ! -f "$JAR_PATH" ]; then
  echo "首次启动，编译项目..."
  cd /app
  mvn clean package -Dmaven.test.skip=true -pl sample -am
else
  echo "jar 已存在，跳过编译"
fi

echo "启动应用..."
java -Xmx384m -Xms128m -XX:MaxMetaspaceSize=96m -XX:ReservedCodeCacheSize=48m \
  -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
  -XX:+UseStringDeduplication \
  -jar "$JAR_PATH" \
  --spring.config.location=file:/app/sample/src/main/resources/application.yml
