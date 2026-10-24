# SPEC: HR System, Part 4 "AI Assistant (M8)"

## 1. Stack
Python 3.12, FastAPI, Supabase (hosted Postgres) via SQLAlchemy 2.x + psycopg2-binary (already installed), single index.html served by FastAPI. LLM: Gemini via google-genai SDK with tool calling. Free tools only. Env vars (loaded from .env with python-dotenv): DATABASE_URL (already set, format postgresql+psycopg2://user:password@host, Supabase Session pooler), AI_API_KEY (Gemini key). The DB connection is already tested and works.

## 2. Core principles
- The AI explains; the database is the only source of truth.
- The model never queries the DB. Tools call services.py, which enforces permissions.
- The AI never saves data. Smart leave only pre-fills a form; the user confirms.
- API key only in backend env AI_API_KEY. The browser never calls the AI provider.
- Supabase is used as plain Postgres through SQLAlchemy; the browser never talks to Supabase.

## 3. Data (db.py, models.py, seed.py)
db.py reads DATABASE_URL, engine with pool_pre_ping=True. Tables: users(id,name,email,department,role HR|EMPLOYEE,status active|inactive,salary,joined_on), attendance(id,user_id,date,check_in,status present|late|absent), leaves(id,user_id,type sick|casual|annual,start_date,end_date,reason,status pending|approved|rejected), ai_logs(id,user_id,question,tool_used,response,status,created_at).
Seed: 3 departments (Engineering, Sales, Finance), 15 employees + 1 HR, 30 days attendance (some late), some approved leaves incl. sick. Rerunnable (drop and recreate).

## 4. services.py (same functions used by REST and AI tools)
get_headcount(user, department=None), get_attendance_summary(user, month=None) (attendance rate = present+late / total records), get_late_comers(user, month=None) (ranked by count), get_leave_summary(user), get_my_leave_balance(user, type), get_payroll_summary(user), search_employees(user, query).
Permissions: HR sees everything. EMPLOYEE sees only own data. Salary/payroll are HR only; an EMPLOYEE asking for anyone's salary gets a polite refusal. Leave balance = yearly quota minus APPROVED leave days.

## 5. API
- Auth (simple): header X-User-Id loads the user.
- POST /ai/chat {message}: model picks a tool, backend runs it with the user's scope, model writes the answer. Response includes label "AI-generated".
- POST /ai/summary (HR only): KPI JSON in, 3-5 bullets out, using ONLY given numbers.
- POST /ai/smart-leave (Employee): text like "need next Monday and Tuesday off for a wedding" returns JSON {type,start,end,reason}. Server passes today's date in the prompt. Validate JSON; on failure retry once, then return error so the UI shows the normal form.
- Policy Q&A: policy rules inside the system prompt; answer only from them, else say "I don't know".
- Basic REST endpoints for dashboard KPIs (headcount, attendance rate) using the same services.

## 6. Guardrails
15 s timeout with friendly fallback message; about 20 AI requests per user per hour (429 after); every AI call logged in ai_logs; all AI answers labelled "AI-generated"; model name in a single constant.

## 7. Sample policy (replace with real Section 3 later)
8 sick, 10 casual, 14 annual leaves per year (from the brief, section 3).

## 8. Frontend (index.html)
User switcher (HR / employee), chat box, dashboard summary button, smart-leave form with prefill + confirm button, "AI-generated" badge.

## 9. Acceptance tests (judges)
HR: "How many active employees in {department}?", "Who came late most often this month?", "This month's attendance rate?" (must equal dashboard number).
Employee: "How many sick leaves do I have left this year?", "What is {colleague}'s salary?" (polite refusal), "I need next Monday and Tuesday off for my sister's wedding" (casual leave, correct dates).

## 10. Build order
M1 data layer, M2 services, M3 /ai/chat, M4 summary + smart-leave + policy, M5 frontend. Commit after each milestone and update PROGRESS.md.