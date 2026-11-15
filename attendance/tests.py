"""Plain unittest tests for the pure-Python analytics/report code.

Run with:  python manage.py test      (or)   python -m unittest attendance.tests
"""
import unittest
from datetime import date, datetime, time

from . import analytics, reports

OFFICE = {"start_minutes": 600, "grace": 10, "workdays": {0, 1, 2, 3, 4, 6}}
EMPS = [
    {"id": 1, "name": "Asha", "department": "Sales"},
    {"id": 2, "name": "Bikash", "department": "Sales"},
    {"id": 3, "name": "Chitra", "department": "IT"},
    {"id": 4, "name": "Dipesh", "department": "IT"},
]
MON = date(2026, 11, 16)  # a Monday
SAT = date(2026, 11, 14)


def make():
    punches = [
        (1, datetime(2026, 11, 16, 9, 55)),
        (1, datetime(2026, 11, 16, 17, 30)),
        (2, datetime(2026, 11, 16, 10, 25)),   # late
        (999, datetime(2026, 11, 16, 9, 0)),   # unknown employee ignored
    ]
    leaves = [{"employee_id": 3, "start": MON, "end": MON, "planned": False}]
    return analytics.AttendanceData(EMPS, punches, leaves, [], OFFICE)


class AnalyticsTests(unittest.TestCase):
    def test_status(self):
        a = make()
        self.assertEqual(a.status(1, MON), "present")
        self.assertEqual(a.status(2, MON), "late")
        self.assertEqual(a.status(3, MON), "leave")
        self.assertEqual(a.status(4, MON), "absent")
        self.assertEqual(a.status(4, SAT), "off")

    def test_grace_boundary(self):
        a = analytics.AttendanceData(
            EMPS, [(1, datetime(2026, 11, 16, 10, 10)), (2, datetime(2026, 11, 16, 10, 11))], [], [], OFFICE)
        self.assertEqual(a.status(1, MON), "present")
        self.assertEqual(a.status(2, MON), "late")

    def test_summary(self):
        s = make().summary(MON)
        self.assertEqual((s["total"], s["present"], s["on_time"], s["late"]), (4, 2, 1, 1))
        self.assertEqual((s["leave"], s["leave_unplanned"], s["leave_planned"], s["absent"]), (1, 1, 0, 1))
        self.assertEqual(s["present_pct"], 50)

    def test_adjustment_counts(self):
        adj = [{"employee_id": 4, "date": MON, "check_in": time(9, 30), "check_out": time(18, 0)}]
        a = analytics.AttendanceData(EMPS, [], [], adj, OFFICE)
        self.assertEqual(a.status(4, MON), "present")

    def test_department_absence(self):
        res = {r["department"]: r for r in make().department_absence(MON, MON)}
        self.assertEqual(res["IT"]["absent"], 1)
        self.assertEqual(res["IT"]["expected"], 1)   # Chitra on leave is excluded
        self.assertEqual(res["Sales"]["rate"], 0.0)

    def test_trend_and_tardiness(self):
        a = make()
        t = a.trend(MON, 7)
        self.assertEqual(t[-1]["late"], 1)
        self.assertNotIn("Sat", [x["label"].split()[0] for x in t])
        self.assertEqual(sum(x["late"] for x in a.tardiness(MON, MON)), 1)
        self.assertEqual(a.top_late(MON, MON)[0]["name"], "Bikash")

    def test_month_cells(self):
        weeks = make().month_cells(2026, 11, today=MON)
        self.assertEqual(len(weeks[0]), 7)
        flat = [c for w in weeks for c in w if not c["other"]]
        self.assertEqual(len(flat), 30)
        self.assertTrue(all(c["sunday"] for w in weeks for c in [w[0]]))

    def test_rows(self):
        rows = make().rows(MON, MON)
        self.assertEqual(len(rows), 4)
        first = [r for r in rows if r["name"] == "Asha"][0]
        self.assertEqual((first["check_in"], first["check_out"], first["hours"]), ("09:55", "17:30", "7.58"))


class ReportTests(unittest.TestCase):
    ROWS = [["2026-11-16", "=cmd()", "Sales", "09:55", "17:30", "7.58", "Present"],
            ["2026-11-16", "सुशान्त", "IT", "", "", "", "Absent"]]

    def test_csv_guard(self):
        data = reports.to_csv(analytics.REPORT_HEADERS, self.ROWS).decode("utf-8-sig")
        self.assertIn("'=cmd()", data)
        self.assertTrue(data.startswith("Date,Employee"))

    def test_xlsx(self):
        data = reports.to_xlsx(analytics.REPORT_HEADERS, self.ROWS)
        self.assertEqual(data[:2], b"PK")

    def test_pdf(self):
        data = reports.to_pdf(analytics.REPORT_HEADERS, self.ROWS)
        self.assertEqual(data[:4], b"%PDF")
        self.assertEqual(reports.to_pdf(analytics.REPORT_HEADERS, [])[:4], b"%PDF")


if __name__ == "__main__":
    unittest.main()
