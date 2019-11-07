# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import waiver
from . import offered
from . import rule_engine
from . import contract
from . import wizard
from . import invoice
from . import discount
from . import batch
from . import api


def register():
    Pool.register(
        waiver.WaiverPremium,
        waiver.WaiverPremiumOption,
        discount.DiscountModification,
        discount.DiscountModificationOption,
        offered.Product,
        offered.OptionDescription,
        offered.WaiverPremiumRule,
        offered.WaiverPremiumRuleTaxRelation,
        offered.CommercialDiscount,
        offered.CommercialDiscountModificationRule,
        offered.DiscountRuleTax,
        offered.DiscountRuleOption,
        rule_engine.RuleEngine,
        contract.Contract,
        contract.ContractOption,
        contract.CommercialDiscountContract,
        wizard.CreatePremiumModificationChoice,
        wizard.SetPremiumModificationEndDateChoice,
        invoice.Invoice,
        invoice.InvoiceLineDetail,
        batch.WaiverPeriodsCreationBatch,
        module='contract_premium_modification', type_='model')

    Pool.register(
        wizard.CreateWaivers,
        wizard.CreateDiscounts,
        wizard.SetPremiumModificationEndDate,
        module='contract_premium_modification', type_='wizard')

    Pool.register(
        api.APIContract,
        module='contract_premium_modification', type_='model', depends=['api'])
