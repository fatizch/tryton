from trytond.pool import Pool

from .offered import *
from .extra_data import *
from .report_engine import *
from .contract import *


def register():
    Pool.register(
        UnderwritingDecision,
        Contract,
        ContractUnderwriting,
        ContractUnderwritingOption,
        Product,
        OptionDescription,
        ExtraData,
        ReportTemplate,
        module='contract_underwriting', type_='model')
