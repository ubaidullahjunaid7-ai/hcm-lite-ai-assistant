import os, json, time, datetime
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types
import services

load_dotenv()
MODEL = os.getenv("AI_MODEL", "gemini-3.5-flash-lite")
client = genai.Client(
    api_key=os.getenv("AI_API_KEY"),
    http_options=types.HttpOptions(timeout=15000),
)
FALLBACK = "The AI assistant is temporarily unavailable. Please try again later."

_hits = {}


def rate_ok(user_id: int) -> bool:
    now = time.time()
    h = [t for t in _hits.get(user_id, []) if now - t < 3600]
    if len(h) >= 20:
        _hits[user_id] = h
        return False
    h.append(now)
    _hits[user_id] = h
    return True


def _clean(x):
    return {"result": json.loads(json.dumps(x, default=str))}


def make_tools(db, user, used):
    def get_headcount(department: Optional[str] = None) -> dict:
        """Number of employees (active and total). Optional department: Engineering, Sales or Finance."""
        used.append("get_headcount")
        return _clean(services.get_headcount(db, user, department))

    def get_attendance_summary(month: Optional[str] = None) -> dict:
        """Attendance summary and attendance rate. month format YYYY-MM; omit for current month."""
        used.append("get_attendance_summary")
        return _clean(services.get_attendance_summary(db, user, month))

    def get_late_comers(month: Optional[str] = None) -> dict:
        """Employees ranked by number of late arrivals. month format YYYY-MM; omit for current month."""
        used.append("get_late_comers")
        return _clean(services.get_late_comers(db, user, month))

    def get_leave_summary() -> dict:
        """Summary of leave requests (pending, approved, rejected)."""
        used.append("get_leave_summary")
        return _clean(services.get_leave_summary(db, user))

    def get_my_leave_balance(leave_type: str) -> dict:
        """Remaining leave balance of the current user. leave_type must be sick, casual or annual."""
        used.append("get_my_leave_balance")
        return _clean(services.get_my_leave_balance(db, user, leave_type))

    def get_payroll_summary() -> dict:
        """Payroll and salary summary. Only HR is allowed."""
        used.append("get_payroll_summary")
        return _clean(services.get_payroll_summary(db, user))

    def search_employees(query: str) -> dict:
        """Search employees by name or department."""
        used.append("search_employees")
        return _clean(services.search_employees(db, user, query))

    return [get_headcount, get_attendance_summary, get_late_comers,
            get_leave_summary, get_my_leave_balance, get_payroll_summary,
            search_employees]


POLICY = """Company policy (the ONLY policy facts you know):
- Office start 09:00, grace 15 minutes. Late means check-in after 09:15.
- Half day: worked less than 5 hours. Weekend is Saturday and Sunday.
- One attendance record per employee per day (a second check-in is rejected).
- Absent: no attendance record and no approved leave. Missing checkout: no check-out.
- Leave quota per year: 14 annual, 8 sick, 10 casual. Unpaid leave is unlimited.
- Leave counts working days only (weekends and public holidays are skipped).
- Leave that overlaps another leave or exceeds the balance is rejected.
- Leave balance = quota minus approved leave days this year.
- Payroll: gross = 1.5 x basic salary. Deductions for absent days, unpaid leave and 0.5 day per half day.
- Only HR can see salaries and payroll; employees only see their own data."""


def chat(db, user, message: str) -> dict:
    today = datetime.date.today()
    who = f"{getattr(user, 'name', '')} (role: {getattr(user, 'role', '')})"
    system = f"""You are the HR assistant. Today is {today.strftime('%A')} {today.isoformat()}.
Current user: {who}.
Rules:
- For any data question (headcount, attendance, late comers, leaves, salary, employees) you MUST call a tool. Never guess numbers.
- Use only numbers returned by tools. If a tool returns denied/error, politely explain the user is not allowed to see that.
- For policy questions answer only from the policy below. If the answer is not there, say "I don't know".
- Keep answers short and clear.
{POLICY}"""
    used = []
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=make_tools(db, user, used),
                temperature=0.2,
            ),
        )
        text = resp.text
        if not text:
            raise ValueError("empty response")
        return {"answer": text, "ok": True, "tools": used}
    except Exception as e:
        print("AI ERROR:", repr(e))
        return {"answer": FALLBACK, "ok": False, "tools": used}


def summarize(kpi: dict) -> dict:
    system = (
        "You are an HR analyst. You receive KPI data as JSON. "
        "Write 3 to 5 short insight bullets. Use ONLY numbers that appear in the JSON. "
        "Never invent or estimate numbers. One bullet per line, each starting with '- '."
    )
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=json.dumps(kpi, default=str),
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.2),
        )
        lines = [l.strip().lstrip("-•* ").strip() for l in (resp.text or "").splitlines() if l.strip()]
        bullets = lines[:5]
        if not bullets:
            raise ValueError("empty summary")
        return {"bullets": bullets, "ok": True}
    except Exception as e:
        print("AI ERROR:", repr(e))
        return {"bullets": [], "ok": False}


VALID_TYPES = {"sick", "casual", "annual", "unpaid"}


def _next_week_dates(today):
    monday = today - datetime.timedelta(days=today.weekday())
    nxt = monday + datetime.timedelta(days=7)
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return {names[i]: (nxt + datetime.timedelta(days=i)).isoformat() for i in range(7)}


def _check_leave(d):
    if not isinstance(d, dict):
        return None
    t = str(d.get("type", "")).lower().strip()
    if t not in VALID_TYPES:
        return None
    try:
        s = datetime.date.fromisoformat(str(d.get("start")))
        e = datetime.date.fromisoformat(str(d.get("end")))
    except ValueError:
        return None
    if e < s:
        return None
    reason = str(d.get("reason", "")).strip()[:200]
    return {"type": t, "start": s.isoformat(), "end": e.isoformat(), "reason": reason}


def smart_leave(text: str) -> dict:
    today = datetime.date.today()
    table = "\n".join(f"- next {k}: {v}" for k, v in _next_week_dates(today).items())
    tomorrow = (today + datetime.timedelta(days=1)).isoformat()
    system = f"""Convert the employee's leave request into JSON with exactly these keys: type, start, end, reason.
Today is {today.strftime('%A')} {today.isoformat()}. Tomorrow is {tomorrow}.
type must be one of: sick, casual, annual, unpaid.
Use casual for weddings, family events and personal errands; sick for illness or doctor visits; annual for vacations or trips.
start and end are ISO dates (YYYY-MM-DD), inclusive. For one day, start equals end.
Dates for "next <weekday>" (the weekday in next week), copy them exactly:
{table}
reason is a short phrase from the request.
If the text is NOT a request for time off (for example a greeting or a question), reply exactly {{"error": "not a leave request"}} and nothing else.
Never invent a leave request. Reply with JSON only."""
    for _ in range(2):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            raw = resp.text or ""
            print("SMART RAW:", raw)
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                parsed = parsed[0]
            if isinstance(parsed, dict) and "error" in parsed:
                return {"ok": False}
            data = _check_leave(parsed)
            if data:
                return {"ok": True, "leave": data}
        except Exception as e:
            print("AI ERROR:", repr(e))
    return {"ok": False}