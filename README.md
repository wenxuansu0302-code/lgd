# LGD integrated v1.4-dev（未定型）

**版本状态：开发验证中，未定型。** 本次更新保存到 GitHub 的 `main` 分支，不作为新的正式发行版。已完成的软件和链路测试不等于完成全部实物验收。

更新日期：2026-10-16。最近一次实板测试接线为 COM5=GW1、COM8=GW2，核心通过 LAN 192.168.0.233 连接本机模拟前端 192.168.0.100；本次更新没有连接或部署硬件。公网服务器 47.99.47.169（SSH 54430）继续使用 V8 基础。

## v1.4 遥测扩展（本地模拟通过，尚未上板）

本次新增侧栏后端遥测：边缘探测窗口、ACK/重试与 Outbox 状态，核心唯一载荷接收字节/速率、60 秒历史、事件和标准化 `sidebar`，服务器缓存接收时间及只读遥测诊断。沿用核心 10017 的 HTTP/SSE 接口，不新增公网端口，不修改 `test/` 模拟前端。

- **前端开发从这里开始：[前端接入与适配指南](docs/frontend_integration.md)**，包含接口清单、页面字段映射、接收流程和验收清单。
- 完整字段、统计口径和浏览器示例：[前端遥测接口 v1.1](docs/frontend_telemetry_api_v1.1.md)。
- 本地回归：`python -m unittest discover -s tests -v`，共 21 项测试通过。

此扩展按用户要求仅在本地模拟验证，没有部署到板卡或线上服务器；本次提交将后端代码和前端对接文档纳入仓库。下文 v1.3 哈希与实板测试是此前已部署版本的历史记录，不能当作此次遥测扩展的实板证据。

## v1.3 更新与验证

- GW1/GW2 共用边缘主程序与隧道机制，各自使用独立证书和地址。GW1 的启动单元覆盖文件位于 `edge/profiles/gw1/etc/systemd/system/`；GW2 继续使用 `edge/etc/systemd/system/`。不得把两个网关的业务 unit 或 `lgd.target` 同时部署到一块板上。
- 核心以 `TUNNEL_SCENES` 区分 active/standby，并校验允许的 JSON/VID0/SNAP 类型。GW4 仅预留地址与 standby 策略，尚未上板、未做本次实物验收。
- GW1/GW2 的隧道通道分别接管 11400/11406 与 11401/11407，停用对应旧拉取线程，避免多来源重复发布。11408 保持 WiFi 旧路径归属。
- 边缘区分探测可达与业务获准；standby 不创建隧道业务积压；故障时 allowed 与 business_allowed 同步变化。
- `now_str()` 显式使用北京时间，修复 GW2 下发校时比北京时间慢 8 小时的问题。最终边缘程序已同步两块实板。
- 服务器增加场景策略状态及 GW1 OpenVPN CCD：`server/etc/lgd-tcp/ccd/lgd-tcp-edge-gw1`。

| 场景 | OpenVPN | Nebula | 状态 |
|---|---|---|---|
| GW1 | 10.78.0.11 | 10.77.0.11 | active，已部署测试 |
| GW2 | 10.78.0.12 | 10.77.0.12 | active，已部署测试 |
| GW4 | 10.78.0.14 | 10.77.0.14 | standby，仅预留 |
| 核心 | 10.78.0.10 | 10.77.0.10 | 接收两路隧道业务 |

此前两路业务均通过核心 10.77.0.10:11500，底层仍经过服务器 11590/TCP。独立的服务器业务转发备用与自动切换尚未实现；侧边栏新增统计已在 v1.4 后端实现并完成本地模拟，尚待部署实板和前端适配。

最新结果见 [三板组网测试报告](docs/network_test_20261015.md) 和 [最终校验摘要](docs/network_test_summary_20261015.json)：两路 JSON 去重、媒体完整性、24 帧并发、本机 HTTP/SSE、白名单、分组控制、进程与承载恢复均通过。边缘业务异常退出约 5.3 秒恢复，承载恢复约 3.8 秒；这些是单次观测，不是性能保证。短波工控机未连接，卫星独立串口未识别，未完成实物短波/卫星与整机冷启动验收。

