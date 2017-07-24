# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.model import Unique

from trytond.modules.coog_core import fields, model

__all__ = [
    'JournalFailureAction',
    'JournalFailureDunning',
    'Payment',
    ]


class JournalFailureAction:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.journal.failure_action'

    dunning_configurations = fields.One2Many(
        'account.payment.journal.failure_action.dunning', 'failure_action',
        'Dunning Configurations', delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        cls._fail_actions_order += ['generate_dunnings']

    def get_actions_for_matching_reject_number(self, **kwargs):
        actions = super(JournalFailureAction,
            self).get_actions_for_matching_reject_number(**kwargs)
        payments = kwargs.get('payments', [])
        procedures = set([p.line.dunning_procedure for p in payments if p.line])
        if len(procedures) == 1:
            for dunning_configuration in self.dunning_configurations:
                if dunning_configuration.procedure != list(procedures)[0]:
                    continue
                actions.append(('generate_dunnings',
                        dunning_configuration.level))
        return actions


class JournalFailureDunning(model.CoogSQL, model.CoogView):
    'Journal Failure Dunning Configuration'

    __name__ = 'account.payment.journal.failure_action.dunning'

    failure_action = fields.Many2One('account.payment.journal.failure_action',
        'Action', select=True, required=True, ondelete='CASCADE')
    procedure = fields.Many2One('account.dunning.procedure', 'Procedure',
        required=True, ondelete='CASCADE')
    level = fields.Many2One('account.dunning.level', 'Level',
        domain=[('procedure', '=', Eval('procedure'))], depends=['procedure'],
        required=True, ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(JournalFailureDunning, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('unique_proc_per_action',
                Unique(t, t.failure_action, t.procedure),
                'Only one configuration per dunning procedure'),
            ]


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    @classmethod
    def fail_generate_dunnings(cls, *args):
        pool = Pool()
        Dunning = pool.get('account.dunning')
        dunnings = []
        for payments, level in args:
            for payment in payments:
                dunning = payment._set_dunning(level)
                if dunning:
                    dunnings.append(dunning)
        if not dunnings:
            return
        Dunning.save(dunnings)

    def _set_dunning(self, level):
        if self.line.dunnings:
            dunning = self.line.dunnings[-1]
            if level.sequence > dunning.level.sequence:
                dunning.level = level
                dunning.state = 'draft'
                return dunning
            return None
        return Pool().get('account.dunning')(
            line=self.line, level=level, procedure=level.procedure)
