from trytond.modules.coop_utils import model, fields, coop_string

__all__ = [
    'Tag',
    ]


class Tag(model.CoopSQL, model.CoopView):
    'Tag'

    __name__ = 'rule_engine.tag'

    code = fields.Char('Code', on_change_with=['code', 'name'])
    name = fields.Char('Name')

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)
