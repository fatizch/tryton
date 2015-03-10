from trytond.pool import Pool
from .commission import *


def register():
    Pool.register(
        PrepaymentPaymentDateRule,
        Plan,
        module='commission_prepayment_rule_engine', type_='model')
