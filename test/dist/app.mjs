import {viewModel,simulation} from './model.mjs';
const $=id=>document.getElementById(id), esc=value=>String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let mode='live',scenario='normal',tick=0,live={nodes:{},events:[],history:[],validation:{}},shown=live,polling=false;
const labels={edge:'边缘 GW2',core:'核心网关',server:'公网服务器'},serviceLabels={'lgd-tcp-carrier.service':'TCP 承载','lgd-nebula.service':'Nebula','gateway-startup-gw2.service':'边缘业务','gateway-v1.service':'核心业务','lgd-server-v8.service':'V8 业务','quectel-cm.service':'5G 拨号'};
function toast(text){$('toast').textContent=text;$('toast').style.display='block';setTimeout(()=>$('toast').style.display='none',3800);}
function badge(id,tone,text){$(id).className='badge '+tone;$(id).textContent=text;}
function number(value){return value==null?'—':Number(value).toLocaleString('zh-CN',{maximumFractionDigits:1});}
function graph(id,history,key,color){
 const values=history.map(p=>p[key]),valid=values.filter(v=>v!=null&&Number.isFinite(v));let markup='';
 for(let i=0;i<4;i++)markup+=`<line x1="0" x2="380" y1="${8+i*29}" y2="${8+i*29}" stroke="#edf2f5"/>`;
 if(!valid.length){$(id).innerHTML=markup+'<text x="190" y="62" text-anchor="middle" class="chart-empty">等待有效样本</text>';return;}
 const max=Math.max(1,...valid)*1.12,min=0,denominator=Math.max(1,values.length-1);let groups=[],current=[];
 values.forEach((v,i)=>{if(v==null){if(current.length)groups.push(current);current=[];}else current.push(`${(i/denominator*380).toFixed(1)},${(94-(v-min)/(max-min)*80).toFixed(1)}`);});if(current.length)groups.push(current);
 groups.forEach(group=>{markup+=`<polyline points="${group.join(' ')}" stroke="${color}" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;if(group.length===1){const [cx,cy]=group[0].split(',');markup+=`<circle cx="${cx}" cy="${cy}" r="3" fill="${color}"/>`;}});
 markup+=`<text x="1" y="108" fill="#a5b3bf" font-size="8">较早</text><text x="379" y="108" text-anchor="end" fill="#a5b3bf" font-size="8">现在</text><text x="379" y="11" text-anchor="end" fill="#90a3b1" font-size="8">${max.toFixed(0)}</text>`;$(id).innerHTML=markup;
}
function render(){
 shown=mode==='demo'?simulation(scenario,tick):live;const vm=viewModel(shown);
 $('clock').textContent=new Date().toLocaleString('zh-CN',{hour12:false});
 $('pathStatus').textContent=vm.status;$('pathStatus').className='metric-value small '+vm.tone;$('pathHint').textContent=vm.hint;
 $('rtt').textContent=number(vm.probe?.ok?vm.probe.rtt_ms:null);$('pending').textContent=number(vm.edge?.critical_pending);
 $('businessStatus').textContent=mode==='demo'?'不计入实测':vm.validation.running?'验收进行中':vm.businessOK?'隔离验收通过':vm.validation.results?.passed===false?'验收未通过':'待运行';
 $('businessStatus').className='metric-value small '+(vm.businessOK?'good':vm.validation.results?.passed===false?'bad':'');
 $('businessHint').textContent=vm.validation.results?.completed_at?'最近验收 '+new Date(vm.validation.results.completed_at*1000).toLocaleTimeString('zh-CN'):'JSON 去重 / 图片完整性';
 $('sourceText').textContent=mode==='demo'?'仅演示工作机制，不操作三端':'COM5 边缘 · COM8 核心 · SSH 服务器';
 $('liveMode').classList.toggle('selected',mode==='live');$('demoMode').classList.toggle('selected',mode==='demo');$('demoBanner').classList.toggle('hidden',mode!=='demo');
 const ages=Object.values(shown.nodes||{}).map(n=>Date.now()/1000-n.observed_at);
 $('freshness').textContent=mode==='demo'?'模拟样本':vm.validation.running?'验收中 · 定期采样暂停':ages.length?`最旧观测 ${Math.max(...ages).toFixed(0)} 秒前`:'等待首次采样';
 badge('routeBadge',vm.pathOK?'good':'neutral',!vm.pathOK?'业务通路未就绪':vm.peer.overlay_mode==='direct'?'逻辑 direct / 物理 TCP 中转':vm.peer.overlay_mode==='relay'?'Nebula relay':'路径待观测');
 $('overlayLine').style.stroke=vm.pathOK&&vm.enabled?'#20a98b':'#c9d5df';$('carrierLine').style.stroke=vm.addressesOK?'#adccda':'#dbc4c4';
 document.querySelectorAll('.flow-dot').forEach(dot=>dot.style.display=vm.pathOK&&vm.enabled?'':'none');
 $('serviceCards').innerHTML=['edge','server','core'].map(role=>{
  const node=vm[role];const rows=Object.entries(node?.services||{}).map(([name,s])=>{const paused=['T','t','Z','unknown'].includes(s.ProcessState),ok=s.ActiveState==='active'&&!paused;return `<div class="service-row"><span>${esc(serviceLabels[name]||name)}</span><b class="${ok?'good':'bad'}" title="PID ${esc(s.MainPID)} · 重启 ${esc(s.NRestarts)}">${ok?'运行':paused?'暂停/异常':'未运行'}</b></div>`;}).join('');
  const good=node&&Object.values(node.services||{}).length&&Object.values(node.services).every(s=>s.ActiveState==='active'&&!['T','t','Z','unknown'].includes(s.ProcessState));badge(role+'NodeBadge',node?good?'good':'warn':'neutral',node?good?'进程就绪':'检查服务':'采样不可用');
  return `<div class="service-card"><h3>${labels[role]} · ${esc(shown.nodes?.[role]?.source||'待采样')}</h3>${rows||`<p class="service-row">${esc(shown.nodes?.[role]?.error?'采集失败，请查看原始观测':'等待观测')}</p>`}</div>`;
 }).join('');
 const symbols={pass:'✓',fail:'×',warn:'!',pending:'·',manual:'↗',blocked:'Ⅱ'},names={pass:'通过',fail:'未通过',warn:'陈旧',pending:'待验证',manual:'待实测',blocked:'组停用'};
 $('checkList').innerHTML=vm.checks.map(c=>`<div class="check-row"><span class="check-icon ${c.result}">${symbols[c.result]}</span><div class="check-copy"><strong>${esc(c.label)}</strong><p>${esc(c.detail)}</p></div><span class="check-state">${names[c.result]}</span></div>`).join('');
 const passed=vm.checks.filter(c=>c.result==='pass').length;badge('checkCount',passed>=4?'good':'neutral',`${passed} / 6 项通过${mode==='demo'?'（模拟）':''}`);
 $('validateBtn').disabled=mode==='demo'||vm.validation.running||!vm.edge||!vm.core;$('validateBtn').textContent=vm.validation.running?'◌ '+(vm.validation.step||'正在验收'):mode==='demo'?'离线模式不执行真实验收':'▶ 运行隔离数据验收';
 $('validationStep').textContent=vm.validation.running?vm.validation.step:vm.validation.results?.error?'验收未通过。请查看原始观测中的错误证据后重试。':'使用真实传输类与独立接收器，不写入生产业务缓存。';
 $('refreshBtn').disabled=mode==='demo';
 $('jsonCount').textContent=number(vm.peer.json_received);$('mediaCount').textContent=number(vm.peer.media_received);$('duplicateCount').textContent=number(vm.peer.duplicates);$('fps').textContent=number(vm.core?.endpoints?.fps?.body?.fps);
 $('telemetryAlert').textContent=vm.core&&!vm.telemetryFresh?'注意：GW2 管理遥测尚未更新或已陈旧。通路探测成功不代表遥测链路正常。':'生产计数与独立验收分开统计；无摄像头或传感器输入时，生产计数可为零。';
 $('telemetryAlert').classList.toggle('warn',!!(vm.core&&!vm.telemetryFresh));
 $('sampleCount').textContent=(shown.history?.length||0)+' 个样本';graph('rttChart',shown.history||[],'rtt_ms','#29a78d');graph('queueChart',shown.history||[],'pending','#7b9dc1');
 const test=vm.validation.results;badge('imageBadge',vm.businessOK?'good':test?.passed===false?'bad':'neutral',vm.businessOK?'哈希一致':'待验收');
 $('validationImage').classList.toggle('hidden',!vm.businessOK);$('imagePlaceholder').classList.toggle('hidden',vm.businessOK);
 $('imageBytes').textContent=number(test?.image_bytes);$('imagePublications').textContent=number(test?.receiver?.video_publications);$('identityResult').textContent=test?.wrong_identity_rejected?'已拒绝':'待验证';$('imageHash').textContent=test?.image_sha256||'尚无此次验收证据';
 $('eventList').innerHTML=(shown.events||[]).slice(0,14).map(e=>`<div class="event ${e.kind}"><time>${new Date(e.time*1000).toLocaleTimeString('zh-CN',{hour12:false})}</time><span class="event-dot"></span><span>${esc(e.message)}</span></div>`).join('')||'<div class="event">等待实际采样事件</div>';
 if(!$('rawJson').classList.contains('hidden')){const raw={...shown};delete raw.token;$('rawJson').textContent=JSON.stringify(raw,null,2);}
}
async function poll(){if(polling)return;polling=true;try{const response=await fetch('/api/state',{cache:'no-store',signal:AbortSignal.timeout(4500)});if(!response.ok)throw new Error('HTTP '+response.status);live=await response.json();}catch(error){live.nodes={};live.events=[{time:Date.now()/1000,message:'本地采集服务不可用：'+error.message,kind:'warn'}];}finally{polling=false;render();}}
async function action(path){const response=await fetch(path,{method:'POST',headers:{'X-LGD-Token':live.token||''},signal:AbortSignal.timeout(4000)});const body=await response.json();if(!response.ok)throw new Error(body.error||'操作失败');return body;}
$('liveMode').onclick=()=>{mode='live';render();poll();};$('demoMode').onclick=()=>{mode='demo';tick=0;render();};
document.querySelectorAll('[data-scenario]').forEach(button=>button.onclick=()=>{scenario=button.dataset.scenario;tick=0;document.querySelectorAll('[data-scenario]').forEach(b=>b.classList.toggle('selected',b===button));render();});
$('refreshBtn').onclick=async()=>{try{await action('/api/refresh');toast('已请求新的三端采样');}catch(e){toast(e.message);}};
$('rawBtn').onclick=()=>{$('rawJson').classList.toggle('hidden');$('rawBtn').textContent=$('rawJson').classList.contains('hidden')?'查看 JSON':'收起 JSON';render();};
$('validateBtn').onclick=()=>{$('confirmDialog').showModal();};$('cancelTest').onclick=()=>$('confirmDialog').close();$('confirmTest').onclick=async()=>{$('confirmDialog').close();try{await action('/api/validate');toast('真实验收已启动，可查看进度');await poll();}catch(e){toast(e.message);}};
$('exportBtn').onclick=async()=>{try{let report;if(mode==='demo')report={mode:'demo',scenario,generated_at:Date.now()/1000,observations:shown,note:'全部为模拟数据，不代表实际构建成功'};else{const response=await fetch('/api/report',{cache:'no-store'});if(!response.ok)throw new Error('导出失败');report=await response.json();}const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`lgd-${mode}-report-${new Date().toISOString().replace(/[:.]/g,'-')}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);toast(mode==='demo'?'已导出演示数据报告':'已导出真实观测与验证证据');}catch(e){toast(e.message);}};
setInterval(()=>{if(mode==='demo')tick++;render();},1000);setInterval(poll,1500);render();poll();
