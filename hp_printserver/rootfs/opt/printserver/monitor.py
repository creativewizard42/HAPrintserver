"""Read-only IPP monitoring. CUPS alone owns transmission and retries."""
import json


class JobMonitor:
    def __init__(self, log=print):
        self.log = log
        self.jobs = {}
        self.last_printer = None
        self.last_heartbeat = None

    def update(self, connection, name, now, probe):
        printer = connection.getPrinterAttributes(name)
        summary = {key: printer.get(key) for key in (
            "printer-state", "printer-state-reasons", "printer-state-message")}
        if summary != self.last_printer:
            self.log("IPP-printerstatus: " + json.dumps(summary, ensure_ascii=False))
            self.last_printer = summary
        active = connection.getJobs(which_jobs="not-completed", my_jobs=False,
                                    requested_attributes=[
                                        "job-id", "job-printer-uri", "job-state",
                                        "job-state-reasons", "job-state-message",
                                        "job-impressions-completed", "usb-unidir", "usb-no-reattach"])
        # Some servers return only a minimal job list. Do not silently discard
        # jobs when their queue URI is absent from Get-Jobs.
        active = {job: (connection.getJobAttributes(job)
                        if "job-printer-uri" not in attributes else attributes)
                  for job, attributes in active.items()}
        active = {job: attributes for job, attributes in active.items()
                  if attributes.get("job-printer-uri", "").endswith("/printers/" + name)}
        if self.last_heartbeat is None or now - self.last_heartbeat >= 60:
            effective = {job: {key: attrs.get(key, "niet ingesteld")
                               for key in ("usb-unidir", "usb-no-reattach")}
                         for job, attrs in active.items()}
            self.log(f"IPP-monitor actief: {len(active)} openstaande jobs voor {name}; "
                     f"USB-opties per job={effective}; "
                     "printerstatus is geen bevestiging van fysiek ontwaken.")
            self.last_heartbeat = now
        for job, attrs in active.items():
            state = {key: attrs.get(key) for key in (
                "job-state", "job-state-reasons", "job-state-message", "job-impressions-completed",
                "usb-unidir", "usb-no-reattach")}
            record = self.jobs.setdefault(job, {"since": now, "checks": 0, "state": None})
            if state != record["state"]:
                self.log(f"Job {job}: " + json.dumps(state, ensure_ascii=False))
                old_pages = (record["state"] or {}).get("job-impressions-completed") or 0
                if (state.get("job-impressions-completed") or 0) > old_pages:
                    record["since"] = now
                record["state"] = state
            # Do not release held jobs or override pauses, paper faults or filters.
            if record["checks"] < 3 and now - record["since"] >= (60, 120, 240)[record["checks"]]:
                record["checks"] += 1
                reachable = probe(printer.get("device-uri", ""))
                self.log(f"Job {job}: voortgangscontrole {record['checks']}/3; "
                         f"USB-busaanwezig={reachable}; alleen sysfs, geen interfaceclaim; "
                         "standby/ontwaken niet rechtstreeks meetbaar. "
                         "CUPS verstuurt de oorspronkelijke job en herprobeert gemelde backendfouten; "
                         "geen nieuwe kopie ingediend.")
                if record["checks"] == 3:
                    self.log(f"Job {job}: blijft openstaan; controleer printer, papier en IPP-foutreden. "
                             "Geen automatische USB-reset of extra afdruk.")
        for job in set(self.jobs) - set(active):
            attrs = connection.getJobAttributes(job)
            state = attrs.get("job-state")
            self.log(f"Job {job}: eindstatus={state}; redenen={attrs.get('job-state-reasons')}; "
                     + ("CUPS meldt voltooid; fysieke afdruk en ontwaken niet onafhankelijk bevestigd."
                        if state == 9 else "Geen bevestiging van geslaagde afdruk."))
            del self.jobs[job]
