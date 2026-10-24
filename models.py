from sqlalchemy import Column, Integer, String, Date, Time, Float, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(120))
    department = Column(String(50))
    role = Column(String(20))      # HR | EMPLOYEE
    status = Column(String(20))    # active | inactive
    salary = Column(Float)
    joined_on = Column(Date)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date)
    check_in = Column(Time, nullable=True)
    status = Column(String(20))    # present | late | absent

class Leave(Base):
    __tablename__ = "leaves"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String(20))      # sick | casual | annual
    start_date = Column(Date)
    end_date = Column(Date)
    reason = Column(Text)
    status = Column(String(20))    # pending | approved | rejected

class AILog(Base):
    __tablename__ = "ai_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    question = Column(Text)
    tool_used = Column(String(60))
    response = Column(Text)
    status = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())