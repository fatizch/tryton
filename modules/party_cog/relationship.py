from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields, coop_string, export

__metaclass__ = PoolMeta
__all__ = [
    'RelationType',
    'PartyRelation',
    'PartyRelationAll',
    ]


class RelationType(export.ExportImportMixin):
    __name__ = 'party.relation.type'

    code = fields.Char('Code', required=True)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class PartyRelation:
    __name__ = 'party.relation'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


class PartyRelationAll(PartyRelation):
    __name__ = 'party.relation.all'

    def get_synthesis_rec_name(self, name):
        return '%s: %s' % (self.type.rec_name, self.to.rec_name)
