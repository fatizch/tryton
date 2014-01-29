from trytond.pool import Pool
from .table import *
from .test_case import *


def register():
    Pool.register(
        # From table
        TableDefinition,
        TableDefinitionDimension,
        TableCell,
        TableOpen2DAskDimensions,
        Table2D,
        DimensionDisplayer,
        # From test_case
        TestCaseModel,
        module='table', type_='model')

    Pool.register(
        # From table
        TableOpen2D,
        ManageDimension,
        TableCreation,
        module='table', type_='wizard')
