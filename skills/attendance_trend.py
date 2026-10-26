import services


NAME = "attendance_trend"
DESCRIPTION = "Company attendance rate trend for the last 7 days."
ROLES = ["HR"]


def run(user, **kwargs):
    return services.get_attendance_trend(kwargs["db"], user)
