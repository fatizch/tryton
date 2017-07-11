# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import waiver
import offered
import contract
import wizard
import invoice


def register():
    Pool.register(
        waiver.PremiumWaiver,
        waiver.PremiumWaiverContractOption,
        offered.OptionDescription,
        offered.OptionDescriptionTaxRelationForWaiver,
        contract.Contract,
        contract.ContractOption,
        wizard.CreateWaiverChoice,
        wizard.SetWaiverEndDateChoice,
        invoice.InvoiceLineDetail,
        module='contract_waiver_premium', type_='model')

    Pool.register(
        wizard.CreateWaiver,
        wizard.SetWaiverEndDate,
        module='contract_waiver_premium', type_='wizard')
