import datetime

from trytond.modules.cog_utils import model, fields, coop_string, utils
from trytond.pyson import Eval, Bool

__all__ = [
    'ContactType',
    'ContractContact',
    ]


class ContactType(model.CoopSQL, model.CoopView):
    'Contact Type'

    __name__ = 'contract.contact.type'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class ContractContact(model._RevisionMixin, model.CoopSQL, model.CoopView):
    'Contract Contact'

    __name__ = 'contract.contact'
    _parent_name = 'contract'

    end_date = fields.Date('End Date', domain=['OR',
            ('end_date', '=', None),
            ('date', '=', None),
            ('end_date', '>=', Eval('date', datetime.date.min))],
        depends=['date'])
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        required=True, select=True)
    type = fields.Many2One('contract.contact.type', 'Type',
        ondelete='RESTRICT', required=True)
    type_code = fields.Function(
        fields.Char('Type Code'),
        'on_change_with_type_code')
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT',
        required=True)
    address = fields.Many2One('party.address', 'Address', ondelete='RESTRICT',
        domain=[('party', '=', Eval('party'))],
        depends=['party', 'is_address_required'],
        states={'required': Bool(Eval('is_address_required'))})
    is_address_required = fields.Function(
        fields.Boolean('Is Address Required', depends=['type']),
        'on_change_with_is_address_required')

    def _on_change(self):
        if self.type and self.type.code == 'subscriber':
            self.party = self.contract.subscriber
        addresses = utils.filter_list_at_date(
            utils.get_domain_instances(self, 'address'),
            self.date or self.contract.start_date)
        if len(addresses) == 1:
            self.address = addresses[0]
        elif self.address not in addresses:
            self.address = None

    @fields.depends('party', 'address', 'type', 'contract', 'date')
    def on_change_type(self):
        self._on_change()

    @fields.depends('party', 'address', 'type', 'contract', 'date')
    def on_change_party(self):
        self._on_change()

    @fields.depends('type')
    def on_change_with_is_address_required(self, name=None):
        if self.type:
            return self.type.code in ('subscriber', 'accepting_beneficiary')
        return False

    @fields.depends('type')
    def on_change_with_type_code(self, name=None):
        return self.type.code if self.type else None

    @staticmethod
    def revision_columns():
        return ['type', 'party', 'address']

    @classmethod
    def get_reverse_field_name(cls):
        return 'contact'

    def set_default_address(self, date=None):
        if not date:
            date = self.start
        if self.party and not getattr(self, 'address', None):
            self.address = utils.get_good_version_at_date(self.party,
                'addresses', date)
