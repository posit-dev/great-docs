# This module contains all the enumerations that extend those of griffe.

from __future__ import annotations

from enum import Enum


class DCDocstringSectionKind(str, Enum):
    """
    Enumeration of the possible docstring section kinds specific to Dataclasses
    """

    # Added for great-docs
    init_parameters = "init parameters"
    """Init only parameters of a dataclass"""

    parameter_attributes = "parameter attributes"
    """Parameters and at the same time attributes of a dataclass"""
