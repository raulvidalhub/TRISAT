import json
import unittest
from contextlib import closing
from http.client import HTTPConnection

from trisat_sdr.config import ReceiverConfig
from trisat_sdr.receiver import TrisatSdrReceiver
from trisat_sdr.ui.web_dashboard import TrisatWebDashboardServer


class TestWebDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard = TrisatWebDashboardServer(TrisatSdrReceiver(ReceiverConfig()), port=0)
        dashboard.start()
        cls.addClassCleanup(dashboard._httpd.server_close)
        if dashboard._mirror_httpd is not None:
            cls.addClassCleanup(dashboard._mirror_httpd.server_close)
        cls.addClassCleanup(dashboard.stop)
        cls.port = dashboard._httpd.server_port

    def request(self, method, path):
        with closing(HTTPConnection("127.0.0.1", self.port, timeout=5)) as connection:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, response.headers, response.read()

    def request_json(self, method, path, expected_status):
        status, headers, body = self.request(method, path)
        self.assertEqual(status, expected_status)
        self.assertEqual(headers.get_content_type(), "application/json")
        return json.loads(body)

    def test_dashboard_and_status_are_served(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/html")
        self.assertIn(b'id="bandSelect"', body)
        snapshot = self.request_json("GET", "/api/status", 200)
        self.assertIn("band_id", snapshot["secondary_sdr"])

    def test_unknown_routes_return_json_errors(self):
        for method, path in (
            ("GET", "/api/snapshot"),
            ("GET", "/api/health"),
            ("GET", "/missing"),
            ("POST", "/api/missing"),
        ):
            with self.subTest(method=method, path=path):
                self.assertIn("error", self.request_json(method, path, 404))

    def test_invalid_band_does_not_change_receiver_configuration(self):
        path = "/api/set_band"
        result = self.request_json("POST", path + "?band=GAL_E5B", 200)
        self.assertEqual(result, {"status": "ok"})
        snapshot = self.request_json("GET", "/api/status", 200)
        self.assertEqual(snapshot["secondary_sdr"]["band_id"], "GAL_E5B")

        for query in ("band=invalid", "band=", "band=GAL_E6&band=GAL_E5A"):
            with self.subTest(query=query):
                self.assertIn("error", self.request_json("POST", path + "?" + query, 400))
                snapshot = self.request_json("GET", "/api/status", 200)
                self.assertEqual(snapshot["secondary_sdr"]["band_id"], "GAL_E5B")

        self.request_json("POST", path, 200)
        snapshot = self.request_json("GET", "/api/status", 200)
        self.assertEqual(snapshot["secondary_sdr"]["band_id"], "GAL_E6")
