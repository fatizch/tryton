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
        #From Offered
        Product,
        OptionDescription,
        CommissionOptionDescriptionOptionDescriptionRelation,
        CommissionRule,
        #From Contract
        Contract,
        OptionCommissionOptionRelation,
        Option,
        ContractAgreementRelation,
        ContractInvoice,
        CommissionInvoice,
        Invoice,
        Premium,
        PremiumCommission,
        #From Party
        Party,
        Broker,
        #From Distribution
        DistributionNetwork,
        DistributionNetworkComPlanRelation,
        DistributionNetworkBrokerRelation,
        #Rule Engine
        RuleEngineRuntime,
        # Account
        MoveBreakdown,
        Move,
        module='commission', type_='model')
