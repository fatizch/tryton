from trytond.pool import Pool
from .table import *
from .test_case import *


def register():
    Pool.register(
        # from table
        TableDefinition,
        TableDefinitionDimension,
        TableCell,
        TableOpen2DAskDimensions,
        Table2D,
        DimensionDisplayer,
        # from test_case
        TestCaseModel,
        module='table', type_='model')
    Pool.register(
        # from table
        TableOpen2D,
        ManageDimension1,
        ManageDimension2,
        ManageDimension3,
        ManageDimension4,
        TableCreation,
        module='table', type_='wizard')
