# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields
from trytond.pyson import Eval


__metaclass__ = PoolMeta
__all__ = [
    'IndemnificationValidateElement',
    'IndemnificationControlElement',
    'IndemnificationDefinition',
    'CreateIndemnification',
    'SelectService',
    ]


class IndemnificationValidateElement:
    __metaclass__ = PoolMeta
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
    __metaclass__ = PoolMeta
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


class IndemnificationDefinition:
    'Indemnification Definition'
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    beneficiary_extra_data = fields.Dict('extra_data',
        'Beneficiary Extra Data',
        states={'invisible': ~Eval('beneficiary_extra_data')})
    beneficiary_def = fields.Many2One('claim.beneficiary',
        'Beneficiary Definition',
        states={'invisible': ~Eval('beneficiary_def')})

    @fields.depends('beneficiary', 'beneficiary_share', 'service',
        'start_date', 'beneficiary_def')
    def on_change_beneficiary(self):
        super(IndemnificationDefinition, self).on_change_beneficiary()
        if not self.beneficiary:
            self.beneficiary_extra_data = {}
            self.beneficiary_def = None
        if not self.service:
            return
        beneficiary_def = self.service.get_beneficiary_definition_from_party(
                self.beneficiary)
        if beneficiary_def and (not hasattr(self, 'beneficiary_def') or
                beneficiary_def != self.beneficiary_def):
            self.beneficiary_extra_data = beneficiary_def.extra_data_values
            self.beneficiary_def = beneficiary_def


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    def default_definition(self, name):
        pool = Pool()
        Service = pool.get('claim.service')
        Party = pool.get('party.party')
        res = super(CreateIndemnification, self).default_definition(name)
        if res['beneficiary']:
            party = Party(res['beneficiary'])
            service = Service(res['service'])
            beneficiary_def = service.get_beneficiary_definition_from_party(
                party)
        else:
            beneficiary_def = None
        res['beneficiary_extra_data'] = \
            beneficiary_def.extra_data_values if beneficiary_def else None
        res['beneficiary_def'] = beneficiary_def.id if beneficiary_def else None
        return res

    def init_indemnification(self, indemnification):
        super(CreateIndemnification, self).init_indemnification(
            indemnification)
        if not self.definition.beneficiary_extra_data:
            return
        self.definition.beneficiary_def.extra_data_values = \
            self.definition.beneficiary_extra_data
        self.definition.beneficiary_def.save()


class SelectService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.select_service'

    covered_person = fields.Many2One('party.party', 'Covered Person',
        readonly=True, states={'invisible': ~Eval('selected_service')})

    @fields.depends('covered_person')
    def on_change_selected_service(self):
        super(SelectService, self).on_change_selected_service()
        if self.selected_service:
            self.covered_person = self.selected_service.loss.covered_person
        else:
            self.covered_person = None
