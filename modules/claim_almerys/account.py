# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls.business_kind.selection.append(
            ('third_party_management', "Third Party Management"))


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    almerys_services = fields.One2Many(
        'claim.service', 'third_party_invoice_line', "Almerys Services",
        readonly=True)
    almerys_canceled_services = fields.One2Many(
        'claim.service', 'third_party_invoice_line_cancel',
        "Almerys Canceled Services", readonly=True)
