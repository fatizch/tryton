from trytond.pool import Pool
from .coop_process import *
from .export import *


def register():
    Pool.register(
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
        module='coop_process', type_='model')

    Pool.register(
        GenerateGraph,
        module='coop_process', type_='report')

    Pool.register(
        ProcessFinder,
        module='coop_process', type_='wizard')
