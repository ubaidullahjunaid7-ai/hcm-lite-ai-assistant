import services


NAME = "team_directory"
DESCRIPTION = "Names, departments, and job titles of active employees."
ROLES = ["HR", "EMPLOYEE"]
PARAMETERS = {"department": (str, False)}


def run(user, **kwargs):
    return services.get_team_directory(
        kwargs["db"],
        user,
        kwargs.get("department"),
    )
