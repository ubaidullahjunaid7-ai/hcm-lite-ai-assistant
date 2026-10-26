import services


NAME = "get_my_leave_balance"
DESCRIPTION = "Remaining leave balance of the current user for sick, casual, or annual leave."
ROLES = ["HR", "EMPLOYEE"]
PARAMETERS = {"leave_type": (str, True)}


def run(user, **kwargs):
    return services.get_my_leave_balance(kwargs["db"], user, kwargs["leave_type"])
