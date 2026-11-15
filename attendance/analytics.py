"""Pure-Python attendance analytics (no Django imports, so it can be unit-tested alone).

Inputs are plain dicts / tuples built by ``services.py``:

  employees   [{"id": 1, "name": "Asha", "department": "Sales"}, ...]
  punches     [(employee_id, naive_local_datetime), ...]
  leaves      [{"employee_id": 1, "start": date, "end": date, "planned": True}, ...]  (approved only)
  adjustments [{"employee_id": 1, "date": date, "check_in": time|None, "check_out": time|None}, ...] (approved only)
  office      {"start_minutes": 600, "grace": 10, "workdays": {0,1,2,3,4,6}}  (weekday: Mon=0 ... Sun=6)
"""
import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta

PRESENT, LATE, LEAVE, ABSENT, OFF = "present", "late", "leave", "absent", "off"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def fmt_minutes(m):
    if m is None:
        return ""
    return "%02d:%02d" % (m // 60, m % 60)


class AttendanceData:
    def __init__(self, employees, punches, leaves, adjustments, office):
        self.employees = list(employees)
        self.office = office
        self.start = int(office.get("start_minutes", 600))
        self.grace = int(office.get("grace", 10))
        self.workdays = set(office.get("workdays", {0, 1, 2, 3, 4, 6}))
        self._ids = {e["id"] for e in self.employees}
        # (emp_id, date) -> [first_minutes, last_minutes]
        self._times = {}
        for emp_id, dt in punches:
            if emp_id not in self._ids:
                continue
            m = dt.hour * 60 + dt.minute
            self._merge(emp_id, dt.date(), m, m)
        for a in adjustments:
            if a["employee_id"] not in self._ids:
                continue
            ci = a.get("check_in")
            co = a.get("check_out")
            ci_m = ci.hour * 60 + ci.minute if ci else None
            co_m = co.hour * 60 + co.minute if co else None
            if ci_m is None and co_m is None:
                continue
            self._merge(a["employee_id"], a["date"], ci_m if ci_m is not None else co_m,
                        co_m if co_m is not None else ci_m)
        self._leaves = defaultdict(list)
        for lv in leaves:
            self._leaves[lv["employee_id"]].append(lv)

    def _merge(self, emp_id, d, first, last):
        cur = self._times.get((emp_id, d))
        if cur is None:
            self._times[(emp_id, d)] = [first, last]
        else:
            cur[0] = min(cur[0], first)
            cur[1] = max(cur[1], last)

    # ---- per employee/day -------------------------------------------------
    def is_workday(self, d):
        return d.weekday() in self.workdays

    def times(self, emp_id, d):
        return self._times.get((emp_id, d))

    def leave_for(self, emp_id, d):
        for lv in self._leaves.get(emp_id, ()):
            if lv["start"] <= d <= lv["end"]:
                return lv
        return None

    def status(self, emp_id, d):
        t = self.times(emp_id, d)
        if t is not None:
            return LATE if t[0] > self.start + self.grace else PRESENT
        if self.leave_for(emp_id, d):
            return LEAVE
        if not self.is_workday(d):
            return OFF
        return ABSENT

    # ---- summaries ---------------------------------------------------------
    def summary(self, d):
        total = len(self.employees)
        c = {PRESENT: 0, LATE: 0, LEAVE: 0, ABSENT: 0, OFF: 0}
        planned = unplanned = 0
        for e in self.employees:
            s = self.status(e["id"], d)
            c[s] += 1
            if s == LEAVE:
                if self.leave_for(e["id"], d).get("planned", True):
                    planned += 1
                else:
                    unplanned += 1
        here = c[PRESENT] + c[LATE]
        expected = total - c[LEAVE] if self.is_workday(d) else 0
        return {
            "total": total,
            "present": here,
            "on_time": c[PRESENT],
            "late": c[LATE],
            "leave": c[LEAVE],
            "leave_planned": planned,
            "leave_unplanned": unplanned,
            "absent": c[ABSENT],
            "off_day": not self.is_workday(d) and here == 0,
            "present_pct": round(100.0 * here / total) if total else 0,
            "late_pct": round(100.0 * c[LATE] / here) if here else 0,
            "expected": expected,
        }

    def trend(self, end, days):
        out = []
        for i in range(days - 1, -1, -1):
            d = end - timedelta(days=i)
            if not self.is_workday(d) and not any(self.times(e["id"], d) for e in self.employees):
                continue
            s = self.summary(d)
            out.append({
                "date": d.isoformat(),
                "label": "%s %d" % (WEEKDAYS[d.weekday()], d.day),
                "on_time": s["on_time"], "late": s["late"],
                "absent": s["absent"], "leave": s["leave"],
            })
        return out

    def department_absence(self, start, end):
        """Absence rate (% of expected workdays missed) per department."""
        agg = defaultdict(lambda: [0, 0])  # dept -> [absent, expected]
        d = start
        while d <= end:
            if self.is_workday(d):
                for e in self.employees:
                    s = self.status(e["id"], d)
                    if s in (PRESENT, LATE, ABSENT):
                        agg[e.get("department") or "Unassigned"][1] += 1
                        if s == ABSENT:
                            agg[e.get("department") or "Unassigned"][0] += 1
            d += timedelta(days=1)
        return [
            {"department": k, "absent": v[0], "expected": v[1],
             "rate": round(100.0 * v[0] / v[1], 1) if v[1] else 0.0}
            for k, v in sorted(agg.items())
        ]

    def tardiness(self, start, end):
        """Late arrivals grouped by weekday."""
        counts = [0] * 7
        d = start
        while d <= end:
            for e in self.employees:
                if self.status(e["id"], d) == LATE:
                    counts[d.weekday()] += 1
            d += timedelta(days=1)
        return [{"label": WEEKDAYS[i], "late": counts[i]} for i in range(7) if i in self.workdays]

    def top_late(self, start, end, limit=5):
        counts = defaultdict(int)
        d = start
        while d <= end:
            for e in self.employees:
                if self.status(e["id"], d) == LATE:
                    counts[e["id"]] += 1
            d += timedelta(days=1)
        names = {e["id"]: e for e in self.employees}
        ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
        return [{"name": names[i]["name"], "department": names[i].get("department", ""), "late": n}
                for i, n in ranked]

    def month_cells(self, year, month, today=None):
        """Calendar weeks (Sunday-first) with a class per day for the teal calendar card."""
        today = today or date.today()
        cal = calendar.Calendar(firstweekday=6)
        weeks = []
        for week in cal.monthdatescalendar(year, month):
            row = []
            for d in week:
                cell = {"day": d.day, "other": d.month != month, "sunday": d.weekday() == 6,
                        "today": d == today, "level": "none", "date": d.isoformat()}
                if not cell["other"] and d <= today and self.is_workday(d):
                    s = self.summary(d)
                    if s["total"] and s["present"] + s["leave"] > 0:
                        pct = s["present_pct"]
                        cell["level"] = "high" if pct >= 90 else "mid" if pct >= 60 else "low"
                    elif s["total"]:
                        cell["level"] = "low"
                row.append(cell)
            weeks.append(row)
        return weeks

    def rows(self, start, end):
        """Flat report rows: one per employee per day (workdays and any day with activity)."""
        out = []
        d = start
        while d <= end:
            for e in self.employees:
                t = self.times(e["id"], d)
                s = self.status(e["id"], d)
                if s == OFF and t is None:
                    continue
                hours = ""
                if t and t[1] > t[0]:
                    hours = "%.2f" % ((t[1] - t[0]) / 60.0)
                out.append({
                    "date": d.isoformat(), "name": e["name"], "department": e.get("department", ""),
                    "check_in": fmt_minutes(t[0]) if t else "",
                    "check_out": fmt_minutes(t[1]) if t and t[1] != t[0] else "",
                    "hours": hours, "status": s,
                })
            d += timedelta(days=1)
        return out


REPORT_HEADERS = ["Date", "Employee", "Department", "Check-in", "Check-out", "Hours", "Status"]


def report_table(rows):
    return [[r["date"], r["name"], r["department"], r["check_in"], r["check_out"], r["hours"],
             r["status"].capitalize()] for r in rows]
