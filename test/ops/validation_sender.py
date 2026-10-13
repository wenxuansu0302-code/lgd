import base64,json,pathlib,socket,struct,sys,time,uuid
sys.path.insert(0,'/root/lgd')
import gateway_merged as edge
from gateway_merged import PathManager,TunnelJsonSender,Outbox
json_bytes=edge._lgdt_json_bytes
read_line=edge._lgdt_read_line
root=pathlib.Path('/root/lgd_integrated_stage_20261013/validation');root.mkdir(parents=True,exist_ok=True)
path=PathManager('gateway_2','10.77.0.10',11650,interval=0.5);path.start()
for _ in range(30):
 if path.allowed():break
 time.sleep(0.3)
assert path.allowed(),'Validation ingress not reachable'
box=Outbox(str(root/'outbox.db'))
item=box.add({'json_data':json.dumps({'gateway':'gateway_2','validation':'transport-only-'+uuid.uuid4().hex,'padding':'x'*65536}),'slice_id':'urllc'},'gateway_2')
sender=TunnelJsonSender(path,None,box)
sender._send(item['json_data'],item['delivery_id'])
sender._send(item['json_data'],item['delivery_id'])
box.ack(item['delivery_id']);sender.close()
image=base64.b64decode(pathlib.Path('/root/lgd_tunnel_stage_20261013/validation/image.b64').read_text())
metadata=json_bytes({'frame_id':'validation-only'})
body=struct.pack('!I',len(metadata))+metadata+image
edge._TUNNEL_PATH=path
media=edge.MediaCloudConnection('10.77.0.10',11650,'gateway_2',True)
media.send_raw_packet(struct.pack('!4sQ',b'VID0',len(body))+body);media.close()
with socket.create_connection(('10.77.0.10',11650),timeout=5) as conn:
 conn.settimeout(5)
 conn.sendall(json_bytes({'gateway':'gateway_1','_transport':{'version':'1.0','delivery_id':'identity-reject'}})+b'\n')
 assert conn.recv(100)==b'','Wrong gateway identity was accepted'
nonce=uuid.uuid4().hex
with socket.create_connection(('10.77.0.10',11500),timeout=5) as conn:
 conn.settimeout(5);start=time.monotonic()
 conn.sendall(json_bytes({'type':'transport_probe','gateway':'gateway_2','nonce':nonce,'padding':'y'*200000})+b'\n')
 response=read_line(conn);assert response.get('nonce')==nonce and response.get('enabled') is True
 rtt=(time.monotonic()-start)*1000
path.closed.set();path.monitor.closed.set()
print(json.dumps({'json_ack_and_duplicate_ack':'passed','media_bytes':len(image),'wrong_identity':'rejected','production_probe_bytes':200000,'probe_roundtrip_ms':round(rtt,2),'outbox_pending':box.count()}))
