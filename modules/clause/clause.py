# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import Unique

from trytond.modules.coog_core import model, fields, coog_string


__all__ = [
    'Clause',
    ]


class Clause(model.CoogSQL, model.CoogView):
    'Clause'

    __name__ = 'clause'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    kind = fields.Selection([('specific', 'Specific')], 'Kind')
    kind_string = kind.translated('kind')
    customizable = fields.Boolean('Customizable')
    content = fields.Text('Content', translate=True)

    @classmethod
    def __setup__(cls):
        super(Clause, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

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
