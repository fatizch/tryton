# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import commission
import invoice


def register():
    Pool.register(
        commission.Commission,
        commission.Agent,
        commission.CreateAgentsAsk,
        invoice.InvoiceLine,
        module='commission_waiting_cog', type_='model')
    Pool.register(
        commission.CreateAgents,
        module='commission_waiting_cog', type_='wizard')
