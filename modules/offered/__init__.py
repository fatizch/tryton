from trytond.pool import Pool

from .rule_engine import *
from .offered import *
from .extra_data import *
from .test_case import *
from .configuration import *
from .package import *
from .report_engine import *


def register():
    Pool.register(
        Configuration,
        OptionDescription,
        Product,
        ProductOptionDescriptionRelation,
        OptionDescriptionRequired,
        OptionDescriptionExcluded,
        Package,
        PackageOptionDescriptionRelation,
        ProductPackageRelation,
        ExtraData,
        ExtraDataSubExtraDataRelation,
        ProductExtraDataRelation,
        OptionDescriptionExtraDataRelation,
        RuleEngine,
        OptionDescriptionEndingRule,
        TestCaseModel,
        ReportProductRelation,
        ReportTemplate,
        module='offered', type_='model')
