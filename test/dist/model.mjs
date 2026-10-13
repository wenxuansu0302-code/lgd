export function viewModel(state, now = Date.now() / 1000) {
  const node = (role) => { const n = state.nodes?.[role]; return n && !n.error && now - n.observed_at < 22 ? n : null; };
  const edge = node('edge'), core = node('core'), server = node('server');
  const transport = core?.endpoints?.transport?.body || {};
  const peer = transport.gateways?.gateway_2 || {};
  const probe = edge?.probe;
  const business={edge:'gateway-startup-gw2.service',core:'gateway-v1.service',server:'lgd-server-v8.service'};
  const servicesOK = [['edge',edge],['core',core],['server',server]].every(([role,n]) => ['lgd-tcp-carrier.service','lgd-nebula.service',business[role],...(role==='server'?[]:['quectel-cm.service'])].every(unit=>n?.services?.[unit]?.ActiveState==='active' && !['T','t','Z','unknown'].includes(n.services[unit].ProcessState)));
  const suffix={edge:'12',core:'10',server:'1'};
  const addressesOK = [['edge',edge],['core',core],['server',server]].every(([role,n])=>n?.addresses?.nebula1?.some(a=>a.split('/')[0]==='10.77.0.'+suffix[role]) && n?.addresses?.lgdtcp0?.some(a=>a.split('/')[0]==='10.78.0.'+suffix[role]));
  const pathOK = !!(probe?.ok && probe.ack?.core_ready && transport.listener_state === 'listening');
  const enabled = probe?.ok ? probe.ack.enabled === true && peer.enabled !== false : null;
  const gw = core?.endpoints?.telemetry?.body?.gateways?.find(g => g.gateway_id === 'Gateway2');
  const telemetryFresh = gw?.edge?.age_ms != null && gw.edge.age_ms < 5000;
  const validation = state.validation || {};
  const tests = validation.results;
  const businessOK = !!(tests?.passed && tests.image_sha256_match && tests.duplicate_ack && !tests.cleanup_errors?.length);
  let status = '等待真实采样', tone = 'neutral', hint = '取得三端最新状态后开始判定';
  if (edge && core) {
    if (!pathOK) { status = '隧道通路不可用'; tone = 'bad'; hint = probe?.error || transport.listener_error || '检查隧道地址与核心监听状态'; }
    else if (!enabled) { status = '通路可达 · GW2 已停用'; tone = 'warn'; hint = '探测成功，业务由组策略阻止'; }
    else if (!servicesOK || !addressesOK) { status = '业务通路已通 · 节点待核对'; tone = 'warn'; hint = '边缘到核心探测通过，三端服务或地址仍需核对'; }
    else { status = '隧道构建成功'; tone = 'good'; hint = businessOK ? '三端就绪，隔离数据验收已通过' : '三端就绪，运行隔离验收验证数据完整性'; }
  }
  const checks = [
    {label:'三端服务与双层地址',result:servicesOK && addressesOK ? 'pass' : [edge, core, server].every(Boolean) ? 'fail' : 'pending',detail:'拨号 / OpenVPN / Nebula / 业务进程，10.78 与 10.77 地址'},
    {label:'边缘 → 核心实际探测',result:pathOK && enabled ? 'pass' : edge && core ? enabled === false && pathOK ? 'blocked' : 'fail' : 'pending',detail:probe?.ok ? `协议 ACK 与随机 nonce 校验通过 · ${probe.rtt_ms} ms` : probe?.error || '从 GW2 VPN 地址访问核心生产接收口'},
    {label:'关键 JSON 重发去重',result:businessOK ? 'pass' : tests?.passed === false ? 'fail' : 'pending',detail:businessOK ? '两次发送，同一 delivery ID；核心只发布一次' : '需运行独立数据验收，接收计数为零不能证明去重'},
    {label:'图片完整性与身份校验',result:businessOK ? 'pass' : tests?.passed === false ? 'fail' : 'pending',detail:businessOK ? `${tests.image_bytes.toLocaleString()} 字节 · SHA-256 一致 · 错误身份被拒绝` : '比较完整图片哈希，并验证错误身份被拒绝'},
    {label:'管理遥测持续更新',result:telemetryFresh ? 'pass' : core && gw ? 'warn' : 'pending',detail:gw?.edge?.age_ms != null ? `最新边缘遥测距接收 ${Math.round(gw.edge.age_ms / 1000)} 秒` : '等待核心 10017 接口的 GW2 遥测'},
    {label:'业务退出与隧道中断恢复',result:'manual',detail:'在维护窗口注入故障；比较前后 PID 和恢复时长。离线场景不计作实测'},
  ];
  return {edge,core,server,transport,peer,probe,servicesOK,addressesOK,pathOK,enabled,telemetryFresh,gw,validation,businessOK,status,tone,hint,checks};
}

