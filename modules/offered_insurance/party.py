# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pyson import Eval, Not, Bool

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.party_cog.party import STATES_COMPANY

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    'Insurer',
    'InsurerDelegation',
    ]


class Party:
    __name__ = 'party.party'

    insurer_role = fields.One2Many('insurer', 'party', 'Insurer', size=1,
        states={'invisible': ~Eval('is_insurer', False) | Not(STATES_COMPANY)},
        depends=['is_insurer', 'is_person'])
    is_insurer = fields.Function(
        fields.Boolean('Is Insurer',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ('/form/notebook/page[@id="role"]/notebook/page[@id="insurer"]',
                'states', {'invisible': Bool(~Eval('is_insurer'))}),
            ]

    @fields.depends('is_insurer')
    def on_change_is_insurer(self):
        self._on_change_is_actor('is_insurer')

    def get_summary_content(self, label, at_date=None, lang=None):
        res = super(Party, self).get_summary_content(label, at_date, lang)
        if self.insurer_role:
            res[1].append(coog_string.get_field_summary(self, 'insurer_role',
                True, at_date, lang))
        return res

    def get_rec_name(self, name):
        if self.is_insurer:
            return self.name
        else:
            return super(Party, self).get_rec_name(name)


class Insurer(model.CoogView, model.CoogSQL):
    'Insurer'

    __name__ = 'insurer'
    _rec_name = 'party'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    party = fields.Many2One('party.party', 'Insurer', ondelete='RESTRICT',
        required=True)
    delegations = fields.One2Many('insurer.delegation', 'insurer',
        'Insurer Delegations', delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(Insurer, cls).__setup__()
        cls._error_messages.update({
                'missing_generic_delegation': 'There must be at least one '
                '"generic" delegation rule for %s.',
                })

    @classmethod
    def validate(cls, insurers):
        super(Insurer, cls).validate(insurers)
        with model.error_manager():
            cls.check_delegations(insurers)

    @classmethod
    def check_delegations(cls, insurers):
        for insurer in insurers:
            if not any(x.family == 'generic' for x in insurer.delegations):
                insurer.append_functional_error('missing_generic_delegation',
                    (insurer.party.rec_name,))

    @classmethod
    def default_delegations(cls):
        return [{
                'family': 'generic',
                }]

    def get_func_key(self, name):
        return self.party.code

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def search_func_key(cls, name, clause):
        return [('party.code',) + tuple(clause[1:])]

    def get_summary_content(self, labelTrue, at_date=None, lang=None):
        return (self.rec_name, 'X')

    def get_rec_name(self, name):
        return (self.party.rec_name
            if self.party else super(Insurer, self).get_rec_name(name))

    def get_delegation(self, family):
        generic = None
        for elem in self.delegations:
            if elem.family == 'generic':
                generic = elem
            elif elem.family == family:
                return elem
        return generic


class InsurerDelegation(model.CoogView, model.CoogSQL):
    'Insurer Delegation'

    __name__ = 'insurer.delegation'

    insurer = fields.Many2One('insurer', 'Insurer', required=True,
        ondelete='CASCADE', select=True)
    family = fields.Selection([], 'Family')

    @classmethod
    def __setup__(cls):
        super(InsurerDelegation, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('family_uniq', Unique(t, t.insurer, t.family),
                'There can be only one delegation per insurance family.'),
            ]
        cls._delegation_flags = []

    @classmethod
    def __post_setup__(cls):
        cls.family.selection = Pool().get(
            'offered.option.description').family.selection
        super(InsurerDelegation, cls).__post_setup__()

    @classmethod
    def create(cls, vlist):
        result = super(InsurerDelegation, cls).create(vlist)
        Pool().get('offered.option.description')._insurer_flags_cache.clear()
        return result

    @classmethod
    def write(cls, *args):
        super(InsurerDelegation, cls).write(*args)
        Pool().get('offered.option.description')._insurer_flags_cache.clear()

    @classmethod
    def delete(cls, instances):
        super(InsurerDelegation, cls).delete(instances)
        Pool().get('offered.option.description')._insurer_flags_cache.clear()

    @classmethod
    def default_family(cls):
        return 'generic'

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        to_migrate = not TableHandler.table_exist(cls._table)

        super(InsurerDelegation, cls).__register__(module)

        if not to_migrate:
            return
        insurer = Pool().get('insurer').__table__()
        delegation = cls.__table__()
        cursor.execute(*delegation.insert(columns=[delegation.insurer,
                    delegation.family],
                values=insurer.select(insurer.id, Literal('generic'))))
