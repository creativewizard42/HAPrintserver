import importlib.util
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET

spec = importlib.util.spec_from_file_location(
    "server", Path(__file__).resolve().parents[1] / "hp_printserver/rootfs/opt/printserver/server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class ServerTests(unittest.TestCase):
    def options(self, **changes):
        return dict(printer_name="HP_P1102w", printer_description="HP & kantoor",
                    admin_password="test-password-123", device_uri="", **changes)

    def test_options_reject_config_and_password_injection(self):
        for key, value in [("printer_name", "bad\nPort 123"),
                           ("admin_password", "secret\nroot:password"),
                           ("device_uri", "socket://printer"),
                           ("printer_description", "HP\nprinter")]:
            options = self.options()
            options[key] = value
            with self.assertRaises(ValueError):
                server.validate(options)

    def test_usb_compatibility_and_debug_flags_reject_strings(self):
        for key in ("usb_unidir", "usb_no_reattach", "debug_logging"):
            with self.assertRaises(ValueError):
                server.validate(self.options(**{key: "false"}))

    def test_debug_logging_is_opt_in(self):
        self.assertIn("LogLevel info\n", server.cups_config())
        self.assertIn("LogLevel debug\n", server.cups_config(True))

    def test_cups_log_relay_keeps_jobs_and_errors_but_drops_http_debug(self):
        import io
        messages = []
        source = io.StringIO(
            'D [time] [Client 1] bytes=0\n'
            'D [time] [Job 3] Forced uni-directional communication\n'
            'E [time] USB failure\n'
            'I [time] Started backend\n')
        server.relay_cups_logs(source, lambda message, **kwargs: messages.append(message))
        self.assertEqual(len(messages), 3)
        self.assertTrue(any('Forced uni-directional' in line for line in messages))
        self.assertTrue(any('USB failure' in line for line in messages))

    def test_usb_presence_requires_target_model_and_exact_serial(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            device = root / '1-1'
            device.mkdir()
            for name, value in [('idVendor', '03f0'), ('idProduct', '102a'), ('serial', 'target')]:
                (device / name).write_text(value + '\n')
            uri = 'usb://HP/P1102w?serial=target'
            self.assertTrue(server.usb_present(uri, root))
            self.assertFalse(server.usb_present('usb://HP/P1102w?serial=other', root))
            (device / 'idProduct').write_text('0001')
            self.assertFalse(server.usb_present(uri, root))
            self.assertIsNone(server.usb_present('usb://HP/P1102w', root))

    def test_empty_password_requires_configuration(self):
        options = self.options()
        options["admin_password"] = ""
        with self.assertRaises(ValueError):
            server.validate(options)

    def test_usb_discovery_only_matches_correct_model(self):
        output = "network ipp\ndirect usb://HP/Other\ndirect usb://HP/LaserJet%20Professional%20P1102w?serial=123"
        self.assertEqual(server.select_device(output),
                         "usb://HP/LaserJet%20Professional%20P1102w?serial=123")
        self.assertIsNone(server.select_device("network socket://P1102w"))

    def test_multiple_printers_require_explicit_selection(self):
        with self.assertRaises(ValueError):
            server.select_device("direct usb://HP/P1102w?serial=1\ndirect usb://HP/P1102w?serial=2")

    def test_usb_model_with_space_from_printer_log(self):
        uri = "usb://HP/LaserJet%20Professional%20P%201102w?serial=000000000W438BQ6PR1a"
        self.assertEqual(server.select_device("direct " + uri), uri)
        self.assertIsNone(server.select_device("direct usb://HP/P%201102wExtra"))

    def test_other_usb_devices_and_serials_are_not_model_matches(self):
        output = "\n".join([
            "direct usb://SSD/Storage?serial=P1102w",
            "direct usb://Zigbee/Radio",
            "direct usb://HP/Other?serial=P1102w",
            "direct usb://Other/P1102w",
            "direct usb://HP/P1102wExtra",
        ])
        self.assertIsNone(server.select_device(output))
        uri = "usb://HP/LaserJet%20Professional%20P1102w?serial=real-printer"
        self.assertEqual(server.select_device(output + "\ndirect " + uri), uri)

    def test_driver_selection_requires_model_and_filter(self):
        self.assertEqual(server.select_driver(
            "wrong HP P1102\nfoo.ppd HP P1102w Foomatic/foo2zjs-z2"), "foo.ppd")
        with self.assertRaises(RuntimeError):
            server.select_driver("generic Generic PostScript")

    def test_airprint_service_is_valid_and_escapes_description(self):
        root = ET.fromstring(server.airprint_xml("HP_P1102w", "HP & kantoor"))
        self.assertEqual(root.findtext("name"), "HP & kantoor")
        self.assertEqual(root.findtext("service/subtype"), "_universal._sub._ipp._tcp")
        records = [item.text for item in root.findall("service/txt-record")]
        self.assertIn("rp=printers/HP_P1102w", records)
        self.assertIn("Duplex=F", records)

    def test_spool_survives_reinitialization(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "spool"
            source.mkdir()
            (source / "job").write_text("pending")
            try:
                server.persist(source, base / "data")
            except OSError as error:
                if getattr(error, "winerror", None) == 1314:
                    self.skipTest("Windows symlink privilege unavailable")
                raise
            server.persist(source, base / "data")
            self.assertEqual((source / "job").read_text(), "pending")


if __name__ == "__main__":
    unittest.main()
