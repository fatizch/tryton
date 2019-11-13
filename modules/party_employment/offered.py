# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import fields


__all__ = [
    'ItemDescription',
    ]


class EmploymentDataValidationError(ValidationError):
    pass


class ItemDescription(metaclass=PoolMeta):
    __name__ = 'offered.item.description'

    employment_required = fields.Boolean('Employment Information Required',
        help='If set to True, employment informations '
        'will be required for the covered elements',
        states={'invisible': Eval('kind') != 'person'})

    def _has_valid_employment_data(self, covered_element):
        return bool(covered_element.party.get_employment_version_data(
                'gross_salary', covered_element.contract.start_date))

    def check_covered_element(self, covered_element):
        super().check_covered_element(covered_element)
        if self.employment_required:
            if not self._has_valid_employment_data(covered_element):
                raise EmploymentDataValidationError(gettext(
                    'party_employment.msg_employment_required',
                    party=covered_element.party.rec_name))
