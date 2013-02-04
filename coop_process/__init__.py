from trytond.pool import Pool
from .coop_process import *


def register():
    Pool.register(
        StepTransition,
        ProcessDesc,
        StepDesc,
        module='coop_process', type_='model')

    Pool.register(
        GenerateGraph,
        module='coop_process', type_='report')
