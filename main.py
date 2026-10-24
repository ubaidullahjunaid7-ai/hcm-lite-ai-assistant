import json
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

import models, services, ai
from db import get_db

app = FastAPI(title="HR AI Assistant")


def current_user(x_user_id: int = Header(...), db: Session = Depends(get_db)):
    user = db.get(models.User, x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


class ChatIn(BaseModel):
    message: str


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
    result = ai.chat(db, user, msg)
    log_ai(db, user, msg, result)
    return {"answer": result["answer"], "ok": result["ok"], "label": "AI-generated"}

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