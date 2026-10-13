"""Local LGD dashboard: one collector, read-only status, isolated data validation."""
import argparse,base64,concurrent.futures,contextlib,copy,hashlib,json,os,pathlib,subprocess,threading,time,uuid,zlib
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer

ROOT=pathlib.Path(__file__).resolve().parent
RUNTIME=ROOT/'.runtime';RUNTIME.mkdir(exist_ok=True)
OPS=ROOT/'ops'
PORTS={'edge':'COM5','core':'COM8'}
LOCKS={role:threading.RLock() for role in PORTS}
STATE_LOCK=threading.RLock()
WAKE=threading.Event()
STATE={'nodes':{},'events':[],'history':[],'validation':{'running':False,'results':None},'started_at':time.time()}
COLLECTING=threading.Lock()
SECRET=uuid.uuid4().hex

def event(message,kind='info'):
    with STATE_LOCK:
        STATE['events'].insert(0,{'time':time.time(),'message':message,'kind':kind})
        STATE['events']=STATE['events'][:80]

def serial(role,script,timeout=24):
    output=RUNTIME/(role+'_'+uuid.uuid4().hex+'.b64')
    with LOCKS[role]:
        # Include bounded upload time, not only remote command execution time.
        deadline=timeout+max(12,len(pathlib.Path(script).read_bytes())/3000+15)
        proc=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(OPS/'serial_exec.ps1'),'-Port',PORTS[role],'-Script',str(script),'-Output',str(output),'-TimeoutSeconds',str(timeout)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=deadline)
    try:
        if proc.returncode:raise RuntimeError(proc.stderr.decode('utf8',errors='replace')[-700:])
        envelope=json.loads(zlib.decompress(base64.b64decode(output.read_text())))
        if not envelope['ok']:raise RuntimeError(envelope['stderr'][-1000:])
        return envelope['stdout']
    finally:
        if output.exists():output.unlink()

def collect(role):
    started=time.time()
    try:
        if role=='server':
            source=(OPS/'collect_node.py').read_bytes()
            proc=subprocess.run(['ssh','-p','54430','-o','BatchMode=yes','-o','ConnectTimeout=4','root@47.99.47.169','python3','-'],input=source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=16)
            if proc.returncode:raise RuntimeError(proc.stderr.decode(errors='replace')[-500:])
            result=json.loads(proc.stdout)
        else:result=json.loads(serial(role,OPS/'collect_node.py'))
        assert result['role']==role,'串口所连接设备的角色不符'
        result.update(observed_at=time.time(),source=PORTS.get(role,'SSH'),collection_ms=round((time.time()-started)*1000))
        with STATE_LOCK:
            previous=STATE['nodes'].get(role,{})
            if role=='edge':
                before=previous.get('probe',{}).get('ok');after=result.get('probe',{}).get('ok')
                if after is False:
                    result['probe_unavailable_since']=previous.get('probe_unavailable_since',time.time())
                    if before is True:event('边缘到核心实际探测中断','warn')
                elif after is True and before is False:
                    elapsed=time.time()-previous.get('probe_unavailable_since',time.time())
                    result['probe_recovered_seconds']=round(elapsed,2)
                    event('边缘到核心实际探测恢复，观测中断约 {:.1f} 秒'.format(elapsed),'good')
            for unit,value in result.get('services',{}).items():
                old=previous.get('services',{}).get(unit,{})
                if old.get('MainPID') and value.get('MainPID') and old['MainPID']!=value['MainPID']:
                    event(role+' '+unit+' PID 变化：'+old['MainPID']+' → '+value['MainPID'],'warn')
            STATE['nodes'][role]=result
        if previous.get('error') or not previous:event({'edge':'边缘','core':'核心','server':'服务器'}[role]+'真实状态已接入','good')
    except Exception as exc:
        with STATE_LOCK:
            previous=STATE['nodes'].get(role,{})
            STATE['nodes'][role]={'role':role,'source':PORTS.get(role,'SSH'),'error':str(exc),'observed_at':time.time()}
        if previous.get('error')!=str(exc):event(role+'采集不可用：'+str(exc)[:120],'warn')

