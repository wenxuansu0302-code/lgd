import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CorePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "core/root/lgd"))
        sys.modules.pop("config", None)
        cls.core = load_module("core_gateway_v13", ROOT / "core/root/lgd/gateway_v1.py")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        inbox = self.core.Inbox(str(pathlib.Path(self.temp.name) / "inbox.db"))
        self.ingress = self.core.CoreIngress(
            "127.0.0.1",
            0,
            self.core.TUNNEL_PEERS,
            inbox,
            lambda gateway, payload: None,
            lambda gateway, kind, metadata, jpeg, seq: None,
            scenes=self.core.TUNNEL_SCENES,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_gw1_and_gw2_are_active(self):
        self.assertTrue(self.ingress.business_allowed("gateway_1", "JSON"))
        self.assertTrue(self.ingress.business_allowed("gateway_2", "VID0"))

    def test_gw4_stays_standby_when_group_three_recovers(self):
        self.ingress.set_group(3, True)
        policy = self.ingress.policy("gateway_4")
        self.assertEqual(policy["business_mode"], "standby")
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["allowed_kinds"], [])

    def test_group_stop_does_not_change_scene_mode(self):
        self.ingress.set_group(1, False)
        policy = self.ingress.policy("gateway_1")
        self.assertEqual(policy["business_mode"], "active")
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["policy_reason"], "group_disabled")

    def test_wifi_channel_is_never_a_tunnel_route(self):
        self.assertNotIn("gateway_4", self.core.TUNNEL_JSON_ROUTES)
        self.assertEqual(self.core.TUNNEL_SOURCE_OWNER[(11408, "JSON")], "legacy")


class EdgePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "edge/root/lgd"))
        sys.modules.pop("config", None)
        sys.modules.pop("edge_config", None)
        cls.edge = load_module("edge_gateway_v13", ROOT / "edge/root/lgd/gateway_merged.py")

    def test_local_standby_never_starts_allowed(self):
        path = self.edge.PathManager(
            "gateway_4", "10.77.0.10", 11500, business_mode="standby"
        )
        state = path.snapshot()
        self.assertEqual(state["business_mode"], "standby")
        self.assertFalse(state["business_allowed"])
        self.assertFalse(path.allowed())

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self.edge.PathManager(
                "gateway_1", "10.77.0.10", 11500, business_mode="automatic"
            )

    def test_probe_failure_keeps_both_admission_flags_consistent(self):
        path = self.edge.PathManager("gateway_1", "10.77.0.10", 11500)
        path.state.update(allowed=True, business_allowed=True)
        for _ in range(3):
            path.record_failure(ConnectionError("probe failed"))
        state = path.snapshot()
        self.assertFalse(state["allowed"])
        self.assertFalse(state["business_allowed"])
        self.assertEqual(state["core_probe"], "unavailable")


if __name__ == "__main__":
    unittest.main()
