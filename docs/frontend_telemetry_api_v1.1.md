# 核心到前端的通信与切片接口 v1.1

状态：2026-10-15 本地后端更新与模拟联调通过；按用户要求暂不连接或部署实板，也未更新模拟前端。本文中的 192.168.0.233 为恢复实板部署后的地址，不代表当前硬件在线。

2026-10-16 整理纳入仓库；前端实施顺序、页面字段映射和完整对接入口见 [前端接入与适配指南](frontend_integration.md)。接口版本仍为 1.1，硬件部署状态未变化。

## 1. 对接入口

| 用途 | 方法 / 地址 | 返回与使用 |
|---|---|---|
| 首次加载、轮询、断线恢复 | GET `http://192.168.0.233:10017/latest.json` | 完整快照。200 为 JSON；启动尚无快照或缓存过期可返回 204，不调用 response.json() |
| 持续更新 | GET `http://192.168.0.233:10017/events` | SSE，每约 1 秒一个完整快照；事件名 **json**，必须 addEventListener('json', ...) |
| 原隧道诊断 | GET `http://192.168.0.233:10015/transport` | 原诊断保留，新增 received 接收统计。主侧栏使用 10017 中的 sidebar 即可 |
| 原心跳 | GET `http://192.168.0.233:10015/link1`、`/link2` | GW1/GW2 心跳与工控机连接 |
| 原短波状态 | GET `http://192.168.0.233:10016/status` | 短波控制状态，仅查询；本次未新增控制命令 |
| 服务器遥测诊断 | GET `http://10.77.0.1:11507/telemetry` | 服务器原控制端口上的新增只读接口；供运维查询，不要求本机前端访问此 VPN 地址 |

HTTP/SSE 保留 `Access-Control-Allow-Origin: *`，前端可跨源读取。浏览器页面若使用 HTTPS，不能直接调用 HTTP 内网接口，应由同源服务反向代理；接口地址由部署环境配置。

原业务接口保持：GW1 视频 10000/stream、快照 10005/latest.jpg、JSON 10008/latest.json 或 /events；GW2 视频 10001/stream、JSON 10009/latest.json 或 /events。GW2 没有新增独立快照前端映射。10017 只传状态，不携带 JPEG。

## 2. 数据层级

返回类型为 `multi_gateway_slice_status`，`schema_version="1.1"`。旧字段保留，新增标准化侧栏数据。

| 字段 | 含义 |
|---|---|
| `sequence` | 核心发布快照序号；同一 process_id 内递增 |
| `timestamp` | 核心生成快照的北京时间 ISO 字符串 |
| `process_id` | 核心汇总实例标识；核心重启会变化 |
| `expires_after_ms` | 5000。前端超过此时间未收到有效完整快照，显示连接/数据过期 |
| `gateways[]` | GW1、GW2、GW4 对象；按 gateway_id 选择，禁止依赖数组顺序 |
| `gateway_id` | Gateway1 / Gateway2 / Gateway4 |
| `gateway` | 边缘实际注册名称，通常 gateway_1 / gateway_2 |
| `scene` | 1 / 2 / 4 |
| `edge` | 边缘采样在线状态、年龄和工业计算机心跳状态 |
| `transport` | 核心隧道接收与准入诊断；含 received |
| `edge_transport` | 原样保留边缘探测信息，可能是旧数据；前端主显示请使用 sidebar 规范化值 |
| `edge_telemetry` | 边缘进程标识、统计起点、采样时间 |
| `sidebar` | 本次新增，供侧栏直接绑定 |

## 3. sidebar 总览

