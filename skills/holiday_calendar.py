NAME = "holiday_calendar"
DESCRIPTION = "Sample company holidays and their dates."
ROLES = ["HR", "EMPLOYEE"]


def run(user, **kwargs):
    return {
        "holidays": [
            {"name": "New Year's Day", "date": "2026-01-01"},
            {"name": "Kashmir Day", "date": "2026-02-05"},
            {"name": "Pakistan Day", "date": "2026-03-23"},
            {"name": "Labour Day", "date": "2026-05-01"},
            {"name": "Independence Day", "date": "2026-08-14"},
            {"name": "Iqbal Day", "date": "2026-11-09"},
            {"name": "Quaid-e-Azam Day", "date": "2026-12-25"},
            {"name": "Company Wellness Day", "date": "2026-12-31"},
        ]
    }
