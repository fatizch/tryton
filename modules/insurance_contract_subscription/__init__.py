from trytond.pool import Pool

from .subscription_process import *
from .contract import *
from .endorsement import *


def register():
    Pool.register(
        ContractSubscription,
        Option,
        CoveredElement,
        CoveredData,
        SubscriptionManager,
        ProcessDesc,
        SubscriptionProcessParameters,
        #From Endorsement
        EndorsementProcessParameters,
        module='insurance_contract_subscription', type_='model')

    Pool.register(
        SubscriptionProcessFinder,
        EndorsementProcessFinder,
        module='insurance_contract_subscription', type_='wizard')
