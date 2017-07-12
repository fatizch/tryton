# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import configuration
import extra_data
import offered
import package
import report_engine
import rule_engine
import test_case


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
        test_case.TestCaseModel,
        report_engine.ReportProductRelation,
        report_engine.ReportTemplate,
        module='offered', type_='model')
