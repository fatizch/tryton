# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .table import *
from .test_case import *


def register():
    Pool.register(
        # From table
        TableDefinition,
        TableDefinitionDimension,
        TableDefinitionDimensionOpenAskType,
        TableCell,
        TableOpen2DAskDimensions,
        Table2D,
        # From test_case
        TestCaseModel,
        module='table', type_='model')

    Pool.register(
        # From table
        TableDefinitionDimensionOpen,
        TableOpen2D,
        module='table', type_='wizard')
