# 大藤峡安全巡查 uniapp 微信小程序 V1

这是工作人员手机端业务原型，只覆盖事件查看、视频预览、一键喊话、高风险现场处理和闭环提交。

## 启动方式

1. 启动现有后端服务。

```bash
cd /home/jetson/box_system
docker compose up -d
```

2. 修改小程序访问 Jetson 后端的地址。

当前默认指向 Jetson 局域网地址：

```js
const API_BASE_URL = 'http://192.168.31.52:8090'
```

如果你的 Jetson IP 变化了，需要改成新的局域网 IP，例如：

```js
const API_BASE_URL = 'http://新的JetsonIP:8090'
```

配置文件：

```text
src/utils/config.js
```

3. 用 HBuilderX 调试。

打开 HBuilderX，导入目录：

```text
/home/jetson/box_system/dam-miniprogram
```

然后选择：

```text
运行 -> 运行到小程序模拟器 -> 微信开发者工具
```

HBuilderX 会把 uniapp 源码编译到微信小程序临时目录，再拉起微信开发者工具。

4. 用命令行调试。

首次需要安装依赖：

```bash
cd /home/jetson/box_system/dam-miniprogram
npm install
```

开发编译：

```bash
npm run dev:mp-weixin
```

生产编译：

```bash
npm run build:mp-weixin
```

编译结果通常在：

```text
dist/dev/mp-weixin
dist/build/mp-weixin
```

再用微信开发者工具打开对应编译结果目录。

开发阶段可以在微信开发者工具里勾选“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。正式发布时需要换成 HTTPS 域名，并在微信公众平台配置 request/socket/uploadFile 合法域名。

## 技术栈

当前是 uniapp 项目，不是微信原生小程序。

核心文件：

```text
App.vue
src/main.js
src/pages.json
src/manifest.json
src/pages/events/index.vue
src/pages/detail/index.vue
src/pages/process/index.vue
```

## 视频

PC 端仍使用现有 WebRTC，不做改动。

小程序 V1 使用后端适配层返回实时快照预览，并保留短时 MJPEG 票据和 WebRTC 信令信息。后续如果部署小程序可直接播放的 HLS/FLV/RTMP 网关，只需要扩展 `/api/miniprogram/v1/events/{event_id}/video` 的返回即可。

## 容器化

小程序本体不是常驻 Web 服务，不能像 FastAPI 后端或 Vue 前端那样在容器里运行并对外提供页面。它最终运行在微信客户端里。

可以容器化的是：

- 后端小程序适配 API：已经随 `dam-backend` 一起运行。
- 小程序 CI 构建/上传流程：后续可用 `miniprogram-ci` 做一个构建上传容器。
- 静态源码归档：可随仓库或发布包一起保存。

第一版建议不要把它加进 `docker-compose.yml` 作为运行服务，只把 `dam-miniprogram` 作为源码子项目管理。
