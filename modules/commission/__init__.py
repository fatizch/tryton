from trytond.pool import Pool

from .plan import *
from .agreement import *
from .party import *
from .distribution import *
from .contract import *
from .rule_engine import *
from .account import *


def register():
    Pool.register(
        #Plan
        CommissionPlan,
        CommissionComponent,
        CommissionComponentCoverageRelation,
        CommissionRule,
        #Agreement
        CommissionAgreement,
        CompensatedOption,
        CommissionOption,
        #Party
        Party,
        Broker,
        #Distribution
        DistributionNetwork,
        DistributionNetworkComPlanRelation,
        DistributionNetworkBrokerRelation,
        #Contract
        PriceLineComRelation,
        PriceLine,
        Contract,
        #Rule Engine
        OfferedContext,
        # Account
        Move,
        module='commission', type_='model')
