from trytond.pool import Pool
from .coop_process import *


def register():
    Pool.register(
        Status,
        Code,
        ProcessLog,
        StepTransition,
        ProcessStepRelation,
        ProcessDesc,
        XMLViewDesc,
        StepDesc,
        ProcessParameters,
        module='coop_process', type_='model')

    Pool.register(
        GenerateGraph,
        module='coop_process', type_='report')

    Pool.register(
        ProcessFinder,
        module='coop_process', type_='wizard')
