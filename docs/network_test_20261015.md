# GW1 / GW2 / 核心网关组网实测报告

测试日期：2026-10-15，Asia/Shanghai。最终校验记录见 `SUMMARY.json`，测试对象不包含 GW4。

## 结论

当前三块板卡的 5G/TCP 承载、Nebula 加密覆盖网络、边缘到核心业务传输、本机 LAN HTTP/SSE 接收、分组控制与故障恢复均通过本报告所列软件实测。不能据此宣称短波、卫星、真实相机、传感器和整机冷启动全部验收。

## 接线与身份

| 设备 | 接入方式 | 业务身份 | OpenVPN 地址 | Nebula 地址 |
|---|---|---|---|---|
| GW1 | COM5 | gateway_1，callee 025202 | 10.78.0.11 | 10.77.0.11 |
| GW2 | COM8 | gateway_2，callee 025203 | 10.78.0.12 | 10.77.0.12 |
| 核心 | 网口 192.168.0.233 | core，11500 接收 | 10.78.0.10 | 10.77.0.10 |
| 本机模拟前端 | 192.168.0.100/24 | HTTP/SSE 客户端 | — | — |
| 公网服务器 | SSH 47.99.47.169:54430 | OpenVPN hub、Nebula 管理及业务管理 | 10.78.0.1 | 10.77.0.1 |

实际 TCP socket 已确认源地址为 192.168.0.100，目标为 192.168.0.233。边缘与核心的物理承载经过公网服务器 11590/TCP；状态中的 Nebula `direct` 不代表公网物理直连。本次由本机测试客户端模拟前端读取 API，没有把原单边缘串口看板当作三板测试证据。

## 测试结果

| 项目 | GW1 | GW2 | 证据与范围 |
|---|---|---|---|
| 5G 拨号与承载 | 通过 | 通过 | usb0 有地址，拨号服务运行；服务器 OpenVPN 客户端登记三块板卡 |
| Nebula 与生产探测 | 通过 | 通过 | 11500 nonce 匹配、active、policy v1、JSON/VID0/SNAP 获准 |
| JSON 可靠发送 | 通过 | 通过 | 64 KiB payload 经部署的 TunnelJsonSender 发送；同 ID 得到 accepted / duplicate |
| 本机读取 JSON | 通过 | 通过 | 10008、10009 `/latest.json` 的唯一标记与网关身份匹配 |
| 视频帧完整性 | 通过 | 通过 | 本机 10000、10001 `/stream`，每帧 198,749 字节，哈希一致 |
| 快照完整性 | 通过 | 按原设计不发布 | GW1 10005 `/latest.jpg` 正确；GW2 11401 SNAP 无独立前端映射，不将此判为故障 |
| 双路并发 | 通过 | 通过 | 每路发送并接收 12 帧，合计 24 帧；逐帧哈希与来源正确；短时模拟数据测试 |
| 正式进程本地输入口 | 通过 | 通过 | 模拟客户端连接边缘 8888 / 7777，经正在运行的业务线程、隧道、核心到本机，JSON/视频正确 |
| 白名单 | 通过 | 通过 | DEV-001 被转发；不在白名单的 LGD-DENIED-* 被阻止；服务器白名单 API 正常 |
| 校时下行 | 修复后通过 | 修复后通过 | 同时返回 13:31:02 北京时间，核对误差分别 0.311 秒、0.235 秒 |
| SSE 实时推送 | 通过 | 通过 | 10008、10009 `/events` 收到新输入的唯一标记、正确身份及 text/event-stream |
| 身份隔离 | 通过 | 通过 | 从自身 VPN 身份冒用另一网关，核心关闭连接 |
| 分组停用 | 通过 | 通过 | 核心 policy_reason=group_disabled；探测仍应答，业务 ACK rejected；另一组保持启用 |
| 分组恢复 | 通过 | 通过 | 恢复为 active/ready，保留原分组状态 |
| 业务进程异常退出恢复 | 5.28 秒 | 5.30 秒 | KILL 后 systemd 拉起；拨号、OpenVPN、Nebula PID 不变；探测恢复 |
| TCP 承载中断恢复 | 3.86 秒 | 3.82 秒 | 停承载后探测不可用且 allowed/business_allowed 均 false；启动后恢复；业务、拨号、Nebula PID 不变 |
| 持久化消息保留与重发 | 通过 | 通过 | 使用独立测试 Outbox：断网时保留 1 条，重新打开数据库仍在，恢复后调用部署的 sender 获 ACK 并清空。未向生产队列注入真实告警 |
| 管理遥测与心跳 | 通过 | 通过 | 核心 10017 两路 age 均小于 1 秒的最终采样；10015/link1、link2 在线 |
| 核心业务重启 | 通过 | 通过 | 仅核心业务 PID 变化；拨号和两层隧道 PID 不变；6.34 秒内重新收到两路探测 |
| 服务器业务暂停独立性 | 通过 | 通过 | 服务器业务进程 STOP 15 秒，期间两路仍收到核心生产探测 ACK；finally CONT，进程从 T 恢复 S |
| 最终部署一致性 | 通过 | 通过 | 两块边缘运行同一最终程序哈希；业务服务 active，最终待确认队列均 0 |

