# 前端接入与适配指南

更新日期：2026-10-16。对应仓库 v1.4-dev 后端、遥测 schema 1.1，仍为未定型版本。三端代码已完成本地模拟测试，尚未同步开发板和线上服务器；以下地址在部署并恢复组网后使用。当前 `test/` 模拟前端未修改，不代表它已经适配这些字段。

前端只需连接核心网关。核心负责汇总边缘、服务器和本机接收统计，前端负责选择场景、单位换算、绘图和过期提示。侧栏不需要连接边缘串口、SSH 或服务器诊断端口，也不需要展示虚拟地址、隧道软件和底层承载细节。

## 1. 本次必须适配什么

1. 接入核心 `10017` 完整状态快照，按 `gateway_id` 切换 GW1、GW2、GW4。
2. 主侧栏改为读取 `gateways[].sidebar`，渲染通信方式及三类业务切片；旧的 `gateways[].slices` 和 `edge_transport` 仅保留兼容，不作为新主界面的数据源。
3. 接入核心提供的吞吐/RTT 历史和状态变化事件。
4. 区分零值、未知、过期、待命和未部署；接入进程重启与断线恢复处理。
5. 保持原视频、图片、传感 JSON、短波控制和卫星下行业务的独立接口。状态接口不携带媒体或替代原业务数据。

## 2. 接口清单

下表地址均以核心 `192.168.0.233` 为主机；建议前端将主机地址和端口做成部署配置。

### 2.1 侧栏主入口（本次重点）

| 方法 / 地址 | 数据与接入方式 |
|---|---|
| GET `http://192.168.0.233:10017/latest.json` | 所有场景的完整 JSON 状态。首次加载、重连后同步；也可每秒轮询。200 解析 JSON，204 不解析响应体并保留“等待数据/已过期”状态 |
| GET `http://192.168.0.233:10017/events` | SSE，每约 1 秒推送完整快照，事件名为 **json**。使用 `addEventListener('json', ...)`，不能只注册 `onmessage` |

两者数据结构相同。推荐“首次读取 + SSE + 重连再读取”；仅轮询也可。不要为每张切片卡分别建立 SSE 连接，一条连接已包含所有网关。两种方式均应检查数据类型、schema、进程和序号。

### 2.2 现有业务接口（按页面功能继续使用）

| 用途 | 地址 | 前端处理 |
|---|---|---|
| GW1 视频 | `http://192.168.0.233:10000/stream` | MJPEG，可用 `<img>` 显示 |
| GW2 视频 | `http://192.168.0.233:10001/stream` | MJPEG，可用 `<img>` 显示 |
| GW1 快照 | `http://192.168.0.233:10005/latest.jpg` | JPEG；无新鲜图片可能返回 204，不误当作有效图片 |
| GW1 业务 JSON | `http://192.168.0.233:10008/latest.json` 或 `/events` | 原传感/告警业务对象；SSE 事件名为 `json` |
| GW2 业务 JSON | `http://192.168.0.233:10009/latest.json` 或 `/events` | 同上；与侧栏遥测分开消费 |
| 核心短波接收 JSON | `http://192.168.0.233:10010/latest.json` 或 `/events` | 核心宝通接收业务，SSE 事件名为 `json`；保留业务对象中的来源信息 |
| 卫星下行业务 | `http://192.168.0.233:10014/latest.json`、`/records?after_id=0&limit=200`、`/events` | 最新对象、按记录 ID 查询、SSE；此端口 SSE 为默认 message 事件，用 `onmessage`，与 10017 的命名事件不同 |
| 短波控制状态 | GET `http://192.168.0.233:10016/status` | 保留现有控制面状态；显示侧栏摘要时优先使用 10017 |
| 短波呼叫控制 | POST `http://192.168.0.233:10016/call` | JSON `{"db":"-1"}` 静默、`"0"` 轮询、`"1"` GW1、`"2"` GW2、`"3"` GW4；当前配置仅有这三项站台。202 表示命令受理，不能当作无线链路已建立 |

GW2 当前没有独立快照输出端口；GW4 隧道仅待命预留，没有本次新建的视频/JSON 输出映射。不要把 10011 或其他旧端口直接标成“GW4 隧道”。

其他兼容通道仍由 `core/root/lgd/config.py` 定义：视频 10002/10003/10004 的 `/stream`、快照 10006/10007 的 `/latest.jpg`、JSON 10011/10012 的 `/latest.json` 和 `/events`。本次没有改变它们的来源与用途，不要求为新侧栏新增订阅。

### 2.3 可选诊断入口

