from trytond.pool import Pool

from .rule_engine_results import *
from .offered import *
from .complementary_data import *
from .export import *
from .test_case import *


def register():
    Pool.register(
        # From offered
        Offered,
        OptionDescription,
        PackageOptionDescription,
        Product,
        ProductOptionDescriptionRelation,
        # from complementary_data
        ExtraData,
        ExtraDataSubExtraDataRelation,
        ProductExtraDataRelation,
        OptionDescriptionExtraDataRelation,
        Tag,
        ExtraDataTagRelation,
        # from test_case
        TestCaseModel,
        # from export
        ExportPackage,
        module='offered', type_='model')
