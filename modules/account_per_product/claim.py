# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

__all__ = [
    'Indemnification',
    ]


class Indemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    def _group_to_claim_invoice_key(self):
        res = super(Indemnification, self)._group_to_claim_invoice_key()
        res.update({'insurance_product': self.service.contract.product})
        return res

    @classmethod
    def _get_invoice(cls, key):
        invoice = super(Indemnification, cls)._get_invoice(key)
        invoice.product = key['insurance_product']
        return invoice
