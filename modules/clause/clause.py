from trytond.modules.cog_utils import model, fields, coop_string


__all__ = [
    'Clause',
    ]


class Clause(model.CoopSQL, model.CoopView):
    'Clause'

    __name__ = 'clause'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    kind = fields.Selection([('specific', 'Specific')], 'Kind')
    kind_string = kind.translated('kind')
    customizable = fields.Boolean('Customizable')
    content = fields.Text('Content')

    @classmethod
    def __setup__(cls):
        super(Clause, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    @classmethod
    def default_kind(cls):
        return 'specific'

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        if cls.search([('code',) + tuple(clause[1:])], limit=1, order=[]):
            return [('code',) + tuple(clause[1:])]
        return [(cls._rec_name,) + tuple(clause[1:])]
