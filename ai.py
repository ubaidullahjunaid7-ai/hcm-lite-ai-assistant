import os, json, time, datetime
import inspect
from dotenv import load_dotenv
from google import genai
from google.genai import types
from skills.loader import load_skills, skills_for_user

load_dotenv()
MODEL = os.getenv("AI_MODEL", "gemini-3.5-flash-lite")
client = genai.Client(
    api_key=os.getenv("AI_API_KEY"),
    http_options=types.HttpOptions(timeout=15000),
)
FALLBACK = "The AI assistant is temporarily unavailable. Please try again later."
SKILLS = load_skills()

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


def available_skills(user):
    return skills_for_user(SKILLS, user)


def make_tools(db, user, used):
    tools = []
    for skill in available_skills(user):
        def execute_skill(_skill=skill, **kwargs):
            used.append(_skill["NAME"])
            return _clean(_skill["run"](user, db=db, **kwargs))

        parameters = []
        annotations = {}
        for name, details in skill.get("PARAMETERS", {}).items():
            parameter_type, required = details
            parameters.append(inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=inspect.Parameter.empty if required else None,
                annotation=parameter_type,
            ))
            annotations[name] = parameter_type
        execute_skill.__name__ = skill["NAME"]
        execute_skill.__qualname__ = skill["NAME"]
        execute_skill.__doc__ = skill["DESCRIPTION"]
        execute_skill.__signature__ = inspect.Signature(
            parameters,
            return_annotation=dict,
        )
        execute_skill.__annotations__ = {**annotations, "return": dict}
        tools.append(execute_skill)
    return tools


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


def chat(db, user, message: str, history=None) -> dict:
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
    contents = [
        types.Content(
            role="model" if item["role"] == "assistant" else "user",
            parts=[types.Part(text=item["content"])],
        )
        for item in (history or [])[-4:]
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
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