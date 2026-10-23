"""Run inside the built image; no hardware and only held jobs, no USB transmission."""
import cups
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
