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
