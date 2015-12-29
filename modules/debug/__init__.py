from trytond.pool import Pool
from .debug import *


def register():
    Pool.register(
        # From file debug
        FieldInfo,
        ModelInfo,
        VisualizeDebug,
        DebugModelInstance,
        DebugMROInstance,
        DebugMethodInstance,
        DebugMethodMROInstance,
        DebugFieldInstance,
        DebugViewInstance,
        DebugOnChangeRelation,
        DebugOnChangeWithRelation,
        module='debug', type_='model')

    Pool.register(
        # From file debug
        DebugModel,
        Debug,
        RefreshDebugData,
        OpenInitialFrame,
        module='debug', type_='wizard')
