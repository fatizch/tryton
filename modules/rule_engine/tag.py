from trytond.modules.coop_utils import model, fields, coop_string

__all__ = [
    'Tag',
    ]


class Tag(model.CoopSQL, model.CoopView):
    'Tag'

    __name__ = 'tag'

    code = fields.Char('Code', on_change_with=['code', 'name'], required=True)
    name = fields.Char('Name', translate=True)
    parent = fields.Many2One('tag', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('tag', 'parent', 'Childs')
    rules = fields.Many2Many('rule_engine-tag', 'tag',
        'rule_engine', 'Rules')

    @classmethod
    def _export_skips(cls):
        result = super(Tag, cls)._export_skips()
        result.add('rules')
        return result

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)
