# coding: utf-8

"""
SHI tasks module.

Custom tasks for Single Higgs Combinations, extending DHI tasks.
"""

__all__ = [
    "HelloWorld",
    "HZZCreateWorkspace",
    "HZZSnapshot",
    "HZZLikelihoodScan",
    "HZZMergeLikelihoodScan",
    "HZZPlotLikelihoodScan",
    "HZZPlotMultipleLikelihoodScans",
    "HZZAllPOIs",
]

# Import tasks to make them available
from shi.tasks.hello_world import HelloWorld
from shi.tasks.hzz_incremental import (
    HZZCreateWorkspace,
    HZZSnapshot,
    HZZLikelihoodScan,
    HZZMergeLikelihoodScan,
    HZZPlotLikelihoodScan,
    HZZPlotMultipleLikelihoodScans,
    HZZAllPOIs,
)