本地回归可运行 `python -m unittest discover -s tests -v`。测试记录对应的边缘代码 SHA-256 为 `ff44526aaf16f3a0e072fe0e631acd5d91b8b312663f023923db48d1db17ae06`。仓库将 Linux 文本归一为 LF，比较实板原始哈希时须考虑原文件换行差异。

## 模拟前端与构建验证（沿用旧版，本次未更新）

`test/` 仍按原 GW2/核心双串口拓扑工作，不适配当前 GW1/GW2 双串口与核心 LAN 接线。其隔离接收脚本也尚未传入 v1.3 场景策略，不作为本次三板验收工具。以下为原工具说明；本次提交不修改模拟前端代码、样式或脚本。

2026-10-14 新增 [test/](test/) 本地模拟前端，说明见 [test/README.md](test/README.md)。它提供三端真实状态采集、隧道 ACK 探测、独立 JSON/图片验收、离线故障演示和报告导出，继续作为未定型版本的验证工具。

在 Windows 上进入 `test/`，双击 `start.cmd`，然后访问 **http://127.0.0.1:8090**。前端保留 **http://192.168.0.100:8090** 作为 LAN 地址，配置该 IP 后可访问。真实采集使用 COM5（GW2）、COM8（核心）和服务器 SSH；运行缓存、日志和本机测试报告不进入仓库。

## v1.2 架构与历史部署说明

以下端口角色、文件数量和测试记录描述 2026-10-13 的 v1.2 首次归档，当前版本接线和新增配置以文首 v1.3 说明为准。

业务隧道逻辑分别合入三个主程序，不再导入或部署 `tunnel_transport.py`：

| 节点 | 主程序 | 合入的功能 |
|---|---|---|
| edge / COM5 | `root/lgd/gateway_merged.py` | 通路探测、关键 JSON 持久队列与 ACK 重试、发送和接入线程异常恢复、隧道状态诊断 |
| core / COM8 | `root/lgd/gateway_v1.py` | 隧道接收、证书地址与业务身份一致性检查、持久去重、组启停、既有 JSON/图片/视频输出衔接、监听失败后台重试 |
| server | `root/lgd/server_v8.py` | 下游连接替换、断开清理与核心 VPN 来源限制，保留 V8 管理和兼容业务 |

配置仍分别由 `edge_config.py`、`config.py` 和隧道软件配置文件管理。传感器、宝通报文和卫星协议沿用当前实现。

Python 业务由 systemd 直接启动。边缘原有两层业务启动脚本退出运行目录，5G 拨号及本地 usb0 地址/路由恢复由独立的 `quectel-cm.service` 和一个硬件拨号脚本负责。业务异常退出只重启业务，保持拨号和隧道进程运行。核心原启动脚本退出运行目录，网口准备放在业务服务的启动前步骤中。

Nebula、OpenVPN 和拨号服务保留独立故障恢复。每端增加一个统一管理入口 `lgd.target`；依赖设置直接写入已有 service 文件，不再依赖额外的隧道 drop-in 配置。核心和服务器业务启动不再等待 VPN 地址出现，核心隧道接收服务在后台重试，本地功能继续运行。

本目录从三端实时导出并逐文件校验 SHA-256，共 **34 个代码、配置和启动文件**，另附本说明；上一版相同类型文件为 43 个。各角色目录按照对应 Linux 绝对路径展开。未打包私钥、运行数据库、日志、测试脚本和软件二进制。开发及测试过程保存在本机 `tunnel_refactor_20261013`。

## 文件夹结构与文件作用

GitHub 仓库根目录直接包含 `edge/`、`core/`、`server/` 和本 README；本地归档在 `release_v1.2_integrated/` 内采用相同结构。三个角色分别对应三台设备，**只将角色目录内的文件映射到对应设备**。例如 `edge/root/lgd/gateway_merged.py` 对应边缘板的 `/root/lgd/gateway_merged.py`，`core/etc/nebula/config.yaml` 对应核心板的 `/etc/nebula/config.yaml`。

