# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from . import table
from . import test_case
from . import wizard
from trytond.pool import Pool


def register():
    Pool.register(
        table.TableDefinition,
        table.TableDefinitionDimension,
        table.TableDefinitionDimensionOpenAskType,
        table.TableCell,
        table.TableOpen2DAskDimensions,
        table.Table2D,
        test_case.TestCaseModel,
        wizard.Import2DTableParam,
        module='table', type_='model')

    Pool.register(
        table.TableDefinitionDimensionOpen,
        table.TableOpen2D,
        wizard.Import2DTable,
        module='table', type_='wizard')
