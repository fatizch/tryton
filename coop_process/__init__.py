from trytond.pool import Pool
from .coop_process import *


def register():
    Pool.register(
        StepTransition,
        module='process', type_='model')

    Pool.register(
        GenerateGraph,
        module='process', type_='report')
