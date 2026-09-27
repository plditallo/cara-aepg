from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any


class Relation(str, Enum):
    STRICTLY_NARROWER = "STRICTLY_NARROWER"
    EQUIVALENT = "EQUIVALENT"
    INCOMPARABLE = "INCOMPARABLE"
    BROADER = "BROADER"
    UNRESOLVED = "UNRESOLVED"


GOOD = frozenset({Relation.STRICTLY_NARROWER, Relation.EQUIVALENT})

Comparator = Callable[[Any, Any], Relation]


def _is_number(x):
    # bool is a subclass of int in Python; a boolean is not a budget.
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x  # x == x rejects NaN


def set_subset(child, parent):
    if isinstance(child, (str, bytes)) or isinstance(parent, (str, bytes)):
        return Relation.UNRESOLVED
    try:
        c, p = set(child), set(parent)
    except TypeError:
        return Relation.UNRESOLVED
    if c == p:
        return Relation.EQUIVALENT
    if c < p:
        return Relation.STRICTLY_NARROWER
    return Relation.BROADER if p < c else Relation.INCOMPARABLE


def numeric_max(child, parent):
    if not _is_number(child) or not _is_number(parent):
        return Relation.UNRESOLVED
    if child == parent:
        return Relation.EQUIVALENT
    return Relation.STRICTLY_NARROWER if child < parent else Relation.BROADER


def numeric_min(child, parent):
    if not _is_number(child) or not _is_number(parent):
        return Relation.UNRESOLVED
    if child == parent:
        return Relation.EQUIVALENT
    return Relation.STRICTLY_NARROWER if child > parent else Relation.BROADER


def boolean_no_escalation(child, parent):
    if not isinstance(child, bool) or not isinstance(parent, bool):
        return Relation.UNRESOLVED
    if child == parent:
        return Relation.EQUIVALENT
    if parent and not child:
        return Relation.STRICTLY_NARROWER
    return Relation.BROADER


# Ordered from least to most consequential. Deployments should replace this
# with their own registered ordering; any class not listed is UNRESOLVED.
DEFAULT_SIDE_EFFECT_ORDER = (
    "none",
    "read_only",
    "reversible",
    "persistent",
    "external",
    "irreversible",
)


def ordered_class(order):
    index = {name: i for i, name in enumerate(order)}

    def compare(child, parent):
        if child not in index or parent not in index:
            return Relation.UNRESOLVED
        if index[child] == index[parent]:
            return Relation.EQUIVALENT
        return Relation.STRICTLY_NARROWER if index[child] < index[parent] else Relation.BROADER

    return compare


@dataclass
class ComparatorRegistry:
    comparators: dict[str, Comparator]

    @classmethod
    def default(cls):
        return cls({
            "set-subset/v1": set_subset,
            "numeric-max/v1": numeric_max,
            "numeric-min/v1": numeric_min,
            "boolean-no-escalation/v1": boolean_no_escalation,
        })

    def compare(self, comparator_id, child, parent):
        fn = self.comparators.get(comparator_id)
        return Relation.UNRESOLVED if fn is None else fn(child, parent)
