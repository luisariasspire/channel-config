import importlib
import inspect
from pathlib import Path
from typing import Any, Callable, List, Optional

from channel_tool.validation_rules.utils import (
    ValidationRuleInput,
    ValidationRuleViolatedError,
)


def is_validation_function(member: Any) -> bool:
    if not inspect.isfunction(member):
        return False

    if member.__name__.startswith("_"):
        return False

    if not inspect.getfullargspec(member).args == ["input"]:
        return False

    annotations = member.__annotations__

    if len(annotations) != 2:
        return False

    if not annotations["input"] == ValidationRuleInput:
        return False

    if not annotations["return"] == Optional[ValidationRuleViolatedError]:
        return False

    return True


def get_validation_rules() -> (
    List[Callable[[ValidationRuleInput], Optional[ValidationRuleViolatedError]]]
):
    all_validators = []

    for path in Path("channel_tool/validation_rules").rglob("*.py"):
        dir = path.parent.__str__().replace("/", ".")
        package = importlib.import_module(f"{dir}.{path.stem}")
        package_validators = [
            obj for _, obj in inspect.getmembers(package, is_validation_function)
        ]

        all_validators.extend(package_validators)

    return all_validators
