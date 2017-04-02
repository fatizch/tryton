# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import configuration

from .contract import *
from .commission import *
from .invoice import *
from .event import *
from .rule_engine import *


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationTerminationReason,
        Contract,
        ContractOption,
        PlanLines,
        Commission,
        Plan,
        Agent,
        Invoice,
        Event,
        RuleEngineRuntime,
        module='commission_insurance_prepayment', type_='model')
    Pool.register(
        FilterCommissions,
        FilterAggregatedCommissions,
        module='commission_insurance_prepayment', type_='wizard')