"""HA OS USB print server. CUPS owns jobs; this process supervises services."""
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import threading
from urllib.parse import parse_qs, unquote, urlsplit
from xml.etree import ElementTree as ET

QUEUE_PATTERN = r"[A-Za-z][A-Za-z0-9_-]{0,62}"


def validate(options):
    if not re.fullmatch(QUEUE_PATTERN, options["printer_name"]):
        raise ValueError("Ongeldige printer_name")
    password = options.get("admin_password", "")
    if len(password) < 12 or any(c in password for c in "\r\n\x00"):
        raise ValueError("Stel admin_password in op minimaal 12 tekens")
    uri = options.get("device_uri", "")
    if uri and (not uri.startswith("usb://") or any(c.isspace() for c in uri)):
        raise ValueError("device_uri moet een usb:// URI zijn, of leeg voor detectie")
    description = options["printer_description"]
    if not description.strip() or any(ord(c) < 32 for c in description):
        raise ValueError("Ongeldige printer_description")
    for key in ("usb_unidir", "debug_logging"):
        if key in options and not isinstance(options[key], bool):
            raise ValueError(f"{key} moet een boolean zijn")
    return options


def cups_config(debug=False):
    config = """Port 631
Listen /run/cups/cups.sock
ServerAlias *
WebInterface Yes
Browsing Off
DefaultAuthType Basic
DefaultEncryption IfRequested
DefaultShared Yes
DefaultPolicy default
ErrorPolicy retry-job
JobRetryInterval 60
JobRetryLimit 3
PreserveJobFiles No
PreserveJobHistory Yes
MaxJobs 100
MaxRequestSize 52428800
LogLevel info
<Location />
  Order allow,deny
  Allow localhost
  Allow @LOCAL
</Location>
<Location /admin>
  AuthType Default
  Require user @SYSTEM
  Encryption Required
  Order allow,deny
  Allow localhost
  Allow @LOCAL
</Location>
<Policy default>
  <Limit CUPS-Add-Modify-Printer CUPS-Delete-Printer CUPS-Set-Default CUPS-Add-Modify-Class CUPS-Delete-Class CUPS-Accept-Jobs CUPS-Reject-Jobs Pause-Printer Resume-Printer Enable-Printer Disable-Printer Pause-Printer-After-Current-Job Hold-New-Jobs Release-Held-New-Jobs Restart-Printer Shutdown-Printer Startup-Printer Promote-Job Schedule-Job-After CUPS-Authenticate-Job>
    AuthType Default
    Require user @SYSTEM
    Order deny,allow
  </Limit>
  <Limit Send-Document Send-URI Hold-Job Release-Job Restart-Job Purge-Jobs Set-Job-Attributes Cancel-Job CUPS-Move-Job Cancel-My-Jobs Close-Job>
    Require user @OWNER @SYSTEM
    Order deny,allow
  </Limit>
  <Limit All>
    Order deny,allow
  </Limit>
</Policy>
"""

    return config.replace("LogLevel info", "LogLevel debug" if debug else "LogLevel info")


def usb_options(options):
    # CUPS 2.x usb-libusb supports this job option. Keep it out of the
    # device URI so serial-based detection and exact URI matching still work.
    return ["-o", "usb-unidir-default=" +
            ("true" if options.get("usb_unidir", True) else "false")]


def airprint_xml(name, description):
    root = ET.Element("service-group")
    ET.SubElement(root, "name").text = description
    service = ET.SubElement(root, "service")
    ET.SubElement(service, "type").text = "_ipp._tcp"
    ET.SubElement(service, "subtype").text = "_universal._sub._ipp._tcp"
    ET.SubElement(service, "port").text = "631"
    for item in ["txtvers=1", "qtotal=1", f"rp=printers/{name}",
                 f"ty={description}", "product=(HP LaserJet Pro P1102w)",
                 "pdl=application/pdf,image/urf,image/jpeg,image/pwg-raster",
                 "URF=W8,SRGB24,CP1,RS600", "Color=F", "Duplex=F"]:
        ET.SubElement(service, "txt-record").text = item
    return ET.tostring(root, encoding="unicode")


