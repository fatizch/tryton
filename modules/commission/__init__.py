from trytond.pool import Pool

from .offered import *
from .contract import *
from .party import *
from .distribution import *
from .contract import *
from .rule_engine import *
from .account import *


def register():
    Pool.register(
        Product,
        OptionDescription,
        CommissionOptionDescriptionOptionDescriptionRelation,
        CommissionRule,
        Contract,
        OptionCommissionOptionRelation,
        Option,
        ContractAgreementRelation,
        ContractInvoice,
        CommissionInvoice,
        Invoice,
        InvoiceLine,
        Premium,
        PremiumCommission,
        Party,
        Broker,
        DistributionNetwork,
        DistributionNetworkComPlanRelation,
        DistributionNetworkBrokerRelation,
        RuleEngineRuntime,
        # Account
        MoveBreakdown,
        Move,
        module='commission', type_='model')
