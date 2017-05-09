# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import commission
import invoice

from trytond.pool import Pool


def register():
    Pool.register(
        commission.Agent,
        commission.Commission,
        invoice.Invoice,
        module='commission_wholesale', type_='model')
    Pool.register(
        commission.FilterCommissions,
        commission.CreateInvoicePrincipal,
        module='commission_wholesale', type_='wizard')
