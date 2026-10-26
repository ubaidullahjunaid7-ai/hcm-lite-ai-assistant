import json
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from typing import Literal

import models, services, ai
from db import get_db

app = FastAPI(title="HR AI Assistant")


def current_user(x_user_id: int = Header(...), db: Session = Depends(get_db)):
    user = db.get(models.User, x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=500)


class ChatIn(BaseModel):
    message: str
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=4)


def log_ai(db, user, message, result, endpoint="chat"):
    try:
        cols = {c.name for c in models.AILog.__table__.columns}
        answer = result.get("answer")
        tools = ",".join(result.get("tools", []))
        vals = {
            "user_id": user.id,
            "endpoint": endpoint,
            "question": message, "prompt": message, "message": message, "request": message,
            "answer": answer, "response": answer,
            "tools": tools, "tools_used": tools, "tool_used": tools,
        }
        row = models.AILog(**{k: v for k, v in vals.items() if k in cols})
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        print("LOG ERROR:", repr(e))


@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    return [
        {
            "id": u.id,
            "name": getattr(u, "name", None),
            "role": str(getattr(u, "role", "")),
            "department": getattr(u, "department", None),
        }
        for u in db.query(models.User).order_by(models.User.id).all()
    ]


@app.get("/skills")
def list_skills(user=Depends(current_user)):
    return [
        {
            "name": skill["NAME"],
            "description": skill["DESCRIPTION"],
            "roles": skill["ROLES"],
        }
        for skill in ai.available_skills(user)
    ]


@app.get("/ai/logs")
def ai_logs(db: Session = Depends(get_db), user=Depends(current_user)):
    if not services._is_hr(user):
        raise HTTPException(status_code=403, detail="Only HR/Admin can view AI logs")

    rows = (db.query(models.AILog, models.User.name)
            .outerjoin(models.User, models.User.id == models.AILog.user_id)
            .order_by(models.AILog.created_at.desc(), models.AILog.id.desc())
            .limit(50).all())
    return [
        {
            "user": {"id": log.user_id, "name": user_name},
            "question": log.question,
            "tool": log.tool_used,
            "created_at": log.created_at,
        }
        for log, user_name in rows
    ]


@app.get("/kpi")
def kpi(db: Session = Depends(get_db), user=Depends(current_user)):
    data = {
        "headcount": services.get_headcount(db, user),
        "attendance": services.get_attendance_summary(db, user),
        "late_comers": services.get_late_comers(db, user),
        "leaves": services.get_leave_summary(db, user),
    }
    return jsonable_encoder(data)


@app.post("/ai/chat")
def ai_chat(body: ChatIn, db: Session = Depends(get_db), user=Depends(current_user)):
    msg = body.message.strip()
    if not msg or len(msg) > 500:
        raise HTTPException(status_code=400, detail="Message must be 1-500 characters")
    if not ai.rate_ok(user.id):
        raise HTTPException(status_code=429, detail="Rate limit: 20 AI requests per hour")
    result = ai.chat(db, user, msg, [item.model_dump() for item in body.history])
    log_ai(db, user, msg, result)
    return {
        "answer": result["answer"],
        "ok": result["ok"],
        "label": "AI-generated",
        "skill": (result.get("tools") or [None])[0],
    }

@app.post("/ai/summary")
def ai_summary(db: Session = Depends(get_db), user=Depends(current_user)):
    if not services._is_hr(user):
        raise HTTPException(status_code=403, detail="Only HR/Admin can use the dashboard summary")
    if not ai.rate_ok(user.id):
        raise HTTPException(status_code=429, detail="Rate limit: 20 AI requests per hour")
    kpi_data = jsonable_encoder({
        "headcount": services.get_headcount(db, user),
        "attendance": services.get_attendance_summary(db, user),
        "late_comers": services.get_late_comers(db, user),
        "leaves": services.get_leave_summary(db, user),
    })
    result = ai.summarize(kpi_data)
    log_ai(db, user, "dashboard summary", {"answer": " | ".join(result["bullets"]), "tools": []}, "summary")
    if not result["ok"]:
        return {"ok": False, "bullets": [], "message": "Summary is unavailable right now.", "label": "AI-generated"}
    return {"ok": True, "bullets": result["bullets"], "label": "AI-generated", "kpi": kpi_data}

class LeaveIn(BaseModel):
    text: str


@app.post("/ai/smart-leave")
def ai_smart_leave(body: LeaveIn, db: Session = Depends(get_db), user=Depends(current_user)):
    msg = body.text.strip()
    if not msg or len(msg) > 300:
        raise HTTPException(status_code=400, detail="Text must be 1-300 characters")
    if not ai.rate_ok(user.id):
        raise HTTPException(status_code=429, detail="Rate limit: 20 AI requests per hour")
    result = ai.smart_leave(msg)
    log_ai(db, user, msg, {"answer": json.dumps(result.get("leave")), "tools": []}, "smart_leave")
    if not result["ok"]:
        return {"ok": False, "message": "Could not understand the request. Please fill the leave form manually.", "label": "AI-generated"}
    return {"ok": True, "prefill": result["leave"], "note": "Review and confirm. Nothing has been saved.", "label": "AI-generated"}

@app.get("/")
def home():
    return FileResponse("index.html")


@app.get("/dashboard")
def dashboard_page():
    return FileResponse("dashboard.html")