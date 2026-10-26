import services


NAME = "department_report"
DESCRIPTION = "Active employee headcount grouped by department."
ROLES = ["HR"]


def run(user, **kwargs):
    return services.get_department_report(kwargs["db"], user)
