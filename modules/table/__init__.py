from trytond.pool import Pool
from .table import *


def register():
    Pool.register(
        TableDefinition,
        TableDefinitionDimension,
        TableCell,
        TableOpen2DAskDimensions,
        Table2D,
        module='table', type_='model')
    Pool.register(
        TableOpen2D,
        module='table', type_='wizard')