| 字段 | 说明 |
|---|---|
| `sampled_at` | 核心快照生成时间，Unix 秒 |
| `process_id` | 核心汇总实例标识 |
| `edge_process_id` | 对应边缘采集实例标识，边缘业务重启会变化 |
| `edge_sampled_at` | 边缘最近采样时间，Unix 秒；未上报为 null |
| `edge_quality` | fresh / stale / unavailable；在线样本为 fresh，存在但过期为 stale，没有为 unavailable |
| `current_path` | 5g_tunnel 或 null；表示当前探测可达且业务获准的选中路径，不等于当前存在业务流量 |
| `carrying_business` | 最近 3 秒收到业务并且隧道可用、业务获准时 true |
| `links` | 四种通信方式的实际状态 |
| `slices` | embb / mmtc / urllc 的规范化指标 |
| `receive_history` | 核心保存的最近最多 60 个完整秒吞吐采样 |
| `probe_history` | 最近最多 60 个核心汇总时刻的 RTT 值，可为 null；不是额外发起的探测 |
| `events` | 本核心进程观察到的最近状态变化，按网关过滤 |
| `unsupported` | 当前尚未具备测量或功能的项目，不得补假数据 |

## 4. 四种通信方式

### links.tunnel：5G隧道

| 字段 | 单位 / 口径 |
|---|---|
| `state` | ready / unavailable / disabled / standby |
| `reachable` | 核心最近 6 秒内收到匹配证书身份的应用探测 |
| `business_allowed` | 核心准入和新鲜边缘本地准入共同决定；分组禁用时 false |
| `probe_rtt_ms` | 边缘发起到核心返回探测 ACK 的应用 RTT，毫秒；过期/无样本为 null |
| `probe_success_pct` | 最近 60 秒有效探测回复数 / 探测尝试数 ×100；收到有效 ACK 但业务被禁用，仍算探测成功 |
| `probe_attempts` / `probe_successes` | 上述比率分母 / 分子。空样本时成功率为 null |
| `probe_window_ms` | 60000 |
| `last_probe_success_at` | 核心最近收到探测的 Unix 秒；不是收到业务的时间 |
| `throughput_bps` | 核心上一完整秒接纳的唯一业务载荷字节 ×8；已去掉重复 JSON，初始化不足完整采样周期时 null |
| `received_bytes` | 本核心接收实例以来累计唯一业务载荷字节 |
| `json_received` | 唯一 JSON 数 |
| `video_received` | VID0 视频帧数，不含快照 |
| `snapshot_received` | SNAP 快照数 |
| `since` | 上述核心接收累计量的统计起点，Unix 秒 |
| `last_business_at` | 最近实际接收业务的 Unix 秒；没有业务为 null |

接收字节定义：JSON 为去掉 `_transport` 后规范化 UTF-8 JSON 对象字节数，不含换行；媒体为 JPEG 字节数，不含 metadata、帧头、TCP、VPN 开销。边缘发送字节包括它发送的应用封装，与核心有效载荷字节口径不同，不能直接相减为丢包率。

核心监听器正常时，即使没有边缘业务，也可真实观测到 0 bps。边缘遥测过期与核心收到 0 bps 是两件事，分别显示质量和流量。

### links.server_relay：服务器业务中转备用

`state="not_deployed"`，`throughput_bps=null`、`rtt_ms=null`。本次只增加遥测接口，没有实现独立备用业务链路或自动切换。不能显示“备用正常”。

### links.shortwave：短波

| 字段 | 说明 |
|---|---|
| `state` | disconnected 为核心工控机未连接；unverified 为工控机连接但不能据此认定无线业务成功 |
| `industrial_pc_connected` | 核心短波工控机 TCP 会话是否存在 |
| `active_for_gateway` | 当前控制器呼叫目标是否属于此网关 |
| `hf_status` / `detect` | 已有控制器上报的字段；保留其原含义 |
| `throughput_bps` / `success_pct` | null：尚无可靠的按网关无线业务统计 |

### links.satellite：卫星模块

| 字段 | 说明 |
|---|---|
| `state` | starting / ready / unavailable / disabled / unknown |
| `sampled_at` | 边缘读取本地卫星状态时间 |
| `last_error` | 最近实际串口或模组错误；不猜测卫星是否已入网 |
| `attempts` / `failed` | 本边缘进程内的模组发送尝试及明确失败次数 |
| `module_confirmed` | 模组 AT 发送确认次数，不等于地面收到的消息数 |
| `confirmed_bytes` | 获得模组发送确认的业务 JSON 字节 |
| `last_module_confirmed_at` | 最近模组发送确认的 Unix 秒 |
| `pending_frames` / `pending_sampled_at` | 最近一次有效模组查询的待发帧数与查询时间；查询失败/串口不可用为 null |
| `ground_confirmed` | null，当前没有关联卫星上行的地面端确认 |
| `confirmation_scope` | satellite_module_only |
| `reason` | 缺上报、禁用或边缘遥测过期等原因，视状态提供 |

