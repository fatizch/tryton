# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.coog_core import model, fields


__all__ = [
    'ExclusionKind',
    'ExclusionKindGroup',
    ]


class ExclusionKind(model.CodedMixin, model.CoogView):
    'Exclusion Kind'

    __name__ = 'offered.exclusion'

    text = fields.Text('Text', translate=True)
    groups = fields.Many2Many('offered.exclusion-res.group',
        'exclusion_kind', 'group', 'Groups', help='Exclusion kind groups')

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
