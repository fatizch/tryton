# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model, fields


__all__ = [
    'Clause',
    ]


class Clause(model.CodedMixin, model.CoogView):
    'Clause'

    __name__ = 'clause'
    _func_key = 'code'

    kind = fields.Selection([('specific', 'Specific')], 'Kind')
    kind_string = kind.translated('kind')
    customizable = fields.Boolean('Customizable')
    content = fields.Text('Content', translate=True)

    @classmethod
    def is_master_object(cls):
        return True

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
