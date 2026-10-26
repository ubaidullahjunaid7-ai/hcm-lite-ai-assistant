import services


NAME = "get_headcount"
DESCRIPTION = "Number of active employees, optionally filtered by department."
ROLES = ["HR"]
PARAMETERS = {"department": (str, False)}


def run(user, **kwargs):
    return services.get_headcount(kwargs["db"], user, kwargs.get("department"))
