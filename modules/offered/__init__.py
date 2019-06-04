# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import configuration
from . import extra_data
from . import offered
from . import package
from . import report_engine
from . import rule_engine
from . import global_search
from . import test_case
from . import api


def register():
    Pool.register(
        configuration.Configuration,
        offered.OptionDescription,
        offered.Product,
        offered.ProductOptionDescriptionRelation,
        offered.OptionDescriptionRequired,
        offered.OptionDescriptionExcluded,
        package.Package,
        package.PackageOptionDescriptionRelation,
        package.ProductPackageRelation,
        extra_data.ExtraData,
        extra_data.ExtraDataSubExtraDataRelation,
        offered.ProductExtraDataRelation,
        offered.OptionDescriptionExtraDataRelation,
        rule_engine.RuleEngine,
        rule_engine.OptionDescriptionEndingRule,
        report_engine.ReportProductRelation,
        report_engine.ReportTemplate,
        global_search.GlobalSearchSet,
        test_case.TestCaseModel,
        module='offered', type_='model')

    Pool.register(
        api.ExtraData,
        module='offered', type_='model', depends=['api'])
