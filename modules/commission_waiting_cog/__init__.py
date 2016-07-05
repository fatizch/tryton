# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .commission import *
from .invoice import *


def register():
    Pool.register(
        Commission,
        Agent,
        CreateAgentsAsk,
        InvoiceLine,
        module='commission_waiting_cog', type_='model')
    Pool.register(
        CreateAgents,
        module='commission_waiting_cog', type_='wizard')
