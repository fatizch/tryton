# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.exceptions import UserError

from trytond.modules.coog_core import fields


__all__ = [
    'ItemDescription',
    ]


class ItemDescription(metaclass=PoolMeta):
    __name__ = 'offered.item.description'

    ssn_required = fields.Boolean('SSN required',
        help='If set to True, SSN will be required',
        states={'invisible': Eval('kind') != 'person'})

    def check_covered_element(self, covered_element):
        if self.ssn_required and not covered_element.party.ssn:
            raise UserError(gettext('party_ssn.msg_ssn_required_for_insured',
                rec_name=covered_element.party.rec_name))
