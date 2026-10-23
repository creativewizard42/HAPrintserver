import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    "monitor", Path(__file__).resolve().parents[1] / "hp_printserver/rootfs/opt/printserver/monitor.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.monitor = module.JobMonitor(self.logs.append)
        self.connection = Mock()
        self.connection.getPrinterAttributes.return_value = {
            "device-uri": "usb://HP/P1102w?serial=selected", "printer-state": 4,
            "printer-state-reasons": ["connecting-to-device"]}
        self.connection.getJobs.return_value = {
            7: {"job-printer-uri": "ipp://localhost/printers/HP_P1102w", "job-state": 5}}
        self.probe = Mock(return_value=False)

    def update(self, now):
        self.monitor.update(self.connection, "HP_P1102w", now, self.probe)

    def test_stalled_job_probes_are_bounded_and_do_not_resubmit(self):
        for now in [0, 59, 60, 119, 120, 240, 500, 1000]:
            self.update(now)
        self.assertEqual(self.probe.call_count, 3)
        self.probe.assert_called_with("usb://HP/P1102w?serial=selected")
        self.assertEqual({call[0] for call in self.connection.method_calls},
                         {"getPrinterAttributes", "getJobs"})
        self.assertTrue(any("blijft openstaan" in line for line in self.logs))

    def test_completion_logs_no_physical_guarantee(self):
        self.update(0)
        self.connection.getJobs.return_value = {}
        self.connection.getJobAttributes.return_value = {"job-state": 9}
        self.update(15)
        self.assertTrue(any("niet onafhankelijk bevestigd" in line for line in self.logs))

    def test_other_queue_is_ignored(self):
        self.connection.getJobs.return_value[7]["job-printer-uri"] = "ipp://localhost/printers/Other"
        self.update(0)
        self.update(300)
        self.probe.assert_not_called()

    def test_minimal_job_list_fetches_queue_and_keeps_monitoring(self):
        self.connection.getJobs.return_value = {7: {"job-state": 5}}
        self.connection.getJobAttributes.return_value = {
            "job-printer-uri": "ipp://localhost/printers/HP_P1102w", "job-state": 5}
        self.update(0)
        self.update(60)
        self.probe.assert_called_once()
        self.assertIn("job-printer-uri",
                      self.connection.getJobs.call_args.kwargs["requested_attributes"])

    def test_heartbeat_continues_when_no_jobs_are_reported(self):
        self.connection.getJobs.return_value = {}
        for now in (0, 15, 60, 120):
            self.update(now)
        self.assertEqual(sum("IPP-monitor actief:" in line for line in self.logs), 3)
        self.probe.assert_not_called()

    def test_held_job_is_not_released(self):
        self.connection.getJobs.return_value[7]["job-state"] = 4
        self.update(0)
        self.update(60)
        self.connection.releaseJob.assert_not_called()


if __name__ == "__main__":
    unittest.main()
