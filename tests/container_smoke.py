"""Run inside the built image; no hardware and no actual print job submitted."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import time

spec = importlib.util.spec_from_file_location("server", "/opt/printserver/server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
Path("/run/cups").mkdir(parents=True, exist_ok=True)
Path("/etc/cups/cupsd.conf").write_text(server.cups_config())
server.run("cupsd", "-t")
cups = subprocess.Popen(["cupsd", "-f"])
try:
    for _ in range(30):
        if Path("/run/cups/cups.sock").exists():
            break
        time.sleep(1)
    driver = server.select_driver(server.run("lpinfo", "-m"))
    server.run("lpadmin", "-p", "Smoke", "-m", driver,
               "-v", "usb://HP/LaserJet%20Professional%20P1102w?serial=smoke",
               "-o", "printer-is-shared=true", "-o", "PageSize=A4")
    with tempfile.TemporaryDirectory() as folder:
        ps = Path(folder) / "page.ps"
        pdf = Path(folder) / "page.pdf"
        ps.write_text("%!PS\n/Helvetica findfont 12 scalefont setfont\n72 720 moveto (Printserver smoke test) show\nshowpage\n")
        subprocess.run(["gs", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
                        f"-sOutputFile={pdf}", str(ps)], check=True, timeout=30)
        result = subprocess.run(["cupsfilter", "-p", "/etc/cups/ppd/Smoke.ppd",
                                 "-m", "printer/Smoke", "-e", str(pdf)],
                                capture_output=True, check=True, timeout=60)
        assert result.stdout, "Driver produced no output"
        print(f"PASS: P1102w PDF filter chain produced {len(result.stdout)} bytes")
finally:
    cups.terminate()
    cups.wait(timeout=10)
