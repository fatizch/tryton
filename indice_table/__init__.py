from trytond.pool import Pool
from .indice_table import *


def register():
    Pool.register(
        IndiceTableDefinition,
        IndiceTableDefinitionDimension,
        IndiceTable,
        IndiceTableOpen2DAskDimensions,
        IndiceTable2D,
        module='indice_table', type_='model')
    Pool.register(
        IndiceTableOpen2D,
        module='indice_table', type_='wizard')
