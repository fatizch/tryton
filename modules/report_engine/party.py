# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.report_engine import Printable

__all__ = [
    'Party',
    ]


class Party(Printable):
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    def get_doc_template_kind(self):
        res = super(Party, self).get_doc_template_kind()
        res.append('party')
        return res

    def get_contact(self):
        return self

    def get_sender(self):
        company = Transaction().context.get('company')
        if company:
            return Pool().get('company.company')(company).party

    def get_object_for_contact(self):
        return self
