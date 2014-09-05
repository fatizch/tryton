from trytond.pool import Pool

from .rule_engine import *
from .offered import *
from .extra_data import *
from .test_case import *
from .configuration import *


def register():
    Pool.register(
        Configuration,
        Offered,
        OptionDescription,
        PackageOptionDescription,
        Product,
        ProductOptionDescriptionRelation,
        OptionDescriptionRequired,
        OptionDescriptionExcluded,
        ExtraData,
        ExtraDataSubExtraDataRelation,
        ProductExtraDataRelation,
        OptionDescriptionExtraDataRelation,
        OptionDescriptionRule,
        TestCaseModel,
        module='offered', type_='model')
