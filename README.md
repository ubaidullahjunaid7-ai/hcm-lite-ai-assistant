# HCM Lite: M8 AI Assistant (Part 4)

Saylani Hackathon "HCM Lite". Solo submission for **Part 4 = M8 AI Assistant** (features #19 to #22), built on top of a small HR backend (users, attendance, leaves) so the AI features can run on real data.

## Stack
- Python 3.12, FastAPI, uvicorn
- SQLAlchemy 2.x + PostgreSQL (Supabase, free tier)
- Google Gemini via `google-genai` (model set by `AI_MODEL`, default `gemini-3.5-flash-lite`)
- Frontend: single `index.html` (plain HTML + fetch), served by FastAPI at `/`

## AI features
| # | Feature | Endpoint |
|---|---------|----------|
| 19 | Chat with tools (model picks a tool, backend runs it with the user's permissions, model writes the answer) | `POST /ai/chat` |
| 20 | Dashboard summary (HR/Admin only, 3-5 bullets from KPI numbers only) | `POST /ai/summary` |
| 21 | Smart leave (sentence to JSON `{type,start,end,reason}`, pre-fills a form; AI never saves) | `POST /ai/smart-leave` |
| 22 | Policy Q&A (rules in system prompt; otherwise "I don't know") | via `POST /ai/chat` |
| — | Recent AI activity logs (HR only, latest 50 requests) | `GET /ai/logs` |

Skills include `get_headcount`, `get_attendance_summary`, `get_late_comers`, `get_leave_summary`, `get_my_leave_balance`, `get_payroll_summary`, `search_employees`, and the plugins `department_report`, `leave_policy_info`, `holiday_calendar`, `team_directory`, and `attendance_trend`.

## Guardrails
- API key only in backend environment variables; the browser never calls the AI provider.
- Tools reuse the same service functions with permission checks: HR sees everything, an Employee sees only their own data, salary/payroll is HR only (polite refusal otherwise).
- 15 second timeout on AI calls.
- Rate limit about 20 requests per user per hour.
- Every AI call is logged in the `ai_logs` table.
- Chat accepts up to four previous user/assistant messages for follow-up questions.
- `GET /ai/logs` is HR-only and returns at most the 50 most recent log entries; employees receive HTTP 403.
- Answers are labelled "[AI-generated]".
- Smart leave validates the JSON, retries once, then falls back to the manual form.

## How to run locally
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then fill in your own values
python seed.py              # drops and recreates tables, adds demo data
uvicorn main:app --reload
```
Open http://127.0.0.1:8000/ (Swagger: http://127.0.0.1:8000/docs).

## How to set the AI key
Create a free key at https://aistudio.google.com/ and put it in `.env` (or the host's environment settings):
```
AI_API_KEY=your_gemini_api_key_here
AI_MODEL=gemini-3.5-flash-lite
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres
```
If the free quota runs out or the model gives 404, set `AI_MODEL=gemini-3.1-flash-lite`. Never commit `.env`.

## How to create the first Admin
`python seed.py` creates the first admin: **user id 1, "HR Admin", role HR**. In the page, choose "HR Admin" in the user dropdown. Employees are ids 2 to 16 (id 16 is inactive).

## Demo questions
- HR: "How many active employees in Engineering?" (5), "Who came late most often this month?" (Sana Javed, 5), "What is this month's attendance rate?" (92.9%, same as `/kpi`)
- Employee (e.g. Sara Khan): "How many sick leaves do I have left this year?" (6), "What is Ali Raza's salary?" (polite refusal), "I need next Monday and Tuesday off for my sister's wedding" (pre-fills casual leave with correct dates)
- Policy: "How many casual leaves per year?" (10), "What is the dress code?" ("I don't know")

## What is done
- #19 chat with 7 tools and permission checks
- #20 dashboard summary (HR/Admin only, 403 for others)
- #21 smart leave pre-fill with validation, one retry and manual fallback
- #22 policy Q&A from Section 3 of the brief
- Logging, rate limit, timeout, AI-generated label

## What is NOT done (honest list)
- Auth is a demo `X-User-Id` header, not JWT/login. A real system would use JWT.
- No separate Admin role: the seeded HR Admin has role HR.
- Leave "Confirm" in the page does not save anything (the Leave module belongs to other teammates). Smart leave does not check overlaps or balance.
- Rate limit is in memory (resets on restart).
- Free Gemini quota can run out.
- Data is fake demo data from `seed.py`.

## Skills and Plugins

Each Python module in `skills/` is loaded automatically when the application starts. The seven existing chat tools are implemented as skills, and `department_report.py` is an HR-only sample plugin.

```text
skills/
  __init__.py
  loader.py
  get_headcount.py
  get_attendance_summary.py
  get_late_comers.py
  get_leave_summary.py
  get_my_leave_balance.py
  get_payroll_summary.py
  search_employees.py
  department_report.py
  leave_policy_info.py
  holiday_calendar.py
  team_directory.py
  attendance_trend.py
```

Every skill module defines:

- `NAME`: unique tool name (lowercase letters, digits, and underscores).
- `DESCRIPTION`: text used to describe the tool to the AI and in the Skills panel.
- `ROLES`: allowed role names, such as `["HR"]` or `["HR", "EMPLOYEE"]`.
- `run(user, **kwargs)`: invokes an existing permission-checked function in `services.py`; skills must not query the database directly.

Optional `PARAMETERS` metadata declares AI arguments as a mapping of argument names to `(Python type, required)` pairs, for example `{"department": (str, False)}`. A skill with no arguments can omit it. Runtime tool declarations are generated from this metadata and the skill description. Roles are used both to filter `/skills` and to restrict which tools are available to the AI.

To add a plugin, create one `.py` file in `skills/` with the `NAME`, `DESCRIPTION`, `ROLES`, and `run(user, **kwargs)` definitions shown below, then restart the application. The loader discovers the module automatically without edits to `loader.py`, `ai.py`, or `main.py`. If the plugin needs database data, add or reuse a permission-checked function in `services.py`; keep database access out of the skill module.

```python
import services

NAME = "department_report"
DESCRIPTION = "Active employee headcount grouped by department."
ROLES = ["HR"]

def run(user, **kwargs):
    return services.get_department_report(kwargs["db"], user)
```

`GET /skills` requires the `X-User-Id` header and returns the skill names, descriptions, and role lists allowed for that user. The UI refreshes this list when the selected demo user changes.

## UI

The frontend is plain HTML, CSS, and JavaScript with no external libraries. `/` is a responsive single-page assistant with a demo user selector, role badge, role-based navigation, labelled chat bubbles, available skill cards, smart leave prefill/review, and an HR-only KPI summary action. Role-specific clickable example-question chips help users start a chat; the last four user/assistant messages are sent as context for follow-up questions. HR navigation also includes an AI Logs section for the most recent 50 requests. HR users can open the separately served `/dashboard` page; employees see the Smart Leave section instead.

Smart Leave only prefills a form for review. Confirming the details in this demo does not save a leave request; the AI never writes to the database.