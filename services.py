from datetime import date, timedelta
from sqlalchemy import func, or_
import models

QUOTA = {"sick": 8, "casual": 10, "annual": 14}


def _denied(msg="You are not allowed to view this information."):
    return {"error": msg, "denied": True}


def _is_hr(user):
    return user.role == "HR"


def _month_range(month=None):
    if month:
        y, m = map(int, month.split("-"))
    else:
        t = date.today()
        y, m = t.year, t.month
    start = date(y, m, 1)
    end = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    return start, end


def _emp_dict(u):
    return {"id": u.id, "name": u.name, "department": u.department,
            "role": u.role, "status": u.status, "salary": u.salary}


def get_headcount(db, user, department=None):
    if not _is_hr(user):
        return _denied("Headcount is available to HR only.")
    q = db.query(func.count(models.User.id)).filter(models.User.status == "active")
    if department:
        q = q.filter(func.lower(models.User.department) == department.lower())
    return {"department": department or "all", "active_employees": q.scalar()}


def get_department_report(db, user):
    if not _is_hr(user):
        return _denied("Department reports are available to HR only.")
    rows = (db.query(models.User.department, func.count(models.User.id))
            .filter(models.User.status == "active")
            .group_by(models.User.department)
            .order_by(models.User.department).all())
    return {"departments": [
        {"department": department or "Unassigned", "active_employees": count}
        for department, count in rows
    ]}


def get_team_directory(db, user, department=None):
    requested_department = (department or "").strip()
    if not _is_hr(user):
        own_department = getattr(user, "department", None)
        if not own_department:
            return _denied("Your department is not set.")
        if requested_department and requested_department.lower() != (own_department or "").lower():
            return _denied("You can only view your own department.")
        requested_department = own_department

    q = db.query(models.User).filter(models.User.status == "active")
    if requested_department:
        q = q.filter(func.lower(models.User.department) == requested_department.lower())
    rows = q.order_by(models.User.name).all()
    return {"employees": [
        {
            "name": employee.name,
            "department": employee.department,
            "job_title": getattr(employee, "job_title", None) or "Not specified",
        }
        for employee in rows
    ]}


def get_attendance_trend(db, user):
    if not _is_hr(user):
        return _denied("Attendance trends are available to HR only.")

    today = date.today()
    start = today - timedelta(days=6)
    rows = (db.query(models.Attendance.date, models.Attendance.status, func.count(models.Attendance.id))
            .filter(models.Attendance.date >= start, models.Attendance.date <= today)
            .group_by(models.Attendance.date, models.Attendance.status)
            .order_by(models.Attendance.date).all())

    counts_by_date = {}
    for attendance_date, status, count in rows:
        counts = counts_by_date.setdefault(attendance_date, {})
        counts[status] = count

    days = []
    total_records = 0
    total_attended = 0
    for offset in range(7):
        day = start + timedelta(days=offset)
        counts = counts_by_date.get(day, {})
        total = sum(counts.values())
        attended = counts.get("present", 0) + counts.get("late", 0)
        total_records += total
        total_attended += attended
        days.append({
            "date": day.isoformat(),
            "attendance_rate_percent": round(attended / total * 100, 1) if total else 0.0,
        })

    return {
        "start_date": start.isoformat(),
        "end_date": today.isoformat(),
        "attendance_rate_percent": round(total_attended / total_records * 100, 1) if total_records else 0.0,
        "days": days,
    }


def get_attendance_summary(db, user, month=None):
    start, end = _month_range(month)
    q = db.query(models.Attendance.status, func.count(models.Attendance.id)).filter(
        models.Attendance.date >= start, models.Attendance.date < end)
    if not _is_hr(user):
        q = q.filter(models.Attendance.user_id == user.id)
    counts = dict(q.group_by(models.Attendance.status).all())
    total = sum(counts.values())
    attended = counts.get("present", 0) + counts.get("late", 0)
    rate = round(attended / total * 100, 1) if total else 0.0
    return {"month": start.strftime("%Y-%m"),
            "scope": "company" if _is_hr(user) else "own",
            "present": counts.get("present", 0), "late": counts.get("late", 0),
            "absent": counts.get("absent", 0), "total_records": total,
            "attendance_rate_percent": rate}


def get_late_comers(db, user, month=None):
    start, end = _month_range(month)
    cnt = func.count(models.Attendance.id)
    q = (db.query(models.User.name, cnt)
         .join(models.Attendance, models.Attendance.user_id == models.User.id)
         .filter(models.Attendance.status == "late",
                 models.Attendance.date >= start, models.Attendance.date < end))
    if not _is_hr(user):
        q = q.filter(models.User.id == user.id)
    rows = q.group_by(models.User.id, models.User.name).order_by(cnt.desc(), models.User.name).limit(5).all()
    return {"month": start.strftime("%Y-%m"),
            "late_comers": [{"name": n, "late_days": c} for n, c in rows]}


def get_leave_summary(db, user):
    q = db.query(models.Leave.type, models.Leave.status, func.count(models.Leave.id))
    if not _is_hr(user):
        q = q.filter(models.Leave.user_id == user.id)
    rows = q.group_by(models.Leave.type, models.Leave.status).all()
    return {"scope": "company" if _is_hr(user) else "own",
            "leaves": [{"type": t, "status": s, "count": c} for t, s, c in rows]}


def get_my_leave_balance(db, user, leave_type):
    lt = (leave_type or "").lower()
    if lt not in QUOTA:
        return {"error": "Unknown leave type. Use one of: " + ", ".join(QUOTA)}
    year = date.today().year
    rows = db.query(models.Leave).filter(
        models.Leave.user_id == user.id, models.Leave.type == lt,
        models.Leave.status == "approved",
        models.Leave.start_date >= date(year, 1, 1),
        models.Leave.start_date <= date(year, 12, 31)).all()
    used = sum((l.end_date - l.start_date).days + 1 for l in rows)
    return {"type": lt, "year": year, "yearly_quota": QUOTA[lt],
            "used_days": used, "remaining_days": max(QUOTA[lt] - used, 0)}


def get_payroll_summary(db, user):
    if not _is_hr(user):
        return _denied("Payroll information is available to HR only.")
    rows = (db.query(models.User.department, func.count(models.User.id), func.sum(models.User.salary))
            .filter(models.User.status == "active").group_by(models.User.department).all())
    return {"total_payroll": float(sum(r[2] or 0 for r in rows)),
            "by_department": [{"department": d, "employees": c, "total_salary": float(s or 0)}
                              for d, c, s in rows]}


def search_employees(db, user, query):
    q = (query or "").strip().lower()
    if not _is_hr(user):
        me = user.name.lower()
        if q and (q in me or me in q):
            return {"results": [_emp_dict(user)]}
        return _denied("You can only view your own information.")
    rows = (db.query(models.User)
            .filter(or_(func.lower(models.User.name).like(f"%{q}%"),
                        func.lower(models.User.department).like(f"%{q}%")))
            .limit(10).all())
    return {"results": [_emp_dict(u) for u in rows]}