export function simulation(scenario='normal', tick=0) {
  const now=Date.now()/1000, lost=scenario==='outage', disabled=scenario==='disabled', pending=scenario==='recovery' ? Math.max(0,48-tick*4) : lost ? 24+tick*2 : 0;
  const services=(business,bad=false)=>Object.fromEntries(['lgd-tcp-carrier.service','lgd-nebula.service',business,...(business==='lgd-server-v8.service'?[]:['quectel-cm.service'])].map((name,i)=>[name,{ActiveState:bad && i===0 ? 'inactive':'active',MainPID:String(2000+i),NRestarts:'0'}]));
  const peer={enabled:!disabled,json_received:lost||disabled?24:24+tick*2,media_received:lost||disabled?144:144+tick*12,duplicates:3,probes:tick+10,overlay_mode:'direct',nebula_peer_mode:'direct',physical_route:'tcp_hub',underlay_carrier:'openvpn_tcp'};
  const nodes={
    edge:{observed_at:now,source:'模拟',services:services('gateway-startup-gw2.service',lost),addresses:{usb0:['10.120.1.12/24'],lgdtcp0:lost?[]:['10.78.0.12/24'],nebula1:['10.77.0.12/24']},probe:lost?{ok:false,error:'模拟：TCP 承载中断'}:{ok:true,ack:{enabled:!disabled,core_ready:true},rtt_ms:Math.round(90+18*Math.sin(tick))},critical_pending:pending},
    core:{observed_at:now,source:'模拟',services:services('gateway-v1.service'),addresses:{lgdtcp0:['10.78.0.10/24'],nebula1:['10.77.0.10/24']},endpoints:{transport:{body:{listener_state:'listening',gateways:{gateway_2:peer}}},telemetry:{body:{gateways:[{gateway_id:'Gateway2',edge:{age_ms:lost?(6+tick)*1000:500,status:lost?'offline':'online'},slices:{embb:{input_bps:1245000,output_bps:lost?0:1220000},mmtc:{input_bps:3200,output_bps:lost?0:3200},urllc:{input_bps:1500,output_bps:lost?0:1500}}}]}},fps:{body:{fps:lost||disabled?0:12}},json:{http_status:200,body:{gateway:'gateway_2',sample:'演示数据'}}}},
    server:{observed_at:now,source:'模拟',services:services('lgd-server-v8.service'),addresses:{lgdtcp0:['10.78.0.1/24'],nebula1:['10.77.0.1/24']}}
  };
  return {nodes,validation:{running:false,results:null},events:[{time:now,message:lost?'模拟承载中断：关键 JSON 等待重试，视频传输暂停':disabled?'模拟组停用：通路仍可达，业务被拒绝':scenario==='recovery'?'模拟恢复：重试原 delivery ID，持久队列逐步排空':'演示通路正常；所有数值均为模拟',kind:lost||disabled?'warn':'good'}],history:Array.from({length:30},(_,i)=>({time:now-(30-i)*6,rtt_ms:lost?null:90+20*Math.sin(i),pending:lost?i:pending,json_received:i*2,media_received:lost?0:i*12}))};
}
