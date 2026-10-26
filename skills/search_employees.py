import services


NAME = "search_employees"
DESCRIPTION = "Search employees by name or department, subject to the current user's permissions."
ROLES = ["HR", "EMPLOYEE"]
PARAMETERS = {"query": (str, True)}


def run(user, **kwargs):
    return services.search_employees(kwargs["db"], user, kwargs["query"])
