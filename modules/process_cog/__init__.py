from trytond.pool import Pool
from .process import *


def register():
    Pool.register(
        # From process
        Status,
        ProcessAction,
        ProcessLog,
        ProcessTransition,
        ProcessStepRelation,
        Process,
        ViewDescription,
        ProcessStep,
        ProcessStart,
        module='process_cog', type_='model')

    Pool.register(
        GenerateGraph,
        module='process_cog', type_='report')

    Pool.register(
        ProcessFinder,
        ProcessEnd,
        ProcessResume,
        module='process_cog', type_='wizard')
