from trytond.pool import Pool
from .account import *
from .offered import *
from .contract import *
from .wizard import *


def register():
    Pool.register(
        Fee,
        ProductPremiumDates,
        Product,
        ProductFeeRelation,
        OptionDescriptionPremiumRule,
        OptionDescription,
        OptionDescriptionFeeRelation,
        OptionDescriptionTaxRelation,
        Contract,
        ContractOption,
        ContractFee,
        Premium,
        PremiumTax,
        DisplayContractPremiumDisplayer,
        DisplayContractPremiumDisplayerPremiumLine,
        module='premium', type_='model')

    Pool.register(
        DisplayContractPremium,
        module='premium', type_='wizard')
