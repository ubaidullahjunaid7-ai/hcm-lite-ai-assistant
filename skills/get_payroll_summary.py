import services


NAME = "get_payroll_summary"
DESCRIPTION = "Payroll and salary summary by department."
ROLES = ["HR"]


def run(user, **kwargs):
    return services.get_payroll_summary(kwargs["db"], user)
