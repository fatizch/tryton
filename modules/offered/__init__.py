from trytond.pool import Pool

from .rule_engine_results import *
from .offered import *
from .complementary_data import *
from .coverage import *
from .export import *


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
        Tag,
        ComplementaryDataDefTagRelation,
        #For export use
        ExportPackage,
        module='offered', type_='model')
