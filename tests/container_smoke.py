"""Run inside the built image; no hardware and only held jobs, no USB transmission."""
import cups
import ctypes
import ctypes.util
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import time

spec = importlib.util.spec_from_file_location("server", "/opt/printserver/server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
Path("/run/cups").mkdir(parents=True, exist_ok=True)
for debug in (True, False):
    Path("/etc/cups/cupsd.conf").write_text(server.cups_config(debug))
    server.run("cupsd", "-t")
cupsd = subprocess.Popen(["cupsd", "-f"])
try:
    for _ in range(30):
        if Path("/run/cups/cups.sock").exists():
            break
        time.sleep(1)
    driver = server.select_driver(server.run("lpinfo", "-m"))
    server.run("lpadmin", "-p", "Smoke", "-m", driver,
               "-v", "usb://HP/LaserJet%20Professional%20P1102w?serial=smoke",
               "-o", "printer-is-shared=true", "-o", "PageSize=A4",
               *server.usb_options({}))
    with tempfile.TemporaryDirectory() as folder:
        ps = Path(folder) / "page.ps"
        pdf = Path(folder) / "page.pdf"
        ps.write_text("%!PS\n/Helvetica findfont 12 scalefont setfont\n72 720 moveto (Printserver smoke test) show\nshowpage\n")
        subprocess.run(["gs", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
                        f"-sOutputFile={pdf}", str(ps)], check=True, timeout=30)
        # Hold every job: validate CUPS default-option propagation without
        # allowing the USB backend to transmit to any device.
        server.run("cupsaccept", "Smoke")
        connection = cups.Connection(host="/run/cups/cups.sock")
        for enabled in (True, False):
            server.run("lpadmin", "-p", "Smoke", *server.usb_options({"usb_unidir": enabled}))
            job = connection.printFile("Smoke", str(pdf), "USB option check",
                                       {"job-hold-until": "indefinite"})
            try:
                attrs = connection.getJobAttributes(job)
                assert attrs["job-state"] == 4, attrs
                actual = str(attrs.get("usb-unidir", "")).lower()
                assert actual == str(enabled).lower(), (enabled, actual)
            finally:
                connection.cancelJob(job)
        print("PASS: CUPS forwards usb-unidir defaults to held jobs (true/false)")
        # A test-only backend captures CUPS' real argv and drains the data.
        # No USB backend or physical device is used for these jobs.
        backend = Path("/usr/lib/cups/backend/optioncheck")
        backend.write_text("#!/usr/bin/python3\nimport pathlib, sys\n"
                           "pathlib.Path('/tmp/backend-options-' + sys.argv[1]).write_text(sys.argv[5])\n"
                           "while sys.stdin.buffer.read(65536): pass\n")
        backend.chmod(0o755)
        server.run("lpadmin", "-p", "OptionCheck", "-m", driver,
                   "-v", "optioncheck:/sink", "-E")
        for enabled in (True, False):
            server.run("lpadmin", "-p", "OptionCheck", *server.usb_options({"usb_unidir": enabled}))
            job = connection.printFile("OptionCheck", str(pdf), "Backend argv check", {})
            for _ in range(60):
                attrs = connection.getJobAttributes(job)
                if attrs["job-state"] >= 7:
                    break
                time.sleep(1)
            assert attrs["job-state"] == 9, attrs
            actual = Path(f"/tmp/backend-options-{job}").read_text()
            # CUPS serializes booleans as bare usb-unidir/nousb-unidir.
            # Parse with the same libcups API that the real USB backend uses.
            libcups = ctypes.CDLL(ctypes.util.find_library("cups"))
            libcups.cupsParseOptions.argtypes = [ctypes.c_char_p, ctypes.c_int,
                                                 ctypes.POINTER(ctypes.c_void_p)]
            libcups.cupsGetOption.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
            libcups.cupsGetOption.restype = ctypes.c_char_p
            libcups.cupsFreeOptions.argtypes = [ctypes.c_int, ctypes.c_void_p]
            parsed = ctypes.c_void_p()
            count = libcups.cupsParseOptions(actual.encode(), 0, ctypes.byref(parsed))
            try:
                value = libcups.cupsGetOption(b"usb-unidir", count, parsed)
                assert value == str(enabled).lower().encode(), (enabled, value, actual)
            finally:
                libcups.cupsFreeOptions(count, parsed)
        print("PASS: real CUPS backend argv includes usb-unidir=true/false; filtered jobs completed")

        jpeg = Path(folder) / "page.jpg"
        subprocess.run(["gs", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=jpeg",
                        "-r72", f"-sOutputFile={jpeg}", str(ps)], check=True, timeout=30)
        for document in (pdf, jpeg):
            result = subprocess.run(["cupsfilter", "-p", "/etc/cups/ppd/Smoke.ppd",
                                     "-m", "printer/Smoke", "-e", str(document)],
                                    capture_output=True, check=True, timeout=60)
            assert result.stdout, "Driver produced no output"
            print(f"PASS: P1102w {document.suffix[1:].upper()} filter chain produced {len(result.stdout)} bytes")

finally:
    cupsd.terminate()
    cupsd.wait(timeout=10)
