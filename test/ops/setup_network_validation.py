import pathlib,subprocess,json
p=pathlib.Path('/etc/nebula/config.yaml');text=p.read_text()
is_core=pathlib.Path('/root/lgd/gateway_v1.py').exists()
rule='    - {port: 11650, proto: tcp, '+('group: edge' if is_core else 'host: lgd-core')+'}\n'
section='  inbound:\n' if is_core else '  outbound:\n'
if rule not in text:text=text.replace(section,section+rule)
p.write_text(text)
check=subprocess.run(['/usr/local/bin/nebula','-test','-config',str(p)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
assert check.returncode==0,check.stdout
subprocess.check_call(['systemctl','kill','--kill-who=main','--signal=HUP','lgd-nebula'])
print(json.dumps({'temporary_diagnostic_port':11650,'only_certificate_authorized_overlay_traffic':True}))
