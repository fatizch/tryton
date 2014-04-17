from trytond.modules.cog_utils import model, fields, coop_string


__all__ = [
    'Clause',
    ]


class Clause(model.CoopSQL, model.CoopView):
    'Clause'

    __name__ = 'clause'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    kind = fields.Selection([('specific', 'Specific')], 'Kind')
    customizable = fields.Boolean('Customizable')
    content = fields.Text('Content')

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def default_kind(cls):
        return 'specific'

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        if cls.search([('code',) + tuple(clause[1:])], limit=1):
            return [('code',) + tuple(clause[1:])]
        return [(cls._rec_name,) + tuple(clause[1:])]
