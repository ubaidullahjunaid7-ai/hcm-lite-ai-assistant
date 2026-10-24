from pprint import pprint
from db import SessionLocal
import models
import services as s

db = SessionLocal()
hr = db.query(models.User).filter_by(role="HR").first()
emp = db.query(models.User).filter_by(name="Sara Khan").first()

print("--- HR ---")
pprint(s.get_headcount(db, hr))
pprint(s.get_headcount(db, hr, "Engineering"))
pprint(s.get_attendance_summary(db, hr))
pprint(s.get_late_comers(db, hr))
pprint(s.get_payroll_summary(db, hr))
print("--- EMPLOYEE (Sara Khan) ---")
pprint(s.get_my_leave_balance(db, emp, "sick"))
pprint(s.get_attendance_summary(db, emp))
pprint(s.get_payroll_summary(db, emp))
pprint(s.search_employees(db, emp, "Ali"))