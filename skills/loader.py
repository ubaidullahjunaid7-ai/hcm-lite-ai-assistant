import importlib
import re
from pathlib import Path


_SKILL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_SKILLS_DIRECTORY = Path(__file__).parent


def load_skills():
    skills = {}
    for path in sorted(_SKILLS_DIRECTORY.glob("*.py")):
        if path.stem in {"__init__", "loader"}:
            continue

        module = importlib.import_module(f"{__package__}.{path.stem}")
        name = getattr(module, "NAME", None)
        description = getattr(module, "DESCRIPTION", None)
        roles = getattr(module, "ROLES", None)
        run = getattr(module, "run", None)
        parameters = getattr(module, "PARAMETERS", {})

        if not isinstance(name, str) or not _SKILL_NAME.fullmatch(name):
            raise ValueError(f"Invalid NAME in skill module {path.name}")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"Missing DESCRIPTION in skill module {path.name}")
        if (not isinstance(roles, list) or not roles
                or any(not isinstance(role, str) or not role for role in roles)
                or len(set(roles)) != len(roles)):
            raise ValueError(f"Invalid ROLES in skill module {path.name}")
        if not callable(run):
            raise ValueError(f"Missing run(user, **kwargs) in skill module {path.name}")
        if not isinstance(parameters, dict):
            raise ValueError(f"Invalid PARAMETERS in skill module {path.name}")
        for parameter, details in parameters.items():
            if (not isinstance(parameter, str) or not _SKILL_NAME.fullmatch(parameter)
                    or not isinstance(details, tuple) or len(details) != 2
                    or details[0] not in (str, int, float, bool)
                    or not isinstance(details[1], bool)):
                raise ValueError(f"Invalid parameter definition in skill module {path.name}")
        if name in skills:
            raise ValueError(f"Duplicate skill NAME: {name}")

        skills[name] = {
            "NAME": name,
            "DESCRIPTION": description.strip(),
            "ROLES": roles,
            "PARAMETERS": parameters,
            "run": run,
        }
    return skills


def skills_for_user(skills, user):
    role = getattr(user, "role", None)
    return [skill for skill in skills.values() if role in skill["ROLES"]]