| 方法 / 地址 | 用途 |
|---|---|
| GET `http://192.168.0.233:10015/transport` | 原始隧道接收、准入及新增 received 统计；供诊断页使用 |
| GET `http://192.168.0.233:10015/link1`、`/link2`、`/link3` | GW1/GW2/GW4 对应心跳组；组 3 在此工程中对应 GW4 |
| GET `http://192.168.0.233:10015/fps1`、`/fps2`、`/fps3` | 旧监控通道帧率，不等同于三场景逐一映射；新切片卡使用 sidebar 的 video_fps |
| GET `http://192.168.0.233:10014/health` | 核心卫星下行接收与数据库诊断，不代表卫星上行已送达 |
| GET `http://10.77.0.1:11507/telemetry` | 服务器 VPN 内运维诊断。普通前端无需访问，也不需要开放新公网端口 |

## 3. 统一快照如何取数

顶层为 `type="multi_gateway_slice_status"`、`schema_version="1.1"`，包含 `process_id`、递增 `sequence`、`timestamp`、`expires_after_ms=5000` 和 `gateways[]`。

场景标识固定为 `Gateway1`、`Gateway2`、`Gateway4`。不要依赖数组下标或边缘别名 `gateway_1`。例如：

```javascript
const gateway = snapshot.gateways.find(g => g.gateway_id === selectedGatewayId);
const sidebar = gateway?.sidebar;
```

以下字段路径均从该 `sidebar` 起算，完整类型、枚举和统计口径见 [字段字典 v1.1](frontend_telemetry_api_v1.1.md)。

### 3.1 顶部与通信链路区

| 页面项目 | 字段 | 展示说明 |
|---|---|---|
| 边缘数据新鲜度 | `edge_quality` | fresh / stale / unavailable；与前端是否连上核心分开显示 |
| 当前选中通路 | `current_path` | `5g_tunnel` 显示“5G隧道”；null 显示“暂无可用通路” |
| 当前有业务 | `carrying_business` | 最近 3 秒确有业务且获准时 true；选中通路不等于已有流量 |
| 隧道状态 | `links.tunnel.state` | ready 正常、unavailable 不可用、disabled 已禁用、standby 待命 |
| 隧道吞吐 | `links.tunnel.throughput_bps` | 核心实际接收的有效载荷速率，bps；除以 1e6 显示 Mbps |
| 隧道探测时延 | `links.tunnel.probe_rtt_ms` | 应用探测往返毫秒，不是视频端到端时延 |
| 隧道探测成功率 | `links.tunnel.probe_success_pct` | 最近 60 秒探测成功率；没有样本为 null |
| 累计接收 | `links.tunnel.received_bytes / json_received / video_received / snapshot_received` | 分别为有效载荷字节、唯一 JSON 条数、视频帧、快照张数 |
| 最近业务时间 | `links.tunnel.last_business_at` | Unix 秒；没有业务为 null |
| 服务器业务中转备用 | `links.server_relay.state` | 当前 not_deployed，显示“未部署”，速率和时延显示“—” |
| 短波状态 | `links.shortwave` | industrial_pc_connected 表示工控机连接；active_for_gateway 表示呼叫目标；unverified 不能渲染成“无线传输正常” |
| 卫星状态 | `links.satellite` | 模块状态、pending_frames、module_confirmed、failed；ready 表示模块会话就绪，ground_confirmed=null 表示没有地面确认 |

GW4 使用同一结构，隧道业务为 standby。边缘没有遥测上报时其速率、队列等允许为空，不应补成绿色正常或模拟流量。

### 3.2 业务切片卡

三张卡分别绑定 `slices.embb`（视频/图像）、`slices.mmtc`（普通传感）、`slices.urllc`（关键告警/控制）。这里是应用业务分类，不是运营商切片承诺。

| 卡片内容 | 字段 | 单位 / 适配要求 |
|---|---|---|
| 指标质量、选中路径 | `quality`、`selected_path` | 决定新鲜/过期提示及路径名称 |
| 输入 / 发送 / 接收吞吐 | `input_bps`、`send_bps`、`received_bps` | bps；接收值由核心测量，前两项来自边缘，不能直接相减当丢包率 |
| 输入 / 发送 / 接收包速率 | `input_pps`、`send_pps`、`received_pps` | 包/秒 |
| 视频帧率 | `video_fps` | 仅 eMBB，核心实际接收 VID0 帧/秒，不含快照 |
| 内存队列 | `queue_depth`、`queue_capacity` | 条数；可渲染占用条 |
| 丢弃计数 | `dropped_interval`、`dropped_total` | 当前边缘采样周期 / 本边缘进程累计 |
| 本地处理或 ACK 时延 | `processing_ms`、`latency_kind` | queue_and_socket_send 显示“排队及发送耗时”；send_to_core_ack 显示“发送确认耗时” |
| JSON 确认统计 | `delivery.attempts / confirmed / failed / retries / ack_success_pct / ack_mean_ms` | 尝试数、确认数、失败数、重试数、尝试确认率、平均 ACK 毫秒；eMBB 无此确认协议 |
| 持久待确认积压 | `pending`、`oldest_wait_ms` | 仅 URLLC；与内存队列分开展示，零待确认时最老等待为 null |

