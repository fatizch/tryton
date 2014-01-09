from trytond.pool import PoolMeta

from trytond.modules.cog_utils import coop_date, fields, model, coop_string

__metaclass__ = PoolMeta

__all__ = [
    'GroupParty',
    'Party',
    ]


class GroupParty(model.CoopSQL, model.CoopView):
    'Group Party'

    __name__ = 'party.group'

    code = fields.Char('Code', required=True, on_change_with=['code', 'name'])
    name = fields.Char('Name')
    parties = fields.One2Many('party.party', 'group', 'Parties',
        add_remove=[('is_company', '=', True)])

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class Party:
    __name__ = 'party.party'

    group = fields.Many2One('party.group', 'Group')

    def get_rate_note_dates(self, from_date):
        return coop_date.get_good_period_from_frequency(from_date, 'quarterly')
