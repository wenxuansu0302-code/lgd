import base64
import importlib.util
import json
import os
import pathlib
import socket
import sqlite3
import struct
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/validation.jpg'
if not FIXTURE.exists():
    FIXTURE = ROOT / 'test/dist/validation.jpg'


def load(name, folder, filename):
    sys.path.insert(0, str(ROOT / folder))
    sys.modules.pop('config', None)
    spec = importlib.util.spec_from_file_location(name, ROOT / folder / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


edge = load('telemetry_edge', 'edge/root/lgd', 'gateway_merged.py')
core = load('telemetry_core', 'core/root/lgd', 'gateway_v1.py')
server = load('telemetry_server', 'server/root/lgd', 'server_v8.py')


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError('condition did not become true')


class Heartbeat:
    def is_online(self, group):
        return group in (1, 2)

    def snapshot(self, group):
        return {'industrial_pc_connected': False, 'heartbeat_age_ms': 100}


class TelemetryTests(unittest.TestCase):
    def collector(self):
        return edge.SliceMetricsCollector('gateway_1', edge.DroppingQueue(10), edge.DroppingQueue(10))

    def test_probe_window_uses_attempts_and_no_samples_is_null(self):
        path = edge.PathManager('gateway_1', '127.0.0.1', 1)
        self.assertIsNone(path.snapshot()['probe_window']['success_pct'])
        path.record_probe(True, 10)
        path.record_probe(False)
        window = path.snapshot()['probe_window']
        self.assertEqual(window['attempts'], 2)
        self.assertEqual(window['success_pct'], 50)
        with patch.object(edge.time, 'time', return_value=time.time() + 61):
            self.assertIsNone(path.snapshot()['probe_window']['success_pct'])

    def test_periodic_snapshot_does_not_reset_totals(self):
        metric = self.collector()
        metric.record_input('mmtc', 100)
        metric.record_output('mmtc', 125, 4)
        first = metric.snapshot()
        second = metric.snapshot()
        self.assertGreater(first['slices']['mmtc']['output_bps'], 0)
        self.assertEqual(second['slices']['mmtc']['output_bps'], 0)
        self.assertEqual(second['slices']['mmtc']['totals']['out_bytes'], 125)
        self.assertIsNone(second['slices']['urllc']['delivery']['ack_success_pct'])

    def test_persistent_outbox_reports_oldest_wait_and_ack_clear(self):
        with tempfile.TemporaryDirectory() as temp:
            outbox = edge.Outbox(str(pathlib.Path(temp) / 'outbox.db'))
            self.assertIsNone(outbox.snapshot()['oldest_wait_ms'])
            record = outbox.add({'json_data': json.dumps({'gateway': 'gateway_1', 'alarm': True}), 'slice_id': 'urllc'}, 'gateway_1')
            with outbox.connect() as connection:
                connection.execute('UPDATE outbox SET created=?', (time.time() - 2,))
            self.assertGreater(outbox.snapshot()['oldest_wait_ms'], 1900)
            self.assertGreater(outbox.snapshot()['current_oldest_wait_ms'], 1900)
            outbox.ack(record['delivery_id'])
            snapshot = outbox.snapshot()
            self.assertEqual(snapshot['pending'], 0)
            self.assertIsNone(snapshot['current_oldest_wait_ms'])
            self.assertGreater(snapshot['oldest_wait_ms'], 1900)
            self.assertEqual(snapshot['oldest_wait_ms'], snapshot['last_confirmed_wait_ms'])

    def test_outbox_telemetry_failure_does_not_kill_reporting(self):
        with tempfile.TemporaryDirectory() as temp:
            outbox = edge.Outbox(str(pathlib.Path(temp) / 'outbox.db'))
            path = edge.PathManager('gateway_1', '127.0.0.1', 1)
            with patch.object(edge, '_TUNNEL_PATH', path), patch.object(edge, '_TUNNEL_OUTBOX', outbox), patch.object(outbox, 'snapshot', side_effect=sqlite3.OperationalError('busy')):
                result = self.collector().snapshot()
            self.assertIsNone(result['outbox']['pending'])
            self.assertEqual(result['outbox']['quality'], 'unavailable')
            self.assertIsNone(result['transport']['critical_pending'])

    def test_received_throughput_drops_to_zero_without_losing_totals(self):
        metrics = core.ReceiveMetrics()
        stamp = int(metrics.since) + 2
        with patch.object(core.time, 'time', return_value=stamp):
            metrics.record('gateway_1', 'embb', 1234, 'video')
        with patch.object(core.time, 'time', return_value=stamp + 1):
            sample = metrics.snapshot('gateway_1')
        self.assertEqual(sample['received_bps'], 1234 * 8)
        self.assertEqual(sample['slices']['embb']['video_fps'], 1)
        with patch.object(core.time, 'time', return_value=stamp + 3):
            sample = metrics.snapshot('gateway_1')
        self.assertEqual(sample['received_bps'], 0)
        self.assertEqual(sample['bytes'], 1234)

    def test_receive_history_is_bounded_and_restart_has_new_identity(self):
        metrics = core.ReceiveMetrics()
        stamp = int(metrics.since) + 2
        for tick in range(100):
            with patch.object(core.time, 'time', return_value=stamp + tick):
                metrics.record('gateway_2', 'mmtc', 10, 'json')
        with patch.object(core.time, 'time', return_value=stamp + 101):
            result = metrics.snapshot('gateway_2')
        self.assertLessEqual(len(result['history']), 60)
        self.assertEqual(result['json'], 100)
        self.assertEqual(result['bytes'], 1000)
        self.assertNotEqual(metrics.process_id, core.ReceiveMetrics().process_id)

    def test_server_telemetry_http_reports_receipt_not_business_delivery(self):
        hub = server.LatestSliceStateHub()
        hub.update('gateway2', {'type': 'slice_metrics', 'gateway': 'gateway_2', 'slices': {}})
        with patch.object(server, '_SLICE_METRICS_HUB', hub):
            http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.ControlHandler)
            threading.Thread(target=http.serve_forever, daemon=True).start()
            try:
                with urllib.request.urlopen('http://127.0.0.1:{}/telemetry'.format(http.server_address[1]), timeout=3) as response:
                    data = json.load(response)
                self.assertEqual(data['reports_received'], 1)
                self.assertIn('gateway2', data['gateways'])
            finally:
                http.shutdown();http.server_close()

    def test_failed_delivery_is_not_counted_as_confirmed(self):
        class Unavailable:
            def require(self):
                raise ConnectionError('local simulation: no tunnel')
        metrics = self.collector()
        sender = edge.TunnelJsonSender(Unavailable(), None, None, metrics=metrics)
        wire = json.dumps({'type': 'alarm', 'gateway': 'gateway_1'})
        for _ in range(2):
            with self.assertRaises(ConnectionError):
                sender._send(wire, 'same-message')
        delivery = metrics.snapshot()['slices']['urllc']['delivery']
        self.assertEqual(delivery['attempts'], 2)
        self.assertEqual(delivery['failed'], 2)
        self.assertEqual(delivery['confirmed'], 0)
        self.assertEqual(delivery['retries'], 1)
        self.assertEqual(delivery['ack_success_pct'], 0)

    def test_local_standby_cannot_be_rendered_as_active_path(self):
        registry = core.SliceMetricsRegistry(Heartbeat())
        payload = self.collector().snapshot()
        payload['transport'] = {'business_allowed': False, 'business_mode': 'standby'}
        rx = core.ReceiveMetrics()
        transport = {'enabled': True, 'business_mode': 'active',
                     'last_probes': time.time(), 'received': rx.snapshot('gateway_1')}
        sidebar = registry.sidebar('Gateway1', 'online', payload, transport, {})
        self.assertIsNone(sidebar['current_path'])
        self.assertFalse(sidebar['links']['tunnel']['business_allowed'])

    def test_relay_retains_fields_and_ages_cached_snapshots(self):
        hub = server.LatestSliceStateHub()
        payload = self.collector().snapshot()
        payload['transport'] = {'rtt_ms': 42, 'critical_pending': 1}
        hub.update('gateway1', payload)
        forwarded = json.loads(hub.initial()[1][0])
        self.assertNotIn('relay', payload)
        self.assertEqual(forwarded['transport'], payload['transport'])
        self.assertEqual(hub.snapshot()['reports_received'], 1)
        forwarded['relay']['server_received_at'] = time.time() - 30
        registry = core.SliceMetricsRegistry(Heartbeat())
        registry.update(forwarded)
        gateway = registry.snapshot()['gateways'][0]
        self.assertEqual(gateway['edge']['status'], 'offline')
        self.assertIsNone(gateway['sidebar']['slices']['embb']['send_bps'])
        self.assertIsNone(gateway['sidebar']['links']['tunnel']['probe_rtt_ms'])

    def test_satellite_module_confirmation_does_not_claim_ground_delivery(self):
        module = edge.SatelliteUplink('auto', 115200, 'gateway_1', 60, 4, 3, 0, False)
        self.assertIsNone(module.snapshot()['ground_confirmed'])
        with patch.object(module, '_build_payload', return_value=({'s': 'WS', 'v': 2, 't': '261015120000'}, b'123')), patch.object(module, '_send_at_command', return_value=(True, ['+FrameNo: 7', 'OK'])):
            self.assertTrue(module._send_business_frame(object(), 'test'))
        state = module.snapshot()
        self.assertEqual(state['module_confirmed'], 1)
        self.assertEqual(state['confirmed_bytes'], 3)
        self.assertIsNone(state['ground_confirmed'])
        with patch.object(module, '_send_at_command', return_value=(False, ['ERROR'])):
            self.assertIsNone(module._query_pending_count(object()))
        self.assertIsNone(module.snapshot()['pending_frames'])

    def test_missing_fields_stay_null_and_events_do_not_repeat(self):
        registry = core.SliceMetricsRegistry(Heartbeat())
        first = registry.snapshot()
        sidebar = first['gateways'][0]['sidebar']
        self.assertEqual(sidebar['links']['server_relay']['state'], 'not_deployed')
        self.assertIsNone(sidebar['links']['tunnel']['probe_success_pct'])
        self.assertIsNone(sidebar['slices']['embb']['end_to_end_frame_age_ms'])
        payload = self.collector().snapshot()
        registry.update(payload)
        second = registry.snapshot()['gateways'][0]['sidebar']
        third = registry.snapshot()['gateways'][0]['sidebar']
        self.assertEqual(len(second['events']), 1)
        self.assertEqual(second['events'], third['events'])

    def test_two_gateway_tcp_sources_have_separate_receive_counters(self):
        with tempfile.TemporaryDirectory() as temp:
            ingress = core.CoreIngress('127.0.0.1', 0,
                {'127.0.0.1': 'gateway_1', '127.0.0.2': 'gateway_2'},
                core.Inbox(str(pathlib.Path(temp) / 'two.db')),
                lambda *args: None, lambda *args: None, scenes=core.TUNNEL_SCENES,
                log=lambda *args: None)
            ingress.start()
            self.assertTrue(ingress.ready.wait(3))
            try:
                for source, gateway in [('127.0.0.1', 'gateway_1'), ('127.0.0.2', 'gateway_2')]:
                    with socket.socket() as client:
                        client.settimeout(3)
                        client.bind((source, 0))
                        client.connect(ingress.sock.getsockname())
                        payload = {'gateway': gateway, 'type': 'sensor', 'value': 2,
                            '_transport': {'version': '1.0', 'delivery_id': 'same-id'}}
                        client.sendall((json.dumps(payload) + '\n').encode())
                        reader = client.makefile('rb')
                        self.assertEqual(json.loads(reader.readline())['status'], 'accepted')
                        reader.close()
                first = ingress.snapshot('gateway_1')['received']
                second = ingress.snapshot('gateway_2')['received']
                self.assertEqual(first['json'], 1)
                self.assertEqual(second['json'], 1)
                self.assertEqual(first['bytes'], second['bytes'])
            finally:
                ingress.stop()

    def test_real_sender_receiver_server_tcp_http_and_sse(self):
        with tempfile.TemporaryDirectory() as temp:
            ingress = core.CoreIngress('127.0.0.1', 0, {'127.0.0.1': 'gateway_1'},
                core.Inbox(str(pathlib.Path(temp) / 'inbox.db')),
                lambda *args: None, lambda *args: None, scenes=core.TUNNEL_SCENES, log=lambda *args: None)
            ingress.start()
            self.assertTrue(ingress.ready.wait(3))
            path = edge.PathManager('gateway_1', '127.0.0.1', ingress.sock.getsockname()[1], interval=0.1)
            path.start()
            old_ingress, old_path, old_outbox = core._TUNNEL_INGRESS, edge._TUNNEL_PATH, edge._TUNNEL_OUTBOX
            core._TUNNEL_INGRESS, edge._TUNNEL_PATH = ingress, path
            outbox = edge.Outbox(str(pathlib.Path(temp) / 'outbox.db'))
            edge._TUNNEL_OUTBOX = outbox
            http = None
            sockets = []
            sender = None
            media = None
            try:
                wait_for(path.allowed)
                collector = self.collector()
                payload = {'gateway': 'gateway_1', 'type': 'alarm', 'validation': 'local-only'}
                item = outbox.add({'json_data': json.dumps(payload), 'slice_id': 'urllc'}, 'gateway_1')
                sender = edge.TunnelJsonSender(path, None, outbox, metrics=collector)
                ack = sender._send(item['json_data'], item['delivery_id'])
                self.assertEqual(ack['status'], 'accepted')
                self.assertEqual(sender._send(item['json_data'], item['delivery_id'])['status'], 'duplicate')
                outbox.ack(item['delivery_id'])
                image = FIXTURE.read_bytes()
                metadata = json.dumps({'gateway': 'gateway_1'}).encode()
                body = struct.pack('!I', len(metadata)) + metadata + image
                media = edge.MediaCloudConnection('127.0.0.1', path.port, 'gateway_1', True)
                for kind in (b'VID0', b'SNAP'):
                    media.send_raw_packet(struct.pack('!4sQ', kind, len(body)) + body)
                wait_for(lambda: ingress.snapshot('gateway_1')['media_received'] == 2)
                rx = ingress.snapshot('gateway_1')['received']
                self.assertEqual(rx['bytes'], len(core._lgdt_json_bytes(payload)) + len(image) * 2)
                self.assertEqual((rx['json'], rx['video'], rx['snapshot']), (1, 1, 1))
                snapshot = collector.snapshot()
                delivery = snapshot['slices']['urllc']['delivery']
                self.assertEqual((delivery['attempts'], delivery['confirmed'], delivery['retries']), (2, 2, 1))
                upstream = socket.socket();upstream.bind(('127.0.0.1', 0));upstream.listen(1)
                client = socket.create_connection(upstream.getsockname());accepted, address = upstream.accept()
                sockets.extend([upstream, client, accepted])
                hub = server.LatestSliceStateHub()
                threading.Thread(target=server.handle_slice_upstream,
                    args=(accepted, address, hub, 1024 * 1024), daemon=True).start()
                client.sendall((json.dumps(snapshot) + '\n').encode())
                wait_for(lambda: hub.snapshot()['reports_received'] == 1)
                downstream = socket.socket();downstream.bind(('127.0.0.1', 0));downstream.listen(1)
                consumer = socket.create_connection(downstream.getsockname());producer, address = downstream.accept()
                sockets.extend([downstream, consumer, producer])
                consumer.settimeout(3)
                threading.Thread(target=server.handle_slice_downstream,
                    args=(producer, address, hub), daemon=True).start()
                stream = consumer.makefile('rb')
                forwarded = json.loads(stream.readline())
                stream.close()
                registry = core.SliceMetricsRegistry(Heartbeat())
                self.assertTrue(registry.update(forwarded))
                combined = registry.snapshot()
                evidence = os.environ.get('LGD_TELEMETRY_EVIDENCE_DIR')
                if evidence:
                    directory = pathlib.Path(evidence)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / 'http_snapshot.json').write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding='utf-8')
                sidebar = combined['gateways'][0]['sidebar']
                self.assertEqual(sidebar['current_path'], '5g_tunnel')
                self.assertEqual(sidebar['links']['tunnel']['json_received'], 1)
                self.assertGreater(sidebar['links']['tunnel']['probe_attempts'], 0)
                self.assertEqual(sidebar['slices']['urllc']['pending'], 0)
                output = core.JsonHub('slice_metrics', 11420, None)
                output.update(json.dumps(combined), combined)
                http = core.ThreadingHTTPServer(('127.0.0.1', 0), core.make_json_handler(output))
                threading.Thread(target=http.serve_forever, daemon=True).start()
                base = 'http://127.0.0.1:' + str(http.server_address[1])
                with urllib.request.urlopen(base + '/latest.json', timeout=3) as response:
                    self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
                    self.assertEqual(json.load(response)['schema_version'], '1.1')
                with urllib.request.urlopen(base + '/events', timeout=3) as response:
                    self.assertIn('text/event-stream', response.headers['Content-Type'])
                    self.assertTrue(response.readline().startswith(b': connected'))
                    output.update(json.dumps(combined), combined)
                    lines = []
                    while True:
                        line = response.readline()
                        lines.append(line)
                        if line.startswith(b'data: '):
                            self.assertEqual(json.loads(line[6:])['schema_version'], '1.1')
                            break
                    self.assertTrue(any(line.startswith(b'event: json') for line in lines))
                # Lose the connection after a unique message is accepted:
                # a retry still receives duplicate ACK, not a second publication.
                sender.close()
                retry = sender._send(item['json_data'], item['delivery_id'])
                self.assertEqual(retry['status'], 'duplicate')
                self.assertEqual(ingress.snapshot('gateway_1')['received']['json'], 1)
                self.assertEqual(collector.snapshot()['slices']['urllc']['delivery']['retries'], 2)
            finally:
                if sender:sender.close()
                if media:media.close()
                path.closed.set();path.monitor.closed.set()
                if http:http.shutdown();http.server_close()
                for sock in sockets:
                    try:sock.close()
                    except OSError:pass
                ingress.stop()
                core._TUNNEL_INGRESS, edge._TUNNEL_PATH, edge._TUNNEL_OUTBOX = old_ingress, old_path, old_outbox


if __name__ == '__main__':
    unittest.main()
