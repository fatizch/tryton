# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.pool import PoolMeta
from trytond.model import ModelView
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import model


__all__ = [
    'ClaimService',
    'Indemnification',
    ]


class ClaimService(metaclass=PoolMeta):
    __name__ = 'claim.service'

    def calculate_ceiling(self):
        return self.benefit.calculate_ceiling(self)

    def check_indemnification_ceiling(self):
        ceiling = self.calculate_ceiling()
        if not ceiling:
            return
        amount = self.get_indemnifications_total_amount()
        if self.get_indemnifications_total_amount() > ceiling:
            raise ValidationError(gettext(
                    'claim_indemnification_ceiling'
                    '.msg_indemnifications_above_ceiling',
                    service=self.rec_name,
                    ceiling=ceiling,
                    amount=amount))

    def get_indemnifications_total_amount(self):
        # round how ?
        return sum(x.amount for x in self.indemnifications
            if not x.status.startswith('cancel') and x.status != 'rejected')


class Indemnification(metaclass=PoolMeta):
    __name__ = 'claim.indemnification'

    @classmethod
    def check_ceiling(cls, indemnifications):
        with model.error_manager():
            for service in {x.service for x in indemnifications}:
                service.check_indemnification_ceiling()

    @classmethod
    @ModelView.button
    def validate_indemnification(cls, indemnifications):
        cls.check_ceiling(indemnifications)
        super(Indemnification, cls).validate_indemnification(indemnifications)

    @classmethod
    @ModelView.button
    def calculate(cls, indemnifications):
        super(Indemnification, cls).calculate(indemnifications)
        cls.check_ceiling(indemnifications)
