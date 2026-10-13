import json,pathlib,subprocess
root=pathlib.Path('/root/lgd_integrated_stage_20261013/validation')
if pathlib.Path('/root/lgd/gateway_v1.py').exists():
 print((root/'results.json').read_text())
 subprocess.run(['systemctl','stop','lgd-integrated-validation.service'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
p=pathlib.Path('/etc/nebula/config.yaml');text=p.read_text()
text='\n'.join(line for line in text.splitlines() if 'port: 11650,' not in line)+'\n';p.write_text(text)
check=subprocess.run(['/usr/local/bin/nebula','-test','-config',str(p)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
assert check.returncode==0,check.stdout
subprocess.check_call(['systemctl','kill','--kill-who=main','--signal=HUP','lgd-nebula'])
print('Temporary validation listener stopped and port authorization removed.')
