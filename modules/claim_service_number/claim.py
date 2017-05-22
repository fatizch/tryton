# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields
from .benefit import SEQUENCE_REFERENCE


__all__ = [
    'ClaimService',
    'Claim',
    ]


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    number = fields.Char('Number', states={
        'invisible': ~Eval('benefit_sequence')
        }, depends=['benefit_sequence'])
    benefit_sequence = fields.Function(fields.Reference(
            'Benefit Sequence', SEQUENCE_REFERENCE),
        'get_benefit_sequence')

    @classmethod
    def create(cls, vlist):
        created = super(ClaimService, cls).create(vlist)
        records = [x for x in created if x.benefit_sequence]
        with model.error_manager():
            for record in records:
                record.number = record.benefit.sequence.get_id(
                    record.benefit.sequence.id)
            cls.save(records)
        return created

    def get_benefit_sequence(self, name):
        if self.benefit:
            return self.benefit.sequence


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    delivered_services_numbers = fields.Function(fields.Char(
            'Delivered Services Numbers'),
        'get_delivered_services_numbers')

    def get_delivered_services_numbers(self, name=None):
        return ', '.join([x.number for x in self.delivered_services
                if x.number])
