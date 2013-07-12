from trytond.pool import Pool
from .table import *


def register():
    Pool.register(
        TableDefinition,
        TableDefinitionDimension,
        TableCell,
        TableOpen2DAskDimensions,
        Table2D,
        DimensionDisplayer,
        module='table', type_='model')
    Pool.register(
        TableOpen2D,
        ManageDimension1,
        ManageDimension2,
        ManageDimension3,
        ManageDimension4,
        TableCreation,
        module='table', type_='wizard')
