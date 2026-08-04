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

PC 端使用 WebRTC，小程序使用 `live-player` 播放后端发布的 RTMP 实时流。实时流异常时，小程序直接切换同一摄像头的快照接口，不再签发未使用的 MJPEG 兼容票据。

## 服务通知

风险提醒使用微信小程序一次性订阅消息。小程序端通过 `uni.requestSubscribeMessage` 拉起授权，用户允许后调用后端记录 openid 和模板授权；后端在安全事件风险等级变化时调用微信 `subscribeMessage.send` 发布服务通知。

当前模板 ID：

```text
5NGdwcxDcjqwTuuCCp-LTbiSEl4Cp8N08wN-0R-WbcA
```

后端需要配置：

```bash
WECHAT_MINIPROGRAM_APP_ID=wx0915df56d799f471
WECHAT_MINIPROGRAM_APP_SECRET=你的微信AppSecret
WECHAT_RISK_TEMPLATE_ID=5NGdwcxDcjqwTuuCCp-LTbiSEl4Cp8N08wN-0R-WbcA
WECHAT_RISK_TEMPLATE_FIELDS=thing1,thing2,thing3,time4
WECHAT_RISK_SUBSCRIPTION_TYPE=once
```

模板字段顺序为：风险级别、风险类型、风险标题、发布时间。如果微信后台模板实际 keyword 不是 `thing1/thing2/thing3/time4`，改 `WECHAT_RISK_TEMPLATE_FIELDS` 即可。

`AppSecret` 放在：

```text
dam-miniprogram/wechat-keys/wechat.env
```

`docker-compose.yml` 已把这个文件作为后端服务的 `env_file`。如果微信后台模板属于长期订阅模板，可以把 `WECHAT_RISK_SUBSCRIPTION_TYPE` 改为 `permanent`；普通一次性模板保持 `once`，用户允许一次只能发送一条服务通知。

## 现场处置增强

- 现场照片在提交前会用 Canvas 写入左下角水印，包含事件、点位、安装地址和时间。
- 首页、详情和摄像头列表使用小程序本地缓存做浅兜底；网络失败时优先展示最近一次数据。
- 高风险事件支持点位导航。后端摄像头台账增加 `install_address`、`latitude`、`longitude`，小程序地图页会拉取摄像头列表并使用 `openLocation` 打开微信导航。
- 一号点位默认坐标暂设为河海大学西康路校区图书馆：纬度 `32.055156`，经度 `118.75809`。

## 容器化

小程序本体不是常驻 Web 服务，不能像 FastAPI 后端或 Vue 前端那样在容器里运行并对外提供页面。它最终运行在微信客户端里。

可以容器化的是：

- 后端小程序适配 API：已经随 `dam-backend` 一起运行。
- 小程序 CI 构建/上传流程：后续可用 `miniprogram-ci` 做一个构建上传容器。
- 静态源码归档：可随仓库或发布包一起保存。

第一版建议不要把它加进 `docker-compose.yml` 作为运行服务，只把 `dam-miniprogram` 作为源码子项目管理。
