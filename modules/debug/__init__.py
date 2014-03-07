from trytond.pool import Pool
from .debug import *


def register():
    Pool.register(
        # From file debug
        FieldInfo,
        ModelInfo,
        VisualizeDebug,
        module='debug', type_='model')

    Pool.register(
        # From file debug
        DebugModel,
        Debug,
        module='debug', type_='wizard')