def collector():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        while True:
            with STATE_LOCK:paused=STATE['validation']['running']
            if not paused:
                with COLLECTING:
                    tasks=[pool.submit(collect,role) for role in ('edge','core','server')]
                    for task in tasks:task.result()
                    with STATE_LOCK:
                        edge=STATE['nodes'].get('edge',{})
                        core=STATE['nodes'].get('core',{})
                        peer=core.get('endpoints',{}).get('transport',{}).get('body') or {}
                        peer=peer.get('gateways',{}).get('gateway_2',{})
                        point={'time':time.time(),'rtt_ms':edge.get('probe',{}).get('rtt_ms'),'pending':edge.get('critical_pending'),'json_received':peer.get('json_received'),'media_received':peer.get('media_received')}
                        STATE['history'].append(point);STATE['history']=STATE['history'][-90:]
            WAKE.wait(6);WAKE.clear()

def snapshot():
    with STATE_LOCK:data=copy.deepcopy(STATE)
    data.update(server_time=time.time(),preferred_url='http://192.168.0.100:8090',collector='serial',token=SECRET)
    for node in data['nodes'].values():node['age_seconds']=round(time.time()-node['observed_at'],1)
    return data

def stage_fixture():
    fixture=(ROOT/'dist'/'validation.jpg').read_bytes()
    target='/root/lgd_tunnel_stage_20261013/validation'
    digest=hashlib.sha256(fixture).hexdigest()
    check=RUNTIME/'check_fixture.py'
    check.write_text("import base64,hashlib,json,pathlib\np=pathlib.Path("+repr(target+"/image.b64")+")\nprint(json.dumps({'valid':p.exists() and hashlib.sha256(base64.b64decode(p.read_text())).hexdigest()=="+repr(digest)+"}))\n",encoding='utf8')
    if json.loads(serial('edge',check)).get('valid'):return digest
    script=RUNTIME/'stage_fixture.py'
    script.write_text("import base64,pathlib\np=pathlib.Path("+repr(target)+");p.mkdir(parents=True,exist_ok=True)\n(p/'image.b64').write_text("+repr(base64.b64encode(fixture).decode())+")\nprint('Fixture ready')\n",encoding='utf8')
    serial('edge',script,35)
    assert json.loads(serial('edge',check)).get('valid'),'板端测试样本校验失败'
    return digest

def safety_cleanup_script():
    # A device-local timer guarantees removal even if this PC is disconnected.
    code=(OPS/'finish_network_validation.py').read_text(encoding='utf8')
    code=code.replace(" print((root/'results.json').read_text())"," if (root/'results.json').exists():print((root/'results.json').read_text())")
    encoded=base64.b64encode(code.encode()).decode()
    script=RUNTIME/'arm_cleanup.py'
    timer='lgd-ui-validation-cleanup-'+uuid.uuid4().hex[:8]
    script.write_text("import base64,pathlib,subprocess\np=pathlib.Path('/root/lgd_integrated_stage_20261013/ui_validation_cleanup.py');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode("+repr(encoded)+"))\nold=subprocess.check_output(['systemctl','list-units','--all','--plain','--no-legend','lgd-ui-validation-cleanup*'],universal_newlines=True)\nunits=[line.split()[0] for line in old.splitlines() if line.split() and line.split()[0].startswith('lgd-ui-validation-cleanup')]\nif units:subprocess.run(['systemctl','stop']+units,stdout=subprocess.PIPE,stderr=subprocess.PIPE)\nsubprocess.check_call(['systemd-run','--collect','--unit="+timer+"','--on-active=150','/usr/bin/python3',str(p)])\nprint('Cleanup armed')\n",encoding='utf8')
    return script

