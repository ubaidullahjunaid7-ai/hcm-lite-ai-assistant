import services


NAME = "get_leave_summary"
DESCRIPTION = "Summary of leave requests by type and status."
ROLES = ["HR", "EMPLOYEE"]


def run(user, **kwargs):
    return services.get_leave_summary(kwargs["db"], user)
