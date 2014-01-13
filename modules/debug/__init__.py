from trytond.pool import Pool
from .debug import *


def register():
    Pool.register(
        # From file debug
        VisualizeDebug,
        module='debug', type_='model')

    Pool.register(
        # From file debug
        Debug,
        module='debug', type_='wizard')