def isolated_validation():
    success=False;cleanup_errors=[]
    results={}
    try:
        with COLLECTING,LOCKS['edge'],LOCKS['core']:
            def step(text):
                with STATE_LOCK:STATE['validation']['step']=text
                event(text)
            try:
                step('准备独立测试样本与自动清理')
                expected=stage_fixture()
                cleanup=safety_cleanup_script()
                for role in ('core','edge'):serial(role,cleanup)
                # Each run uses fresh isolated hubs/inbox; production stores are untouched.
                reset=RUNTIME/'reset_validation.py'
                reset.write_text("import pathlib,subprocess\nsubprocess.run(['systemctl','stop','lgd-integrated-validation.service'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)\np=pathlib.Path('/root/lgd_integrated_stage_20261013/validation')\nfor name in ('inbox.db','inbox.db-wal','inbox.db-shm','results.json'):\n f=p/name\n if f.exists():f.unlink()\nprint('Isolated fixture reset')\n",encoding='utf8')
                serial('core',reset)
                step('连接独立测试接收器')
                for role in ('core','edge'):serial(role,OPS/'setup_network_validation.py')
                serial('core',OPS/'start_validation_receiver.py')
                step('验证 JSON 重发去重、图片完整性与身份拒绝')
                sent=serial('edge',OPS/'validation_sender.py',35)
                sender=json.loads(sent.strip().splitlines()[-1])
                time.sleep(1.3)
                received=serial('core',OPS/'finish_network_validation.py')
                receiver=json.loads(received.splitlines()[0])
                assert receiver['json_publications']==1,'JSON 重发被重复发布'
                assert receiver['video_publications']==1,'测试图片接收计数不符'
                assert receiver['video_sha256']==expected,'图片 SHA-256 不一致'
                assert sender['wrong_identity']=='rejected','错误网关身份未被拒绝'
                assert receiver['stats']['gateways']['gateway_2']['duplicates']==1
                results={'passed':True,'completed_at':time.time(),'scope':'隔离实例，使用部署主程序的真实传输类','json_publications':1,'duplicate_ack':True,'image_bytes':sender['media_bytes'],'image_sha256':expected,'image_sha256_match':True,'wrong_identity_rejected':True,'production_probe_ms':sender['probe_roundtrip_ms'],'production_probe_bytes':sender['production_probe_bytes'],'sender':sender,'receiver':receiver}
                success=True
            finally:
                step('关闭测试接收器并撤销临时访问规则')
                for role in ('edge','core'):
                    try:serial(role,OPS/'finish_network_validation.py')
                    except Exception as exc:cleanup_errors.append(role+': '+str(exc))
    except Exception as exc:
        results={'passed':False,'completed_at':time.time(),'error':str(exc)}
    results['cleanup_errors']=cleanup_errors
    if cleanup_errors:results['passed']=False
    with STATE_LOCK:
        STATE['validation'].update(running=False,step='验证完成' if success and not cleanup_errors else '验证未通过，请查看证据',results=results)
    (RUNTIME/'last_validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    event('隔离数据链路验收通过' if results.get('passed') else '隔离数据链路验收未通过','good' if results.get('passed') else 'warn')
    WAKE.set()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)
    def log_message(self,fmt,*args):pass
    def json(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode();self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/api/state':return self.json(200,snapshot())
        if path=='/api/report':
            data=snapshot();data.pop('token',None)
            return self.json(200,{'generated_at':time.time(),'mode':'live','observations':data,'note':'状态和隔离数据验收分别判定；此报告不证明实物短波/卫星或断电冷启动通过。'})
        if path.startswith('/api/'):return self.json(404,{'error':'unknown endpoint'})
        return super().do_GET()
    def do_POST(self):
        # Actions are operator-selected, not triggered by remote cross-site requests.
        if self.headers.get('X-LGD-Token')!=SECRET:return self.json(403,{'error':'请从本地演示页面发起操作'})
        if self.path=='/api/refresh':WAKE.set();return self.json(202,{'accepted':True})
        if self.path=='/api/validate':
            with STATE_LOCK:
                if STATE['validation']['running']:return self.json(409,{'error':'验证已在进行'})
                for role in ('edge','core'):
                    node=STATE['nodes'].get(role,{})
                    if node.get('error') or time.time()-node.get('observed_at',0)>20:return self.json(409,{'error':'请先取得两块板的最新真实状态'})
                STATE['validation'].update(running=True,step='正在启动验证',results=None,started_at=time.time())
            threading.Thread(target=isolated_validation,daemon=True).start()
            return self.json(202,{'accepted':True})
        return self.json(404,{'error':'unknown action'})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8090);parser.add_argument('--host',default='0.0.0.0');parser.add_argument('--no-collector',action='store_true')
    args=parser.parse_args()
    # A single instance owns both serial ports. Browser tabs share cached samples.
    lock=(RUNTIME/'server.lock').open('a+b')
    import msvcrt
    lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise SystemExit('演示服务已运行，请打开 http://127.0.0.1:'+str(args.port))
    if not args.no_collector:threading.Thread(target=collector,daemon=True).start()
    event('真实采集启动：COM5 边缘 / COM8 核心 / SSH 服务器')
    (RUNTIME/'server.pid').write_text(str(os.getpid()))
    print('Local: http://127.0.0.1:'+str(args.port),flush=True)
    print('LAN (after 192.168.0.100 is configured): http://192.168.0.100:'+str(args.port),flush=True)
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()

if __name__=='__main__':main()
