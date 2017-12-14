# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import commission
import invoice
import contract
import offered


def register():
    Pool.register(
        commission.Commission,
        commission.Agent,
        commission.AgentAgentRelation,
        commission.Plan,
        commission.PlanAgentRelation,
        invoice.InvoiceLine,
        contract.Contract,
        contract.ContractOption,
        offered.OptionDescription,
        module='commission_multi_agents', type_='model')
