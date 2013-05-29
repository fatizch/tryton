from trytond.pool import Pool

from .plan import *
from .agreement import *
from .party import *
from .distribution import *


def register():
    Pool.register(
        #Plan
        CommissionPlan,
        CommissionComponent,
        CommissionPlanComponentRelation,
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
        module='commission', type_='model')
