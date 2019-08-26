# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields
from trytond.modules.endorsement.endorsement import relation_mixin


__all__ = [
    'Clause',
    'EndorsementContract',
    'EndorsementClause',
    ]


class Clause(object, metaclass=PoolMeta):
    _history = True
    __name__ = 'contract.clause'


class EndorsementContract(metaclass=PoolMeta):
    __name__ = 'endorsement.contract'

    clauses = fields.One2Many('endorsement.contract.clause',
        'contract_endorsement', 'Clause Endorsement', delete_missing=True)

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        contract_idx = order.index('contract')
        order.insert(contract_idx + 1, 'contract.clause')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        for contract in instances['contract']:
            instances['contract.clause'] += contract.clauses

    def get_endorsement_summary(self, name):
        result = super(EndorsementContract, self).get_endorsement_summary(name)
        clause_summary = [x.get_diff('contract.clause', x.clause)
            for x in self.clauses]
        if clause_summary:
            result[1].append([
                    gettext('endorsement_clause.msg_clause_modifications'),
                    clause_summary])
        return result

    def apply_values(self):
        values = super(EndorsementContract, self).apply_values()
        clauses = []
        for clause in self.clauses:
            clauses.append(clause.apply_values())
        if clauses:
            values['clauses'] = clauses
        return values


class EndorsementClause(relation_mixin('endorsement.contract.clause.field',
            'clause', 'contract.clause', 'Clause'),
        model.CoogSQL, model.CoogView, metaclass=PoolMeta):
    'Endorsement Clause'
    __name__ = 'endorsement.contract.clause'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Contract Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementClause, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

    def get_rec_name(self, name):
        if self.clause:
            return self.clause.rec_name
        Clause = Pool().get('contract.clause')
        return gettext(
            'endorsement_clause.msg_new_clause',
            name=Clause(**self.values).get_rec_name(None))

    @classmethod
    def _ignore_fields_for_matching(cls):
        return set(['contract'])