GitHub 根目录另有 `.gitattributes`（统一 Linux 文本换行）和 `.gitignore`（排除私钥、数据库、日志和 Python 缓存）；这两个仓库维护文件无需部署到设备。

```text
.
├── README.md
├── edge/                              # COM5，当前为 gateway_2
│   ├── root/
│   │   ├── start_lgd_5g.sh
│   │   └── lgd/
│   │       ├── gateway_merged.py
│   │       ├── edge_config.py
│   │       └── whitelist.json
│   └── etc/
│       ├── lgd-tcp/
│       │   ├── config.conf
│       │   └── restrict-underlay.sh
│       ├── nebula/config.yaml
│       └── systemd/system/
│           ├── lgd.target
│           ├── gateway-startup-gw2.service
│           ├── quectel-cm.service
│           ├── lgd-tcp-carrier.service
│           └── lgd-nebula.service
├── core/                              # COM8，核心网关
│   ├── root/lgd/
│   │   ├── gateway_v1.py
│   │   └── config.py
│   └── etc/
│       ├── lgd-tcp/
│       │   ├── config.conf
│       │   └── restrict-underlay.sh
│       ├── nebula/config.yaml
│       └── systemd/system/
│           ├── lgd.target
│           ├── gateway-v1.service
│           ├── quectel-cm.service
│           ├── lgd-tcp-carrier.service
│           └── lgd-nebula.service
└── server/                            # 公网服务器，V8 基础
    ├── root/lgd/
    │   ├── server_v8.py
    │   ├── whitelist.json
    │   └── tunnel_group_policy.json
    └── etc/
        ├── lgd-tcp/
        │   ├── config.conf
        │   ├── restrict-underlay.sh
        │   └── ccd/
        │       ├── lgd-tcp-core
        │       └── lgd-tcp-edge-gw2
        ├── nebula/config.yaml
        └── systemd/system/
            ├── lgd.target
            ├── lgd-server-v8.service
            ├── lgd-tcp-carrier.service
            └── lgd-nebula.service
```

### edge：边缘网关的 12 个文件

| 文件 | 作用 |
|---|---|
| `root/lgd/gateway_merged.py` | 边缘主程序。7777 接收图片/视频，8888 接收 JSON，9100 对接宝通设备；统一衔接白名单、短波缓存、卫星上行及心跳/遥测。内置通路探测、关键 JSON 持久排队和 ACK 重试、发送线程恢复；隧道业务发往核心 10.77.0.10:11500。 |
| `root/lgd/edge_config.py` | 默认参数：接入口、协议时序、队列大小、卫星串口识别、隧道地址和持久队列路径。命令行参数可覆盖对应默认值。此板的 `gateway_2`、宝通被叫号 `025203` 由业务 service 明确指定。 |
| `root/lgd/whitelist.json` | 允许接入的设备标识本地缓存，由主程序使用并按配置从服务器同步；它不是网关注册文件。 |
| `root/start_lgd_5g.sh` | 独立硬件拨号脚本。启动和监管 quectel-CM，检查 usb0 地址及默认路由，实际本地链路失效时重拨；不负责启动、停止 Python 业务。 |
| `etc/lgd-tcp/config.conf` | OpenVPN 客户端配置，连接公网 47.99.47.169:11590/TCP，形成外层 10.78 承载网。证书和密钥通过设备上的文件路径引用。 |
| `etc/lgd-tcp/restrict-underlay.sh` | 设置外层承载接口的 iptables/ip6tables 规则：允许 IPv4 UDP 与 ICMP，阻断其它入口及接口转发，使业务通过 Nebula 加密网络访问。 |
| `etc/nebula/config.yaml` | Nebula 客户端配置：证书路径、服务器映射、Lighthouse/Relay、虚拟接口、对核心和服务器的访问规则、本机诊断接口。 |
| `etc/systemd/system/lgd.target` | 本端统一启停入口，将拨号、OpenVPN、Nebula 和边缘业务纳入同一管理目标；自身不执行业务代码。 |
| `etc/systemd/system/gateway-startup-gw2.service` | 直接启动边缘主程序并传入 GW2 参数；异常退出由 systemd 重启。虽然保留原 service 名称，已不再执行旧的多层业务启动脚本。 |
| `etc/systemd/system/quectel-cm.service` | 在启动前准备三个 LAN 网口，随后运行独立拨号脚本。与业务分开管理，业务进程崩溃不会触发拨号重启。 |
| `etc/systemd/system/lgd-tcp-carrier.service` | 启动前加载承载网限制规则，随后运行 OpenVPN，进程异常时独立重启。 |
| `etc/systemd/system/lgd-nebula.service` | 校验配置并运行 Nebula，组织外层承载依赖，进程异常时独立重启。 |

