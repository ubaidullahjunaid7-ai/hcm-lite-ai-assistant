import services


NAME = "leave_policy_info"
DESCRIPTION = "Annual leave entitlements and basic leave policy."
ROLES = ["HR", "EMPLOYEE"]


def run(user, **kwargs):
    return {
        "days_per_year": {
            "sick": 12,
            "casual": services.QUOTA["casual"],
            "annual": services.QUOTA["annual"],
        }
    }
