from trytond.pool import Pool

from waiver import *
from offered import *
from contract import *
from wizard import *
from invoice import *


def register():
    Pool.register(
        PremiumWaiver,
        PremiumWaiverContractOption,
        OptionDescription,
        OptionDescriptionTaxRelationForWaiver,
        Contract,
        ContractOption,
        CreateWaiverChoice,
        SetWaiverEndDateChoice,
        InvoiceLineDetail,
        module='contract_waiver_premium', type_='model')

    Pool.register(
        CreateWaiver,
        SetWaiverEndDate,
        module='contract_waiver_premium', type_='wizard')
