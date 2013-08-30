from trytond.modules.coop_utils import model, fields, coop_string

__all__ = [
    'Tag',
    ]


class Tag(model.CoopSQL, model.CoopView):
    'Tag'

    __name__ = 'rule_engine.tag'

    code = fields.Char('Code', on_change_with=['code', 'name'], required=True)
    name = fields.Char('Name')
    parent = fields.Many2One('rule_engine.tag', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('rule_engine.tag', 'parent', 'Childs')

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)