视频端到端帧龄 `end_to_end_frame_age_ms`、短波吞吐/成功率、卫星地面确认目前没有可靠测量，显示“— / 暂无测量”。不要使用探测 RTT 或本地发送耗时代替它们。

### 3.3 曲线与事件

- `receive_history[]`：最近最多 60 个完整秒，`timestamp` 为 Unix 秒，`received_bps` 为总吞吐，`slices_bps.embb/mmtc/urllc` 为各切片吞吐。可直接绘制总量与分切片曲线。
- `probe_history[]`：`timestamp` 与 `probe_rtt_ms`。null 留断点，不补零。
- `events[]`：按 `id` 去重；显示 `timestamp`、`before`、`after`。三个状态位置依次为隧道状态、边缘状态、卫星模块状态。事件表示观察到变化，不表示已经执行备用切换。

每次推送是完整快照：曲线直接替换或按时间戳合并，事件按 ID 合并，不能每秒重复追加整个列表。历史与事件仅驻留核心内存，核心重启后重新积累。

## 4. 接收与异常处理约定

1. 页面建立一个共享状态连接；首次读取 latest.json，同时监听 SSE 的 `json` 事件。按 process_id 和 sequence 去重，避免 HTTP 与 SSE 重复更新或同进程乱序覆盖。
2. SSE 自动重连后再次读取 latest.json。10017 不支持 Last-Event-ID 历史重放；不要假设会补齐所有断线期间事件。
3. 有效新快照到达时记录浏览器 `performance.now()`。超过 expires_after_ms 没有新快照，侧栏显示“核心连接/数据已过期”；不要继续维持绿色正常。
4. 连着核心仍可能收到过期的边缘数据。使用 edge_quality 及切片 quality；核心观测到的 0 bps 可以是真实零流量，不能与边缘测量缺失混为一谈。
5. 任何数值先用 `value !== null && Number.isFinite(value)` 检查；0 显示 0，null 或缺字段显示“—”。避免 `value || 0`、`Number(null)` 把未知值变成零。
6. process_id 改变时清除序号/事件/曲线会话基准；边缘 edge_process_id 改变时清除边缘累计差值基准。不要跨进程对累计量求差。速率已经由后端计算，前端无需自行推算。
7. Unix 时间单位为秒，浏览器 `new Date(seconds * 1000)`；毫秒时延可除以 1000 显示秒。吞吐 bps 除以 1000/1e6，字节累计量可按选定的 KB/MB 或 KiB/MiB 显示并标清单位。
8. HTTP/SSE 已提供跨源响应头。HTTPS 页面访问 HTTP 内网会受浏览器混合内容限制，应使用同源反向代理；SSE 代理需关闭响应缓冲。该配置属于前端部署，不要求新增后端进程。
9. 页面卸载或连接不再被任何组件使用时调用 EventSource.close()。使用轮询时避免上一请求未结束就叠加新请求。

包含首次读取、重连同步和过期计时的 JavaScript 示例见 [接口文档第 7 节](frontend_telemetry_api_v1.1.md#7-前端接收示例仅文档不修改模拟前端)。

## 5. 前后端工作边界及交付检查

| 负责方 | 工作 |
|---|---|
| 边缘后端 | 探测样本、业务输入/发送速率、内存队列、Outbox、ACK/重试、卫星模组遥测 |
| 服务器后端 | 转发遥测、标记缓存接收时间、提供运维诊断 |
| 核心后端 | 唯一有效载荷接收统计、按网关隔离、数据质量、60 秒历史、状态变化及统一快照 |
| 前端 | 接收/重连、场景选择、字段绑定、单位换算、状态文案、曲线、事件去重、页面断线提示 |

适配完成后至少检查：

- GW1/GW2 场景切换不串数据；GW4 显示待命而不制造隧道业务。
- 空样本、真实零流量、disabled、standby、stale、核心连接中断分别正确展示。
- 核心/边缘重启后累计量与序号不产生负值或卡住更新。
- 曲线与事件不会随完整快照重复堆积，SSE 重连后恢复最新状态。
- 原有媒体、业务 JSON、短波控制和卫星下行页面继续从各自接口接收数据。
- 独立服务器备用未部署、无线统计缺测、卫星模块确认与地面确认的文案符合实际能力。

后端本地验证命令为 `python -m unittest discover -s tests -v`。模拟验证不替代恢复硬件后的无线、实板性能及最终前后端联调验收。