卫星累计量属于边缘进程作用域，使用 `sidebar.edge_process_id` / `edge_telemetry.since` 识别重置。edge_quality 非 fresh 时，卫星展示 unknown 和空值，不继续显示旧的 ready。

## 5. 三类业务切片

读取 `sidebar.slices.embb`、`.mmtc`、`.urllc`，分别对应视频/图像、普通传感、关键告警/控制。这是应用层分类，不代表已获得运营商网络切片保障。

| 字段 | 说明 |
|---|---|
| `quality` | fresh / stale / unavailable |
| `selected_path` | 当前可用且获准的 5g_tunnel，或 null |
| `input_bps` / `send_bps` | 边缘本周期输入/发送应用字节速率，bit/s |
| `input_pps` / `send_pps` | 边缘本周期输入/发送包速率，包/秒；媒体包含视频和快照 |
| `received_bps` / `received_pps` | 核心上一完整秒实际接纳的唯一载荷速率/包速率 |
| `video_fps` | 仅 eMBB：核心上一完整秒 VID0 数量，帧/秒；其他切片为 null |
| `last_received_at` | 对应切片最近实际接收时间 |
| `queue_depth` / `queue_capacity` | 边缘内存队列深度/容量。不能当作可靠消息待确认数 |
| `dropped_interval` | 此次边缘采样周期丢弃的队列条目数 |
| `dropped_total` | 本边缘采集实例累计队列丢弃数 |
| `processing_ms` | 该周期平均耗时；必须结合 latency_kind 解释 |
| `latency_kind` | eMBB 为 queue_and_socket_send（排队到本地发送完成）；JSON 隧道为 send_to_core_ack（该次发送到核心 ACK）；不是端到端采集帧龄 |
| `delivery` | JSON 发送尝试统计；eMBB 无此 ACK 协议，其零尝试与 null 成功率不能显示成视频确认成功 |
| `pending` | 仅 URLLC：持久化 Outbox 未确认记录数；其他切片 null |
| `oldest_wait_ms` | 仅 URLLC：有积压时为当前最老未确认记录的等待毫秒；队列清空后保留最近一条已确认记录的等待毫秒（首次确认前为 null） |
| `current_oldest_wait_ms` | 仅 URLLC：当前最老未确认记录的等待毫秒；无积压时为 null |
| `last_confirmed_wait_ms` | 仅 URLLC：最近一条已确认记录从入队到确认的耗时；尚无确认记录时为 null |
| `end_to_end_frame_age_ms` | null，未具备统一采集时钟与帧采集时间匹配 |

`delivery` 内：

- `attempts`：调用发送的尝试数。
- `confirmed` / `failed`：已完成尝试中收到有效 accepted/duplicate ACK 的数量、失败数量。
- `retries`：同一 delivery_id 的后续尝试次数。以有界最近 8192 个 ID 识别，覆盖默认 5000 条待确认容量。
- `ack_success_pct`：confirmed / (confirmed + failed) ×100，无已完成尝试时 null。应命名“发送尝试确认率”，不是唯一消息最终送达率；重复 ACK 也是成功的一次尝试。
- `ack_mean_ms`：本边缘进程内成功发送尝试的平均 ACK 耗时。
- `ack_ms_total`：成功尝试 ACK 耗时累计值，毫秒。

边缘遥测超过 3 秒开始 stale，超过 5 秒为 offline。规范化 sidebar 会把过期的边缘速率、队列、探测 RTT、确认指标清为空值。原始 `slices`、`edge_transport` 保留排障信息，但不要直接拿它们绕过 quality 渲染绿色正常。

## 6. 曲线与事件

`receive_history[]` 的每项包含：

- `timestamp`：完整统计秒的开始时间。
- `received_bps`：该秒总有效接收 bit/s。
- `slices_bps.embb/mmtc/urllc`：该秒各切片有效接收 bit/s。