图像 SHA-256：`caecbc2bc9b03cb09d4dae27ca74c734cb2f2565b7b3421ca8bc26143aeed571`。

## 本次变更及同步

1. GW2 原程序尚未包含 v1.3 场景策略，先在 `/root/lgd_backup_gw2_networktest_20261015_131758` 备份，再同步公共边缘主程序并补入 `TUNNEL_BUSINESS_MODE="active"`、`TUNNEL_POLICY_VERSION=1`。保留 GW2 原启动参数、证书、地址和 callee 身份。
2. 实测发现 GW2 校时下行比北京时间慢 8 小时。`gateway_merged.py` 的 `now_str()` 原使用系统本地时区，现改为 `datetime.now(BJ_TZ)`，使业务时间字符串使用北京时间。修复已同步 GW1、GW2；未修改系统时钟和时区。
3. 修复前备份：GW1 `/root/lgd_backup_timezonefix_20261015_133033`；GW2 `/root/lgd_backup_timezonefix_20261015_133032`。
4. 最终边缘主程序 SHA-256：`ff44526aaf16f3a0e072fe0e631acd5d91b8b312663f023923db48d1db17ae06`。本地与两块板卡一致，实际校时及 LAN JSON 已复测。
5. 核心和服务器本次不需要业务代码修改。没有修改防火墙，没有新增公网端口，没有改动 GW4 分组。
6. 边缘编译与场景策略 6 项测试通过；`git diff --check` 通过。仓库变更未提交、未推送。

## 清理及当前状态

- 所有测试分组均恢复原启用状态；边缘、核心和服务器所需服务最终为 active。
- 服务器暂停测试已恢复 CONT；测试 Outbox 数据库已移除，生产数据库保留。
- 核心上上一轮加入的 `codex-temp-network-test-20261015` SSH 公钥已删除，见 `cleanup.json`。
- 用于可观察验收的 JSON/图片带 transport_validation 或唯一测试标记。它们是模拟输入，不代表现场真实传感器或相机数据；核心接口有数据过期控制。
- 本次测试脚本、JSON 证据和部署文件位于本目录；`gw2_synced_files/` 是导出的 GW2 程序、配置和启动文件，不含私钥。

## 未通过实物验收的范围

- 短波：核心短波状态接口正常，但 BaoTong 工控机 connected=false，两路 industrial_pc_connected=false。没有执行真实呼叫、短信或无线发送，不能认定短波链路已通过。
- 卫星：两块边缘仅看到 Quectel 5G 多串口，未识别出独立卫星串口。线程存在卫星端口检测错误；未向 5G 串口猜测发送卫星 AT 命令。
- 相机/传感器：已测试模拟输入经正式业务进程转发；未执行实物设备协议与负载验收。
- 可靠性：未做整机断电冷启动、长时间压力、运营商物理断网/拔卡、服务器整机故障或拨号进程崩溃。上述恢复数据仅对应已记录的软件故障注入。
- 网络拓扑：当前公网 TCP hub 路径已验证；未验证 UDP 物理直连或其他 relay 拓扑。
- GW4 不在本次测试范围。

## 证据索引

仓库保留本报告与 [最终校验摘要](network_test_summary_20261015.json)。原始 JSON、串口输出及 GW2 导出文件保存在本地主机 `C:/Users/PC/Desktop/lgd/network_test_20261015/`，没有上传私钥、运行数据库和原始日志。

本地原始证据中，`SUMMARY.json` 为最终判据；`e2e.json` 为初次可靠发送及前端读取；`concurrent_media.json` 为双路 24 帧；`local_ingress.json` 为正式进程输入与白名单；`sse.json` 为实时推送；`group_policy.json` 为分组控制；`gw1_recovery.json` / `gw2_recovery.json` 为边缘恢复；`service_recovery.json` 为核心与服务器恢复；`gw1_verified.json` / `gw2_verified.json` 为最终边缘状态；`core_final.json` / `server_final.json` 为最终核心和服务器状态。