def select_device(output):
    matches = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].startswith("usb://"):
            device = urlsplit(parts[1])
            if device.netloc.lower() == "hp" and re.search(
                    r"\bp\s*1102w\b", unquote(device.path), re.IGNORECASE):
                matches.append(parts[1])
    if len(matches) > 1:
        raise ValueError("Meerdere P1102w-printers: stel device_uri expliciet in")
    return matches[0] if matches else None


def select_driver(output):
    for line in output.splitlines():
        if "p1102w" in line.lower() and "foo2zjs" in line.lower():
            return line.split()[0]
    raise RuntimeError("Geen P1102w foo2zjs-driver gevonden")


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=45).stdout


def persist(source, target, seed=None):
    if not target.exists():
        shutil.copytree(seed or source, target)
    if source.is_symlink():
        source.unlink()
    elif source.exists():
        shutil.rmtree(source)
    source.symlink_to(target, target_is_directory=True)


def relay_cups_logs(stream, log=print):
    # HTTP debug traffic otherwise evicts the backend startup from HA's logs.
    # Keep every job diagnostic and all non-debug messages, including errors.
    for line in stream:
        if not line.startswith("D [") or re.search(r"\[Job \d+\]", line):
            log(line.rstrip(), flush=True)


def usb_present(uri, root=Path("/sys/bus/usb/devices")):
    """Inspect only sysfs metadata; never claim a busy USB interface to probe it."""
    device = urlsplit(uri)
    serial = parse_qs(device.query).get("serial", [None])[0]
    if device.scheme != "usb" or device.netloc.lower() != "hp" or not serial:
        return None
    try:
        entries = list(root.iterdir())
    except OSError:
        return None
    for entry in entries:
        try:
            if ((entry / "idVendor").read_text().strip().lower() == "03f0"
                    and (entry / "idProduct").read_text().strip().lower() == "102a"
                    and (entry / "serial").read_text().strip() == serial):
                return True
        except OSError:
            continue
    return False