这是核心原生统计，不要求前端累积才能看到历史；最多 60 个完整秒，不包含启动时的不足一秒区间。`probe_history[]` 为核心每秒汇总的边缘 RTT；空值应在图上留断点，不能连线或补零。

`events[]` 每项含 `id`、`gateway`、`timestamp`、`type="observed_state_change"`、`before`、`after`。before/after 三个位置依次是隧道准入/可达状态、边缘采样状态、卫星模块状态。核心全局环形缓存最多 96 条，按网关返回；不持久化。事件是实际观察到的状态变化，不代表自动切换已执行。事件 ID 去重，不要每次完整快照重复追加同一事件。

核心汇总 process_id 变化时重建会话序号基准；累计接收量还以 `transport.received.process_id` / `since` 为准。边缘 process_id 变化时重置边缘累计量的展示基准。禁止对跨进程的累计量求差得到负吞吐。

## 7. 前端接收示例（仅文档，不修改模拟前端）

```javascript
const base = 'http://192.168.0.233:10017';
let processId = null;
let sequence = -1;
let lastArrival = 0;

function consume(snapshot) {
  if (snapshot.process_id !== processId) {
    processId = snapshot.process_id;
    sequence = -1;
    // 清理上一核心会话的累计差值基准。
  }
  if (snapshot.sequence <= sequence) return;
  sequence = snapshot.sequence;
  lastArrival = performance.now();
  const gw = snapshot.gateways.find(g => g.gateway_id === 'Gateway2');
  if (!gw) return;
  const data = gw.sidebar;
  // 例如：data.links.tunnel.throughput_bps / 1e6 -> Mbps。
  // 仅对非 null 的有限数值换算；否则显示 —。
  renderSidebar(data); // 替换为你的界面渲染函数。
}

async function loadLatest() {
  const response = await fetch(`${base}/latest.json`, { cache: 'no-store' });
  if (response.status === 204) return; // 暂无有效完整快照。
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  consume(await response.json());
}

const events = new EventSource(`${base}/events`);
events.addEventListener('json', event => consume(JSON.parse(event.data)));
events.onopen = () => loadLatest().catch(console.error);
events.onerror = () => { /* 显示重连中；EventSource 自动尝试重连。 */ };
setInterval(() => {
  if (!lastArrival || performance.now() - lastArrival > 5000) {
    showStaleState(); // 替换为你的过期状态处理，不继续保留绿色正常。
  }
}, 1000);
// 页面退出时 events.close()。
```

SSE 是实时完整快照流，不支持按 Last-Event-ID 重放所有遗漏快照；重连后通过 latest.json 重新同步。后台每秒仍会发布新快照，旧边缘信息会标注 stale/unavailable；只收到 SSE 不等于边缘链路正常。

若采用轮询，每秒请求一次 latest.json 即可；无需再同时轮询多个诊断接口。浏览器本机时钟与板端可能不完全同步，主连接过期判断用本地接收间隔，边缘数据质量用后端 quality；“几秒前”时间显示只作展示。

## 8. 本地验证与部署边界

执行 `python -m unittest discover -s tests -v`。通过的测试包括真实 TCP JSON/媒体接收及去重统计、GW1/GW2 来源隔离、服务器上/下游遥测转发、HTTP/CORS、命名 json SSE、失败探测窗口、过期样本、队列 ACK 清理、模块确认不等于地面确认、重启标识与 60 秒缓存边界。

生成真实本地模拟接口样例：设置环境变量 `LGD_TELEMETRY_EVIDENCE_DIR` 为输出目录后运行测试，输出 `http_snapshot.json`。样例中的数据是本机测试产生的，不是实板遥测，也不能据此验收真实无线链路、相机、短波或卫星。

后续实板部署仍只替换三个主程序：两块边缘 `/root/lgd/gateway_merged.py`、核心 `/root/lgd/gateway_v1.py`、服务器 `/root/lgd/server_v8.py`。保留原配置、证书、白名单、数据库与 systemd 单元。每端先备份，再只重启该端业务服务；服务器先更新以提供缓存时间标记，之后边缘、核心更新。本地更新尚未执行这一步。
