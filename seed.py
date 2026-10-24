import random
from datetime import date, time, timedelta
from db import SessionLocal, engine, Base
import models

random.seed(42)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
db = SessionLocal()

depts = ["Engineering", "Sales", "Finance"]
names = ["Ali Raza", "Sara Khan", "Usman Tariq", "Ayesha Noor", "Hamza Sheikh",
         "Fatima Zahra", "Bilal Ahmed", "Hina Malik", "Zain Abbas", "Maryam Iqbal",
         "Omar Farooq", "Noor Fatima", "Ahmed Hassan", "Sana Javed", "Daniyal Ali"]

users = [models.User(name="HR Admin", email="hr@company.com", department="HR", role="HR",
                     status="active", salary=150000, joined_on=date(2020, 1, 1))]
for i, n in enumerate(names):
    users.append(models.User(
        name=n, email=f"{n.split()[0].lower()}{i}@company.com", department=depts[i % 3],
        role="EMPLOYEE", status="inactive" if i == 14 else "active",
        salary=random.randint(60, 140) * 1000,
        joined_on=date(2021 + i % 4, random.randint(1, 12), random.randint(1, 28))))
db.add_all(users)
db.commit()

today = date.today()
for u in users:
    if u.status != "active":
        continue
    for k in range(30):
        d = today - timedelta(days=k)
        if d.weekday() >= 5:
            continue
        r = random.random()
        if r < 0.05:
            st, t = "absent", None
        elif r < 0.20:
            st, t = "late", time(9, random.randint(16, 59))
        else:
            st, t = "present", time(random.choice([8, 9]), random.randint(0, 14))
        db.add(models.Attendance(user_id=u.id, date=d, check_in=t, status=st))

for u in users[1:10]:
    s = date(today.year, random.randint(1, 8), random.randint(1, 25))
    db.add(models.Leave(user_id=u.id, type="sick", start_date=s,
                        end_date=s + timedelta(days=random.randint(0, 2)),
                        reason="Fever", status="approved"))
for u in users[3:7]:
    s = date(today.year, random.randint(1, 8), random.randint(1, 25))
    db.add(models.Leave(user_id=u.id, type="casual", start_date=s,
                        end_date=s + timedelta(days=1), reason="Family event", status="approved"))
db.add(models.Leave(user_id=users[1].id, type="annual", start_date=today + timedelta(days=20),
                    end_date=today + timedelta(days=22), reason="Trip", status="pending"))
db.commit()
print("users:", db.query(models.User).count(),
      "attendance:", db.query(models.Attendance).count(),
      "leaves:", db.query(models.Leave).count())