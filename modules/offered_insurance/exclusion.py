# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.coog_core import model, fields, coog_string


__all__ = [
    'ExclusionKind',
    'ExclusionKindGroup',
    ]


class ExclusionKind(model.CoogSQL, model.CoogView):
    'Exclusion Kind'

    __name__ = 'offered.exclusion'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    text = fields.Text('Text', translate=True)
    groups = fields.Many2Many('offered.exclusion-res.group',
        'exclusion_kind', 'group', 'Groups', help='Exclusion kind groups')

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
            self.code = coog_string.slugify(self.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('name',) + tuple(clause[1:])],
            [('code',) + tuple(clause[1:])],
            ]

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.name)

    @classmethod
    def search(cls, domain, *args, **kwargs):
        if Transaction().context.get('_check_access', False):
            user = Pool().get('res.user')(Transaction().user)
            domain = ['AND', domain, ['OR', ('groups', '=', None),
                ('groups', 'in', [x.id for x in user.groups])]]
        return super(ExclusionKind, cls).search(domain, *args, **kwargs)


class ExclusionKindGroup(model.CoogSQL):
    'Exclusion Kind Group'
    __name__ = 'offered.exclusion-res.group'

    exclusion_kind = fields.Many2One('offered.exclusion',
        'Exclusion Kind', ondelete='CASCADE', required=True, select=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
        required=True, select=True)