### core：核心网关的 10 个文件

| 文件 | 作用 |
|---|---|
| `root/lgd/gateway_v1.py` | 核心主程序。内置边缘隧道接收、身份检查、持久去重及组启停，将 JSON/图片/视频送入原有 Hub 和 100xx 前端接口；保留服务器兼容通道、短波呼叫、卫星数据与状态/遥测服务。VPN 地址未就绪时监听器后台重试，本地服务继续启动。 |
| `root/lgd/config.py` | 核心参数与路由：114xx 上游到 100xx 前端的映射、短波站台和时序、卫星数据库、遥测参数、边缘 VPN 地址与身份映射、持久接收数据库路径。 |
| `etc/lgd-tcp/config.conf` | 核心 OpenVPN 客户端配置，通过公网 11590/TCP 获取固定承载地址 10.78.0.10。 |
| `etc/lgd-tcp/restrict-underlay.sh` | 限制核心外层承载接口，避免直接通过 10.78 网络访问 SSH、HTTP 等业务接口。 |
| `etc/nebula/config.yaml` | 核心 Nebula 配置，通过 nebula1 提供 10.77.0.10，并按证书角色限制边缘业务、服务器管理及诊断访问。 |
| `etc/systemd/system/lgd.target` | 核心统一启停入口，组合拨号、两层隧道和核心业务。 |
| `etc/systemd/system/gateway-v1.service` | 准备核心 LAN 网口后，直接运行 `gateway_v1.py`，指定服务器 VPN 地址；不再调用旧启动脚本或等待隧道地址的脚本。 |
| `etc/systemd/system/quectel-cm.service` | 独立运行核心板的 quectel-CM，并在进程退出时重启；不受核心 Python 业务重启影响。 |
| `etc/systemd/system/lgd-tcp-carrier.service` | 加载限制规则、运行核心 OpenVPN，并独立恢复进程故障。 |
| `etc/systemd/system/lgd-nebula.service` | 校验并运行核心 Nebula，为加密业务提供虚拟网卡与证书认证。 |

### server：服务器的 12 个文件