def main():
    import cups
    from monitor import JobMonitor

    options = validate(json.loads(Path("/data/options.json").read_text()))
    data = Path("/data")
    persist(Path("/etc/cups"), data / "cups", Path("/opt/cups-default"))
    persist(Path("/var/spool/cups"), data / "spool")
    # Preserve access for CUPS' lp group without changing job-file ownership.
    # copytree copies modes, but creates the directory with root's group.
    shutil.chown(data / "spool", user="root", group="lp")
    (data / "spool").chmod(0o710)
    persist(Path("/var/cache/cups"), data / "cache")
    # copytree preserves modes but not Unix ownership. cupsd drops privileges
    # for driver discovery, so an originally root-owned copy is not writable.
    for entry in [data / "cache", *(data / "cache").rglob("*")]:
        if not entry.is_symlink():
            shutil.chown(entry, user="lp", group="lp")
    (data / "cache").chmod(0o770)
    Path("/etc/cups/cupsd.conf").write_text(cups_config(options.get("debug_logging", False)))
    subprocess.run(["chpasswd"], input=f"printadmin:{options['admin_password']}\n",
                   text=True, check=True)
    for folder in ["/run/cups", "/run/dbus", "/run/avahi-daemon"]:
        Path(folder).mkdir(parents=True, exist_ok=True)
    interfaces = sorted(entry.name for entry in Path("/sys/class/net").iterdir()
                        if (entry / "device").exists())
    interface_config = ("allow-interfaces=" + ",".join(interfaces) + "\n") if interfaces else ""
    Path("/etc/avahi/avahi-daemon.conf").write_text("""[server]
host-name=hp-printserver
""" + interface_config + """\
use-ipv4=yes
use-ipv6=yes
allow-point-to-point=no
[wide-area]
enable-wide-area=no
[publish]
publish-workstation=no
[reflector]
enable-reflector=no
""")
    # Logging to HA app logs while retaining Debian's default path/permission settings.
    files = Path("/etc/cups/cups-files.conf")
    content = files.read_text()
    for key in ["ErrorLog", "AccessLog", "PageLog"]:
        content = re.sub(rf"(?m)^\s*{key}\s+.*$", f"{key} stderr", content)
    files.write_text(content)
    run("cupsd", "-t")
    children = []
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen(["dbus-daemon", "--system", "--nofork", "--nopidfile"]))
        time.sleep(1)
        children.append(subprocess.Popen(["avahi-daemon", "--no-chroot"]))
        cupsd = subprocess.Popen(["cupsd", "-f"], stderr=subprocess.PIPE,
                                 text=True, encoding="utf-8", errors="replace")
        children.append(cupsd)
        log_thread = threading.Thread(target=relay_cups_logs, args=(cupsd.stderr,), daemon=True)
        log_thread.start()
        for _ in range(30):
            if Path("/run/cups/cups.sock").exists():
                break
            time.sleep(1)
        driver = select_driver(run("lpinfo", "-m"))
        configured = False
        diagnostic_attempt = 0
        last_status = None
        monitor = JobMonitor(lambda message: print(message, flush=True))
        print("Ontwaakcontrole: printdata via USB hoort Auto-Off te beëindigen; "
              "geen apart bevestigd wekcommando. Backendfouten: CUPS retry-job, "
              "interval 60 seconden, limiet 3. Geen fysieke afdrukgarantie.", flush=True)
        print(f"USB-compatibiliteit: usb_unidir={options.get('usb_unidir', True)}; "
              f"debug_logging={options.get('debug_logging', False)}. "
              "Unidirectioneel versturen is geen apart wekcommando.", flush=True)
        while not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("Een printserverdienst is gestopt; herstart de app")
            if not configured:
                try:
                    uri = options.get("device_uri")
                    devices = ""
                    if not uri:
                        devices = run("lpinfo", "-v")
                        uri = select_device(devices)
                    if uri:
                        name = options["printer_name"]
                        # Do not re-enable a deliberately paused queue at every restart.
                        existing = subprocess.run(["lpstat", "-p", name], capture_output=True).returncode == 0
                        args = ["lpadmin", "-p", name, "-v", uri, "-m", driver,
                                "-D", options["printer_description"],
                                "-o", "printer-is-shared=true", "-o", "printer-error-policy=retry-job",
                                "-o", "PageSize=A4", *usb_options(options)]
                        if not existing:
                            args.append("-E")
                        run(*args)
                        run("lpadmin", "-d", name)
                        Path("/etc/avahi/services/airprint.service").write_text(
                            airprint_xml(name, options["printer_description"]))
                        print(f"Printer gereed: {name}; IPP-poort 631; AirPrint gepubliceerd", flush=True)
                        configured = True
                    else:
                        print("Wacht op HP P1102w via USB; controleer kabel en voeding", flush=True)
                        if diagnostic_attempt % 20 == 0:
                            usb_devices = [line for line in devices.splitlines() if "usb://" in line]
                            print("CUPS USB-apparaten: " + (" | ".join(usb_devices) or "geen"), flush=True)
                            usb = run("lsusb")
                            print("USB-busdiagnose:\n" + (usb.strip() or "geen apparaten"), flush=True)
                        diagnostic_attempt += 1
                except subprocess.SubprocessError:
                    print("USB/CUPS-detectie nog niet gereed; nieuwe poging over 15 seconden", flush=True)
            if configured:
                try:
                    connection = cups.Connection(host="/run/cups/cups.sock")
                    monitor.update(connection, options["printer_name"], time.monotonic(),
                                   usb_present)
                    status = run("lpstat", "-p", options["printer_name"], "-l")
                    jobs = run("lpstat", "-W", "not-completed", "-o", options["printer_name"])
                    snapshot = status.strip() + "\n" + (jobs.strip() or "Geen wachtende printopdrachten")
                    if snapshot != last_status:
                        print("CUPS-wachtrijstatus:\n" + snapshot, flush=True)
                        last_status = snapshot
                except (subprocess.SubprocessError, cups.IPPError, RuntimeError) as error:
                    print("Wachtrijstatus niet beschikbaar: " + str(error), flush=True)
            for _ in range(15):
                if stopping:
                    break
                time.sleep(1)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
