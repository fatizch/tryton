# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond import backend
from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.model.exceptions import ValidationError
from trytond.transaction import Transaction
from trytond.pyson import Eval, Not, Bool

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.party_cog.party import STATES_COMPANY


__all__ = [
    'Party',
    'Insurer',
    'InsurerDelegation',
    'PartyReplace',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    insurer_role = fields.One2Many('insurer', 'party', 'Insurer',
        states={'invisible': ~Eval('is_insurer', False) | Not(STATES_COMPANY)},
        depends=['is_insurer', 'is_person'])
    is_insurer = fields.Function(
        fields.Boolean('Is Insurer',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._role_fields.append('is_insurer')

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ('/form/notebook/page[@id="role"]/notebook/page[@id="insurer"]',
                'states', {'invisible': Bool(~Eval('is_insurer'))}),
            ]

    def _dunning_allowed(self):
        if self.is_insurer:
            return False
        return super(Party, self)._dunning_allowed()

    @classmethod
    def non_customer_clause(cls, clause):
        domain = super(Party, cls).non_customer_clause(clause)
        additional_clause = []
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[2]:
            if clause[1] == '!=' and domain:
                additional_clause += ['OR']
            additional_clause += [('is_insurer', clause[1], False)]
        else:
            if reverse[clause[1]] == '!=' and domain:
                additional_clause += ['OR']
            additional_clause += [('is_insurer', reverse[clause[1]], False)]
        return additional_clause + domain

    @classmethod
    def search_dunning_allowed(cls, name, clause):
        return super(Party, cls).search_dunning_allowed(name, clause) + \
            cls.non_customer_clause(clause)

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
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    party = fields.Many2One('party.party', 'Insurer', ondelete='RESTRICT',
        required=True, domain=[('is_person', '=', False)])
    delegations = fields.One2Many('insurer.delegation', 'insurer',
        'Insurer Delegations', delete_missing=True)
    options = fields.One2Many('offered.option.description', 'insurer',
        'Insurer', delete_missing=True, readonly=True,
        target_not_required=True)

    @classmethod
    def create(cls, values):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        # party is required, so it has to be in there
        parties = [x['party'] for x in values]
        existing = cls.search([('party', 'in', parties)])
        if existing and cls._should_raise_warning_if_possible_duplicate():
            key = 'possible_insurer_duplicate_%s' % '_'.join(
                str(x.id) for x in existing[:10])
            if Warning.check(key):
                raise UserWarning(key, gettext(
                        'offered_insurance.msg_possible_insurer_duplicate',
                        names='\n'.join(
                            {x.party.name for x in existing[:10]})))
        return super(Insurer, cls).create(values)

    @classmethod
    def _should_raise_warning_if_possible_duplicate(cls):
        return True

    @classmethod
    def validate(cls, insurers):
        super(Insurer, cls).validate(insurers)
        with model.error_manager():
            cls.check_delegations(insurers)

    @classmethod
    def _export_skips(cls):
        return super(Insurer, cls)._export_skips() | {'options'}

    @classmethod
    def check_delegations(cls, insurers):
        for insurer in insurers:
            if not any(x.insurance_kind == '' for x in insurer.delegations):
                insurer.append_functional_error(
                    ValidationError(gettext(
                            'offered_insurance.msg_missing_default_delegation',
                            party=insurer.party.rec_name)))

    @classmethod
    def default_delegations(cls):
        return [{
                'insurance_kind': '',
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

    def get_delegation(self, insurance_kind):
        generic = None
        for elem in self.delegations:
            if elem.insurance_kind == '':
                generic = elem
            elif elem.insurance_kind == insurance_kind:
                return elem
        return generic


class InsurerDelegation(model.CoogView, model.CoogSQL):
    'Insurer Delegation'

    __name__ = 'insurer.delegation'

    insurer = fields.Many2One('insurer', 'Insurer', required=True,
        ondelete='CASCADE', select=True)
    insurance_kind = fields.Selection([], 'Insurance Kind')

    @classmethod
    def __setup__(cls):
        super(InsurerDelegation, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('insurance_kind_uniq', Unique(t, t.insurer, t.insurance_kind),
                'There can be only one delegation per insurance kind.'),
            ]
        cls._delegation_flags = []

    @classmethod
    def __post_setup__(cls):
        cls.insurance_kind.selection = Pool().get(
            'offered.option.description').insurance_kind.selection
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
    def default_insurance_kind(cls):
        return ''

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
                    delegation.insurance_kind],
                values=insurer.select(insurer.id, Literal(''))))


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('insurer', 'party'),
            ]
