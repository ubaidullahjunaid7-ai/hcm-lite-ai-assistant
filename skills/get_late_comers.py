import services


NAME = "get_late_comers"
DESCRIPTION = "Employees ranked by late arrivals. Optional month uses YYYY-MM; omit for the current month."
ROLES = ["HR", "EMPLOYEE"]
PARAMETERS = {"month": (str, False)}


def run(user, **kwargs):
    return services.get_late_comers(kwargs["db"], user, kwargs.get("month"))
