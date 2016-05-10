from trytond.pool import Pool
from .account import *
from .offered import *
from .contract import *
from .wizard import *
from .rule_engine import *


def register():
    Pool.register(
        Fee,
        ProductPremiumDate,
        Product,
        ProductFeeRelation,
        OptionDescriptionPremiumRule,
        OptionDescription,
        OptionDescriptionFeeRelation,
        OptionDescriptionTaxRelation,
        Contract,
        ContractOption,
        ContractFee,
        RuleEngine,
        Premium,
        DisplayContractPremiumDisplayer,
        DisplayContractPremiumDisplayerPremiumLine,
        module='premium', type_='model')

    Pool.register(
        DisplayContractPremium,
        module='premium', type_='wizard')
