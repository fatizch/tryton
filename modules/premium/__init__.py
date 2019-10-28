# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import account
from . import offered
from . import contract
from . import wizard
from . import rule_engine


def register():
    Pool.register(
        account.Fee,
        offered.ProductPremiumDate,
        offered.Product,
        offered.ProductFeeRelation,
        offered.OptionDescriptionPremiumRule,
        offered.OptionDescription,
        offered.OptionDescriptionFeeRelation,
        offered.OptionDescriptionTaxRelation,
        contract.Contract,
        contract.ContractOption,
        contract.ContractFee,
        rule_engine.RuleEngine,
        contract.Premium,
        wizard.DisplayContractPremiumDisplayer,
        wizard.DisplayContractPremiumDisplayerPremiumLine,
        module='premium', type_='model')

    Pool.register(
        contract.ContractTaxRuleCountry,
        contract.PremiumTaxRuleCountry,
        module='premium', type_='model', depends=['account_tax_rule_country'])

    Pool.register(
        wizard.DisplayContractPremium,
        module='premium', type_='wizard')
