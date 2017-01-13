# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If, Bool, Len

from trytond.modules.coog_core import fields

__all__ = [
    'UnderwritingDecisionType',
    'Underwriting',
    ]


class UnderwritingDecisionType:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting.decision.type'

    @classmethod
    def __setup__(cls):
        super(UnderwritingDecisionType, cls).__setup__()
        cls.model.selection.append(('claim', 'Claim'))
        cls.model.selection.append(('claim.service', 'Claim Service'))


class Underwriting:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting'

    insurers = fields.Function(
        fields.Many2Many('insurer', None, None, 'Insurers'),
        'get_insurers')
    insurers_names = fields.Function(
        fields.Char('Insurers'),
        'get_insurers_names')

    def get_insurers(self, name):
        return list(set([x.service.option.coverage.insurer.id
                    for x in self.results if x.service and x.service.option]))

    def get_insurers_names(self, name):
        return ', '.join(x.rec_name for x in self.insurers)

    @classmethod
    def __setup__(cls):
        super(Underwriting, cls).__setup__()
        cls.on_object.selection.append(('claim', 'Claim'))

    def add_document(self, document_desc):
        line = super(Underwriting, self).add_document(document_desc)
        if self.on_object.__name__ == 'claim':
            line.claim = self.on_object
        return line


class UnderwritingResult:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting.result'

    claim = fields.Function(
        fields.Many2One('claim', 'Claim', states={
                'invisible': ~Eval('is_claim'),
                'readonly': Len(Eval('possible_claims', [])) <= 1,
                },
            domain=[If(Bool(Eval('is_claim')),
                    ['id', 'in', Eval('possible_claims')], [])],
            depends=['is_claim', 'possible_claims']),
        'get_claim', 'setter_void')
    service = fields.Function(
        fields.Many2One('claim.service', 'Service', states={
                'invisible': ~Eval('is_claim') | ~Eval('claim'),
                'readonly': Eval('underwriting_state') != 'draft'},
            domain=[('claim', '=', Eval('claim'))],
            depends=['claim', 'is_claim', 'underwriting_state']),
        'get_service', 'setter_void')
    is_claim = fields.Function(
        fields.Boolean('Is Claim', states={'invisible': True}),
        'on_change_with_is_claim')
    possible_claims = fields.Function(
        fields.Many2Many('claim', None, None, 'Possible claims'),
        'get_possible_claims')

    @classmethod
    def __setup__(cls):
        super(UnderwritingResult, cls).__setup__()
        cls.target.states['readonly'] = cls.target.states.get('readonly',
            False) | Bool(Eval('is_claim'))
        cls.target.depends += ['is_claim']

    @fields.depends('claim', 'is_claim', 'service', 'target')
    def on_change_claim(self):
        if self.is_claim:
            if not self.service or self.service.claim != self.claim:
                self.target = self.claim
                self.target_model = 'claim'
                self.service = None

    @fields.depends('claim', 'is_claim', 'service', 'target')
    def on_change_service(self):
        if self.is_claim:
            if self.service:
                self.target = self.service
                self.target_model = 'claim.service'
                self.claim = self.service.claim
            else:
                self.target = self.claim
                self.target_model = 'claim'

    @fields.depends('underwriting')
    def on_change_with_is_claim(self, name=None):
        if self.underwriting and self.underwriting.on_object:
            return self.underwriting.on_object.__name__ == 'claim'

    @fields.depends('claim', 'is_claim', 'target', 'underwriting')
    def on_change_underwriting(self):
        super(UnderwritingResult, self).on_change_underwriting()
        self.is_claim = self.on_change_with_is_claim()
        if self.is_claim:
            self.claim = self.underwriting.on_object
            self.possible_claims = [self.claim]
            if not self.target:
                self.target = self.claim
                self.target_model = 'claim'

    def get_claim(self, name):
        if not self.is_claim:
            return None
        if self.service:
            return self.service.claim.id
        return self.target.id

    def get_possible_claims(self, name):
        if self.is_claim:
            return [self.claim.id]
        return []

    def get_service(self, name):
        if self.target.__name__ == 'claim.service':
            return self.target.id
