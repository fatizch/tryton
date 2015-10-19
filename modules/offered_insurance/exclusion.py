from trytond.model import Unique

from trytond.modules.cog_utils import model, fields, coop_string


__all__ = [
    'ExclusionKind',
    ]


class ExclusionKind(model.CoopSQL, model.CoopView):
    'Exclusion Kind'

    __name__ = 'offered.exclusion'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    text = fields.Text('Text', translate=True)

    @classmethod
    def __setup__(cls):
        super(ExclusionKind, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('name', 'code')
    def on_change_name(self):
        if not self.code:
            self.code = coop_string.slugify(self.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('name',) + tuple(clause[1:])],
            [('code',) + tuple(clause[1:])],
            ]

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.name)
