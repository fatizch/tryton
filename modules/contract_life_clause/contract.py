from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    'ContractOption',
    'Beneficiary',
    ]


class Contract:
    __name__ = 'contract'

    def update_contacts(self):
        super(Contract, self).update_contacts()
        pool = Pool()
        Contact = pool.get('contract.contact')
        ContactType = pool.get('contract.contact.type')
        accepting_benefs = []
        benef_parties = []
        contact_type, = ContactType.search(
            [('code', '=', 'accepting_beneficiary')], limit=1, order=[])
        for cov_element in self.covered_elements:
            for option in cov_element.options:
                for benef in option.beneficiaries:
                    if not benef.accepting:
                        continue
                    accepting_benefs.append(benef)
                    benef_parties.append(benef.party)
        contact_parties = [x.party for x in self.contacts
            if x.type == contact_type]

        to_del = []
        for contact in self.contacts:
            if (contact.type == contact_type
                    and contact.party not in benef_parties):
                to_del.append(contact)
        Contact.delete(to_del)
        self.contacts = list(getattr(self, 'contacts', []))
        for benef in accepting_benefs:
            if benef.party in contact_parties:
                continue
            contact = Contact(type=contact_type, party=benef.party,
                address=benef.address)
            self.contacts.append(contact)


class ContractOption:
    __name__ = 'contract.option'

    has_beneficiary_clause = fields.Function(
        fields.Boolean('Has Beneficiary Clause'),
        'on_change_with_has_beneficiary_clause')
    beneficiary_clause = fields.Many2One('clause', 'Beneficiary Clause',
        domain=[('coverages', '=', Eval('coverage'))], states={
            'invisible': ~Eval('has_beneficiary_clause'),
            'required': Bool(Eval('has_beneficiary_clause')),
            'readonly': Eval('contract_status') != 'quote',
            },
        depends=['coverage', 'has_beneficiary_clause', 'contract_status'],
        ondelete='RESTRICT')
    customized_beneficiary_clause = fields.Text(
        'Customized Beneficiary Clause',
        states={
            'invisible': ~Eval('has_beneficiary_clause'),
            'readonly': Eval('contract_status') != 'quote',
            },
        depends=['has_beneficiary_clause', 'contract_status'])
    beneficiaries = fields.One2Many('contract.option.beneficiary', 'option',
        'Beneficiaries',
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
    def new_option_from_coverage(cls, coverage, product, start_date=None,
            end_date=None, item_desc=None):
        new_option = super(ContractOption, cls).new_option_from_coverage(
            coverage, product, start_date, end_date, item_desc)
        new_option.has_beneficiary_clause = len(coverage.beneficiaries_clauses)
        if coverage.default_beneficiary_clause:
            new_option.beneficiary_clause = \
                coverage.default_beneficiary_clause.id
            new_option.customized_beneficiary_clause = \
                coverage.default_beneficiary_clause.content
        return new_option

    @fields.depends('coverage')
    def on_change_with_beneficiary_clause(self, name=None):
        if (not self.coverage
                or not self.coverage.default_beneficiary_clause):
            return
        return self.coverage.default_beneficiary_clause.id

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
        ondelete='CASCADE')
    accepting = fields.Boolean('Accepting')
    party = fields.Many2One('party.party', 'Party', states={
            'invisible': ~Eval('accepting'),
            'required': Bool(Eval('accepting')),
            }, depends=['accepting'],
        ondelete='RESTRICT')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party', None))], states={
            'invisible': ~Eval('accepting'),
            'required': Bool(Eval('accepting')),
            }, depends=['party', 'accepting'], ondelete='RESTRICT')
    reference = fields.Char('Reference', states={
            'invisible': Bool(Eval('accepting')),
            'required': ~Eval('accepting'),
            })
    share = fields.Numeric('Share', digits=(4, 4))

    @fields.depends('party', 'reference')
    def on_change_with_rec_name(self, name=None):
        return self.get_rec_name(name)

    def get_rec_name(self, name=None):
        if self.party:
            return self.party.rec_name
        else:
            return self.reference

    @fields.depends('accepting')
    def on_change_accepting(self):
        if not self.accepting:
            self.party = None
            self.address = None
        else:
            self.reference = ''
