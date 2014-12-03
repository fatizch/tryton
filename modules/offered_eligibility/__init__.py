from trytond.pool import Pool
from .offered import *
from .contract import *


def register():
    Pool.register(
        OptionDescription,
        ContractOption,
        OptionDescriptionEligibilityRule,
        module='offered_eligibility', type_='model')
