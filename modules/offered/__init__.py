from trytond.pool import Pool

from .offered import *
from .complementary_data import *
from .coverage import *


def register():
    Pool.register(
        Offered,
        Coverage,
        PackageCoverage,
        Product,
        ProductOptionsCoverage,
        # from complementary_data
        ComplementaryDataDefinition,
        ComplementaryDataRecursiveRelation,
        ProductComplementaryDataRelation,
        CoverageComplementaryDataRelation,
        module='offered', type_='model')
