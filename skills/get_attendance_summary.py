import services


NAME = "get_attendance_summary"
DESCRIPTION = "Attendance summary and rate. Optional month uses YYYY-MM; omit for the current month."
ROLES = ["HR", "EMPLOYEE"]
PARAMETERS = {"month": (str, False)}


def run(user, **kwargs):
    return services.get_attendance_summary(kwargs["db"], user, kwargs.get("month"))
