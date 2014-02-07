from trytond.pool import Pool

from .offered import *
from .contract import *
from .party import *
from .distribution import *
from .contract import *
from .rule_engine import *
from .account import *
from .billing import *


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
        #From Party
        Party,
        Broker,
        #From Distribution
        DistributionNetwork,
        DistributionNetworkComPlanRelation,
        DistributionNetworkBrokerRelation,
        # From billing
        BillingPremiumCommissionOptionRelation,
        Premium,
        #Rule Engine
        RuleEngineRuntime,
        # Account
        MoveBreakdown,
        Move,
        module='commission', type_='model')
