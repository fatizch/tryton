from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool, Or

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    'ContractOption',
    'Beneficiary',
    ]


class Contract:
    __name__ = 'contract'

    def update_contacts_list(self):
        super(Contract, self).update_contacts_list()
        parties = []
        for cov_element in self.covered_elements:
            for option in cov_element.options:
                for benef in option.beneficiaries:
                    if benef.accepting:
                        parties.append(benef.party)
        contacts = list(getattr(self, 'contacts', []))
        self.synchronize_contacts_of_type(contacts,
            'accepting_beneficiary', parties)
        self.contacts = contacts


class ContractOption:
    __name__ = 'contract.option'

    has_beneficiary_clause = fields.Function(
        fields.Boolean('Has Beneficiary Clause'),
        'on_change_with_has_beneficiary_clause')
    beneficiary_clause = fields.Many2One('clause', 'Beneficiary Clause',
        domain=[('coverages', '=', Eval('coverage'))], states={
            'invisible': ~Eval('has_beneficiary_clause'),
            'required': (Bool(Eval('has_beneficiary_clause'))
                & ~Eval('customized_beneficiary_clause')),
            'readonly': Eval('contract_status') != 'quote',
            },
        depends=['coverage', 'has_beneficiary_clause', 'contract_status',
            'customized_beneficiary_clause'],
        ondelete='RESTRICT')
    customized_beneficiary_clause = fields.Text(
        'Customized Beneficiary Clause',
        states={
            'invisible': ~Eval('has_beneficiary_clause'),
            'required': (Eval('has_beneficiary_clause')
                & ~Eval('beneficiary_clause')),
            'readonly': Eval('contract_status') != 'quote',
            },
        depends=['has_beneficiary_clause', 'contract_status',
            'beneficiary_clause'])
    beneficiaries = fields.One2Many('contract.option.beneficiary', 'option',
        'Beneficiaries', delete_missing=True,
        states={
            'invisible': ~Eval('has_beneficiary_clause'),
            'readonly': Eval('contract_status') != 'quote',
            },
        depends=['has_beneficiary_clause', 'contract_status'])

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._error_messages.update({
                'invalid_beneficiary_shares': 'Total share for clause %s is '
                'invalid',
                'mix_share_and_none': 'Either all share must be completed or '
                'none',
                })

    @classmethod
    def view_attributes(cls):
        return super(ContractOption, cls).view_attributes() + [(
                '/form/notebook/page[@name="beneficiary_clause"]',
                'states',
                {'invisible': ~Eval('has_beneficiary_clause')}
                )]

    @classmethod
    def new_option_from_coverage(cls, coverage, product, start_date,
            end_date=None, item_desc=None):
        new_option = super(ContractOption, cls).new_option_from_coverage(
            coverage, product, start_date, end_date, item_desc)
        new_option.has_beneficiary_clause = bool(len(
                coverage.beneficiaries_clauses))
        if coverage.default_beneficiary_clause:
            new_option.beneficiary_clause = \
                coverage.default_beneficiary_clause.id
            new_option.customized_beneficiary_clause = \
                coverage.default_beneficiary_clause.content
        return new_option

    @fields.depends('beneficiary_clause')
    def on_change_coverage(self):
        super(ContractOption, self).on_change_coverage()
        if not self.coverage or not self.coverage.beneficiaries_clauses:
            self.beneficiary_clause = None
            self.customized_beneficiary_clause = ''
            self.has_beneficiary_clause = False
            return
        self.has_beneficiary_clause = True
        if (self.beneficiary_clause and self.beneficiary_clause not in
                self.coverage.beneficiaries_clauses):
            self.beneficiary_clause = self.coverage.default_beneficiary_clause
        else:
            self.beneficiary_clause = None
        if self.beneficiary_clause:
            self.customized_beneficiary_clause = \
                self.beneficiary_clause.content
        else:
            self.customized_beneficiary_clause = ''

    @fields.depends('coverage')
    def on_change_with_has_beneficiary_clause(self, name=None):
        if not self.coverage:
            return False
        return bool(self.coverage.beneficiaries_clauses)

    def check_beneficiaries(self):
        if not self.beneficiaries:
            return
        if any(getattr(x, 'share', None) is None for x in self.beneficiaries):
            if [x.share for x in self.beneficiaries
                    if getattr(x, 'share', None)]:
                self.raise_user_error('mix_share_and_none')
            else:
                return
        if sum(x.share for x in self.beneficiaries) != Decimal(1):
            self.raise_user_error('invalid_beneficiary_shares',
                (self.rec_name))

    @fields.depends('beneficiary_clause')
    def on_change_with_customized_beneficiary_clause(self):
        if not self.beneficiary_clause:
            return ''
        return self.beneficiary_clause.content

    @classmethod
    def validate(cls, options):
        super(ContractOption, cls).validate(options)
        for option in options:
            option.check_beneficiaries()


class Beneficiary(model.CoopSQL, model.CoopView):
    'Contract Beneficiary'

    __name__ = 'contract.option.beneficiary'

    option = fields.Many2One('contract.option', 'Option', required=True,
        ondelete='CASCADE', select=True)
    accepting = fields.Boolean('Accepting')
    party = fields.Many2One('party.party', 'Party', states={
            'required': Bool(Eval('accepting')),
            }, depends=['accepting'],
        ondelete='RESTRICT')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party', None))], states={
            'invisible': ~Eval('accepting'),
            'required': Bool(Eval('accepting')),
            }, depends=['party', 'accepting'], ondelete='RESTRICT')
    reference = fields.Char('Reference', states={
            'invisible': Or(Bool(Eval('party')), Bool(Eval('accepting'))),
            'required': ~Eval('party'),
            }, depends=['party', 'accepting'])
    share = fields.Numeric('Share', digits=(4, 4))

    @staticmethod
    def default_accepting():
        return True

    @fields.depends('party', 'reference')
    def on_change_with_rec_name(self, name=None):
        return self.get_rec_name(name)

    def get_rec_name(self, name=None):
        if self.party:
            return self.party.full_name
        else:
            return self.reference

    @fields.depends('accepting')
    def on_change_accepting(self):
        if not self.accepting:
            self.party = None
            self.address = None
        else:
            self.reference = ''