| 文件 | 作用 |
|---|---|
| `root/lgd/server_v8.py` | V8 基础的服务器主程序。提供兼容数据转发、白名单、设备状态、组控制、卫星可靠转发、心跳和遥测。内置核心下游连接管理：校验 VPN 来源、替换旧连接并清理已断开的消费者。GW2 到核心的新增业务路径无需由此 Python 程序转发。 |
| `root/lgd/whitelist.json` | 服务器白名单数据，由白名单 HTTP 服务提供给边缘同步；区别于边缘的本地缓存。 |
| `root/lgd/tunnel_group_policy.json` | 组启停状态的持久配置，使服务器业务重启后保留管理状态；不是隧道证书或路由配置。 |
| `etc/lgd-tcp/config.conf` | OpenVPN 服务端配置，监听公网 11590/TCP，提供 10.78.0.0/24 承载网并读取 CCD，允许已授权客户端之间通信。 |
| `etc/lgd-tcp/restrict-underlay.sh` | 服务器侧承载接口限制规则，阻断外层网络上的其它业务入口和接口转发。 |
| `etc/lgd-tcp/ccd/lgd-tcp-core` | 与核心客户端证书名称对应的 CCD 文件，固定分配 10.78.0.10。 |
| `etc/lgd-tcp/ccd/lgd-tcp-edge-gw2` | 与 GW2 客户端证书名称对应的 CCD 文件，固定分配 10.78.0.12。CCD 文件名需与证书身份保持一致。 |
| `etc/nebula/config.yaml` | Nebula Lighthouse 与 Relay 配置，帮助节点发现对端、必要时中继加密数据，并定义服务器自身管理服务的证书访问规则。 |
| `etc/systemd/system/lgd.target` | 服务器统一启停入口，组合 OpenVPN、Nebula 和 V8 业务服务。 |
| `etc/systemd/system/lgd-server-v8.service` | 直接启动 V8 主程序，设置边缘心跳超时、核心 VPN 来源地址、自动重启及文件描述符上限。 |
| `etc/systemd/system/lgd-tcp-carrier.service` | 加载承载网限制规则，运行 OpenVPN 服务端；与服务器 Python 业务分开恢复。 |
| `etc/systemd/system/lgd-nebula.service` | 校验并运行服务器 Nebula，管理发现和中继功能；不与 Python 业务进程绑定退出。 |

### 配置、程序与运行状态的边界

业务处理与应用层隧道协议在三个 Python 主程序中；可调参数在两份 Python 配置及各端 `etc/` 中；systemd 文件只负责准备环境、启动与恢复。Nebula/OpenVPN 的加密、证书握手和虚拟网卡仍由现成软件执行，未重新用 Python 实现。

运行时才产生的 `tunnel_outbox.db`、`tunnel_inbox.db`、卫星数据库、日志及设备上的私钥不在本仓库中。更新代码时应保留这些运行数据。三个角色的同名配置不能互换。当前 edge 的实测部署身份是 **GW2**；原 v1.0 的边缘归档为 **GW1**，不能直接用新版 GW2 service 覆盖 GW1 部署。

## 正常运行

推荐先启动服务器，再启动核心和边缘网关。三端已配置自启动；每端手动启动使用同一个命令：

```sh
systemctl start lgd.target
```

查看完整组成及状态：

```sh
systemctl list-dependencies lgd.target
systemctl is-active lgd-tcp-carrier.service lgd-nebula.service
```

再检查所在端的业务服务：

```sh
# edge
systemctl is-active quectel-cm.service gateway-startup-gw2.service
journalctl -u gateway-startup-gw2.service -n 50 --no-pager

# core
systemctl is-active quectel-cm.service gateway-v1.service
journalctl -u gateway-v1.service -n 50 --no-pager

# server
systemctl is-active lgd-server-v8.service
journalctl -u lgd-server-v8.service -n 50 --no-pager
```

`active` 表示进程运行。5G 拨号、隧道握手和业务重连会继续在后台进行；应同时检查地址与核心接收状态：

```sh
ip -br addr show lgdtcp0
ip -br addr show nebula1
# core：listener_state 应为 listening；retrying 时本地服务仍继续运行
curl -s http://127.0.0.1:10015/transport
```

全部停止或重新启动：

```sh
systemctl stop lgd.target
systemctl restart lgd.target
```

停止目标后，成员服务可能仍短暂显示 `deactivating`；等待成员服务停止完成再进行后续维护。整个目标的重启会重启拨号及隧道。仅更新业务代码时，应只重启所在端的业务 service，以保持 5G 和隧道连接。

## 当前传输路径

```text
公网 11590/TCP → OpenVPN 承载网 10.78.0.0/24
承载网内部 UDP → Nebula 加密业务网 10.77.0.0/24
GW2 10.77.0.12 → 核心 10.77.0.10:11500 → 原有 100xx 输出
管理、白名单、心跳等 → 服务器 10.77.0.1
```

