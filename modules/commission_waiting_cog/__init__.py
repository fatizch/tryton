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
