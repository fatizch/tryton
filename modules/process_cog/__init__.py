from trytond.pool import Pool
from .process import *
from .export import *


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
        # From export
        ExportPackage,
        module='process_cog', type_='model')

    Pool.register(
        GenerateGraph,
        module='process_cog', type_='report')

    Pool.register(
        ProcessFinder,
        module='process_cog', type_='wizard')