服务器承载地址为 10.78.0.1，核心为 10.78.0.10，GW2 为 10.78.0.12。公网继续使用 11590/TCP；没有新增常驻公网端口。11990/UDP 位于既有隧道配置中，当前可用承载为 TCP。诊断中 Nebula 的 `direct` 表示逻辑对端路径，当前物理路径仍是 TCP 服务器中转。

本归档适用于当前三台设备。现有 Nebula/OpenVPN 程序和证书私钥保留在设备上；新设备需安装软件并单独签发证书。其它边缘网关仍走已有兼容入口，此次实测迁移对象为 GW2。

## 实测结果

| 验证 | 结果 |
|---|---|
| 本机与三端运行同一组 20 项测试 | 全部通过；板端使用实际 Python 3.6，服务器使用 Python 3.10 |
| SQLite 读取及 ACK 后删除暂时失败 | 发送循环继续重试，同一关键消息保持原 delivery ID |
| 发送线程异常退出 | 在原进程内恢复，不联动拨号 |
| 强制终止边缘业务进程 | 约 5.73 秒重新打开 7777/8888；拨号、OpenVPN、Nebula PID 全部不变 |
| 核心 Nebula 启动失败且 TUN 地址缺失 | 本地 JSON HTTP 正常响应 204（暂无数据），9100 短波 TCP 接口可连接；恢复后约 0.63 秒重新监听隧道 |
| 64 KiB JSON 重发 | accepted / duplicate ACK 均正常，核心隔离接收实例只发布一次 |
| 198,749 字节 JPEG | 核心接收一次；SHA-256 与发送样本一致 |
| 错误网关身份 | 连接拒绝，未发布 |
| 生产 11500 接收口探测 | 200,000 字节填充探测成功，无业务发布 |
| 重启边缘 OpenVPN | 约 3.54 秒恢复核心探测 |
| 暂停服务器 Python 业务 | 边缘到核心探测继续成功；测试后服务器业务已恢复 |
| 服务器统一目标启停 | 停止时三项成员服务均 inactive；启动后均 active，管理 HTTP 200 |
| 最终归档检查 | 三端目标及成员服务已启用自启动并处于 active，导出文件逐个校验 SHA-256 |

上述时间是本次单次观测。跨端 JSON/图片验证使用部署后主程序中的真实类和隔离接收实例，未向生产告警、执行器或传感器缓存注入测试业务。临时 11650 监听及 Nebula 放行规则已撤销。

此次验证覆盖软件故障恢复、实际 VPN 链路、消息去重和图片完整性。尚未进行断电冷启动、摄像头持续负载、实物卫星发送和实物短波端到端传输；GW2 卫星端口仍采用既有 `auto` 识别，未将 5G AT 串口当作卫星串口。

## 备份

GitHub 更新前，`main` 指向提交 `251f376f5d53454a91e3b111954701ed614e333d`（`Initial release v1.0`）。现有注释标签 **`v1.0`** 已准确指向这一提交，是更新前版本的独立快照；本次更新不移动此标签。旧版仍可从 `v1.0` 检出，`main` 则保存本次未定型开发版本。

检查时 GitHub Releases 列表为空：旧版备份形式为 **Git 标签**，尚无单独的 GitHub Release 发行条目。本次不为未定型版本创建正式发行条目。更新前另保存了包含 `main` 与 `v1.0` 完整历史的本地 Git bundle：`backups/github_lgd_main_before_v1_2_dev_20261013.bundle`。

```sh
# 在另一个工作目录查看正式基线，避免覆盖当前开发工作
git clone --branch v1.0 https://github.com/wenxuansu0302-code/lgd.git lgd_v1_0
```

三端部署前均保留完整代码和启动文件备份：

```text
/root/lgd_backup_v1_1_before_integrated_20261013_230830
```

本机保留 `release_v1.0`、`release_v1.1_tunnel`。本次完整测试记录、发布 SHA-256 清单和部署证据位于 `tunnel_refactor_20261013/evidence` 及 `tunnel_refactor_20261013/release_manifest.json`。
