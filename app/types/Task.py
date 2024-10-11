from enum import Enum


class TaskType(Enum):
    GeometryCheck = "GeometryCheck"
    Mesh = "Mesh"
    DE = "DE"
    DG = "DG"
    BOTH = "BOTH"
