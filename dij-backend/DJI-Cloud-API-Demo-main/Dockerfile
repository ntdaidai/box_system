FROM maven:3.8-eclipse-temurin-11

WORKDIR /app

# 配置 Maven 国内镜像源
RUN mkdir -p /root/.m2 && \
    echo '<?xml version="1.0" encoding="UTF-8"?>\
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"\
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd">\
  <mirrors>\
    <mirror>\
      <id>aliyun</id>\
      <mirrorOf>central</mirrorOf>\
      <name>Aliyun Maven Mirror</name>\
      <url>https://maven.aliyun.com/repository/public</url>\
    </mirror>\
  </mirrors>\
</settings>' > /root/.m2/settings.xml

# 复制 pom 文件先下载依赖
COPY pom.xml ./
COPY cloud-sdk/pom.xml ./cloud-sdk/
COPY sample/pom.xml ./sample/

# 下载依赖
RUN mvn dependency:go-offline -B || true

# 复制源码
COPY . .

# 构建项目（使用 -pl sample -am 构建 sample 模块及其依赖）
RUN mvn clean package -Dmaven.test.skip=true -pl sample -am

# 准备配置目录
RUN mkdir -p /app/sample/target/config

ENTRYPOINT ["sh", "-c", "java -jar /app/sample/target/sample-1.10.0.jar --spring.config.location=file:/app/sample/target/config/"]
