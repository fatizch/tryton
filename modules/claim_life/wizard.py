# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'IndemnificationValidateElement',
    'IndemnificationControlElement'
    ]


class IndemnificationValidateElement:
    __name__ = 'claim.indemnification.assistant.validate.element'

    covered_person = fields.Many2One(
        'party.party', 'Covered Person', readonly=True)

    @classmethod
    def from_indemnification(cls, indemnification):
        res = super(
            IndemnificationValidateElement, cls).from_indemnification(
            indemnification)
        covered_person = indemnification.service.get_covered_person()
        if covered_person:
            res['covered_person'] = covered_person.id
            res['covered_person.rec_name'] = covered_person.rec_name
        return res


class IndemnificationControlElement:
    __name__ = 'claim.indemnification.assistant.control.element'

    covered_person = fields.Many2One(
        'party.party', 'Covered Person', readonly=True)

    @classmethod
    def from_indemnification(cls, indemnification):
        res = super(
            IndemnificationControlElement, cls).from_indemnification(
            indemnification)
        covered_person = indemnification.service.get_covered_person()
        if covered_person:
            res['covered_person'] = covered_person.id
            res['covered_person.rec_name'] = covered_person.rec_name
        return res
