import hashlib,json,pathlib,socket,sqlite3,subprocess,time,urllib.request,uuid
role='server' if pathlib.Path('/etc/systemd/system/lgd-server-v8.service').exists() else 'core' if pathlib.Path('/etc/systemd/system/gateway-v1.service').exists() else 'edge'
main={'edge':'gateway_merged.py','core':'gateway_v1.py','server':'server_v8.py'}[role]
business={'edge':'gateway-startup-gw2.service','core':'gateway-v1.service','server':'lgd-server-v8.service'}[role]
units=['lgd-tcp-carrier.service','lgd-nebula.service',business]+([] if role=='server' else ['quectel-cm.service'])
result={'role':role,'device_time':time.time(),'services':{},'addresses':{},'endpoints':{},'main_sha256':hashlib.sha256((pathlib.Path('/root/lgd')/main).read_bytes()).hexdigest()}
for unit in units:
 p=subprocess.run(['systemctl','show',unit,'--property=ActiveState,SubState,MainPID,NRestarts'],stdout=subprocess.PIPE,universal_newlines=True)
 result['services'][unit]=dict(line.split('=',1) for line in p.stdout.splitlines() if '=' in line)
 state=result['services'][unit]
 try:state['ProcessState']=pathlib.Path('/proc/'+state['MainPID']+'/stat').read_text().rsplit(')',1)[1].split()[0]
 except (OSError,KeyError,IndexError):state['ProcessState']='unknown'
for iface in ('usb0','lgdtcp0','nebula1'):
 p=subprocess.run(['ip','-4','-o','addr','show',iface],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 result['addresses'][iface]=[line.split(' inet ',1)[1].split()[0] for line in p.stdout.splitlines() if ' inet ' in line]
paths=({'transport':(10015,'/transport'),'telemetry':(10017,'/latest.json'),'json':(10009,'/latest.json'),'radio':(10016,'/status'),'fps':(10015,'/fps2')} if role=='core' else {'control':(11507,'/transport')} if role=='server' else {})
for name,(port,path) in paths.items():
 try:
  with urllib.request.urlopen('http://127.0.0.1:'+str(port)+path,timeout=2) as response:
   body=response.read(1048577)
   result['endpoints'][name]={'http_status':response.status,'body':json.loads(body.decode()) if body else None,'sequence':response.headers.get('X-Json-Seq')}
 except Exception as exc:result['endpoints'][name]={'error':str(exc)}
if role=='edge':
 nonce=uuid.uuid4().hex;start=time.monotonic()
 try:
  with socket.create_connection(('10.77.0.10',11500),timeout=2) as conn:
   conn.settimeout(2)
   conn.sendall((json.dumps({'type':'transport_probe','gateway':'gateway_2','nonce':nonce})+'\n').encode())
   with conn.makefile('rb') as f:ack=json.loads(f.readline(65536))
  assert ack.get('nonce')==nonce and ack.get('type')=='transport_probe_ack' and ack.get('version')=='1.0'
  result['probe']={'ok':True,'ack':ack,'rtt_ms':round((time.monotonic()-start)*1000,2)}
 except Exception as exc:result['probe']={'ok':False,'error':str(exc)}
 try:
  db=sqlite3.connect('file:/root/lgd/tunnel_outbox.db?mode=ro',uri=True,timeout=1)
  try:result['critical_pending']=db.execute('SELECT count(*) FROM outbox').fetchone()[0]
  finally:db.close()
 except Exception as exc:result['critical_pending_error']=str(exc)
print(json.dumps(result))
