"""Perception as a PolicyInformationSource (AEPG-PIS-001).

The gateway learns what the gripper holds and what a motion ends at from
this service, never from the proposal. In the simulation it reads the
World directly; on hardware it would be an attested vision/state pipeline
that the governed agent has no write access to.
"""
from aepg_ref.canonical import sha256_uri

PIS_ID = "cara:pis:sim:perception"


class Perception:
    def __init__(self, world):
        self._world = world

    def snapshot(self):
        snap = self._world.snapshot()
        return snap, sha256_uri(snap)
