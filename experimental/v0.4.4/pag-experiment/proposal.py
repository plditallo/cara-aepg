from dataclasses import dataclass


@dataclass(frozen=True)
class Proposal:
    """What the agent asks the arm to do.

    primitive, end, velocity, and force are the motion the controller
    would actually execute. declared_* are the agent's own description of
    the action. The CARA gateway ignores them; the label-based baseline
    trusts them.
    """
    actor: str
    primitive: str          # grasp | place | insert | pour | thrust
    end: tuple
    velocity: float
    force: float
    declared_tool: str = ""
    declared_target: str = ""
    declared_operation: str = ""
