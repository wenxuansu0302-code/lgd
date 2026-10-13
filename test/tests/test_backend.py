import importlib.util,json,pathlib,tempfile,threading,time,unittest,urllib.error,urllib.request
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dashboard_test',ROOT/'server.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
class BackendTests(unittest.TestCase):
    def test_probe_failure_and_recovery_emit_observed_events(self):
        app.STATE['events']=[]
        app.STATE['nodes']['edge']={'role':'edge','probe':{'ok':True}}
        failure=json.dumps({'role':'edge','probe':{'ok':False}})
        recovery=json.dumps({'role':'edge','probe':{'ok':True}})
        with patch.object(app,'serial',side_effect=[failure,recovery]):
            app.collect('edge');app.collect('edge')
        messages=[e['message'] for e in app.STATE['events']]
        self.assertTrue(any('探测中断' in s for s in messages))
        self.assertTrue(any('探测恢复' in s for s in messages))
        self.assertIn('probe_recovered_seconds',app.STATE['nodes']['edge'])

    def test_serial_collection_error_replaces_old_success(self):
        app.STATE['nodes']['edge']={'role':'edge','observed_at':time.time(),'probe':{'ok':True}}
        with patch.object(app,'serial',side_effect=RuntimeError('COM5 occupied')):app.collect('edge')
        self.assertIn('COM5 occupied',app.STATE['nodes']['edge']['error'])
        self.assertNotIn('probe',app.STATE['nodes']['edge'])

    def test_validation_failure_always_cleans_both_devices(self):
        calls=[]
        def fake(role,path,*args):
            calls.append((role,path.name))
            if path.name=='validation_sender.py':raise RuntimeError('injected broken connection')
            return 'fixture-only'
        with tempfile.TemporaryDirectory() as temp,patch.object(app,'RUNTIME',pathlib.Path(temp)),patch.object(app,'stage_fixture',return_value='expected-hash'),patch.object(app,'safety_cleanup_script',return_value=pathlib.Path('cleanup.py')),patch.object(app,'serial',side_effect=fake):
            app.STATE['validation']={'running':True}
            app.isolated_validation()
        self.assertIn(('edge','finish_network_validation.py'),calls)
        self.assertIn(('core','finish_network_validation.py'),calls)
        self.assertFalse(app.STATE['validation']['results']['passed'])
        self.assertFalse(app.STATE['validation']['running'])

    def test_data_action_requires_page_token_and_fresh_samples(self):
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_port)
        try:
            with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(urllib.request.Request(url+'/api/validate',method='POST'))
            self.assertEqual(exc.exception.code,403)
            app.STATE['validation']={'running':False};app.STATE['nodes']={}
            request=urllib.request.Request(url+'/api/validate',method='POST',headers={'X-LGD-Token':app.SECRET})
            with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(request)
            self.assertEqual(exc.exception.code,409)
            report=json.load(urllib.request.urlopen(url+'/api/report'))
            self.assertNotIn('token',report['observations'])
        finally:server.shutdown();server.server_close();thread.join(2)
if __name__=='__main__':unittest.main(verbosity=2)
