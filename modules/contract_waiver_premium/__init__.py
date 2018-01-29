# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import waiver
import offered
import rule_engine
import contract
import wizard
import invoice
import batch


def register():
    Pool.register(
        waiver.WaiverPremium,
        waiver.WaiverPremiumOption,
        offered.OptionDescription,
        offered.WaiverPremiumRule,
        offered.WaiverPremiumRuleTaxRelation,
        rule_engine.RuleEngine,
        contract.Contract,
        contract.ContractOption,
        wizard.CreateWaiverChoice,
        wizard.SetWaiverEndDateChoice,
        invoice.InvoiceLineDetail,
        batch.WaiverPeriodsCreationBatch,
        module='contract_waiver_premium', type_='model')

    Pool.register(
        wizard.CreateWaiver,
        wizard.SetWaiverEndDate,
        module='contract_waiver_premium', type_='wizard')
