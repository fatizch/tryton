# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.model import Unique
from trytond.cache import Cache

from trytond.modules.cog_utils import fields, model

__all__ = [
    'PaymentJournal',
    'JournalFailureAction',
    'JournalFailureDunning',
    'Payment',
    ]


class PaymentJournal:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.journal'

    _dunning_actions_cache = Cache('dunning_actions')

    @classmethod
    def dunning_action(cls, journal, procedure, reject_code):
        Level = Pool().get('account.dunning.level')
        journal = journal if isinstance(journal, int) else journal.id
        procedure = procedure if isinstance(procedure, int) else procedure.id
        val = cls._dunning_actions_cache.get(
            (journal, procedure, reject_code), -1)
        if val != -1:
            return Level(val) if val else None
        cls._dunning_actions_cache.set((journal, procedure, reject_code), None)
        for cur_journal in cls.search([]):
            for failure_action in cur_journal.failure_actions:
                for failure_dunning in failure_action.dunning_configurations:
                    cls._dunning_actions_cache.set((cur_journal.id,
                            failure_dunning.procedure.id,
                            failure_action.reject_reason.code),
                        failure_dunning.level.id)
        return cls.dunning_action(journal, procedure, reject_code)


class JournalFailureAction:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.journal.failure_action'

    dunning_configurations = fields.One2Many(
        'account.payment.journal.failure_action.dunning', 'failure_action',
        'Dunning Configurations', delete_missing=True)


class JournalFailureDunning(model.CoopSQL, model.CoopView):
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

    @classmethod
    def create(cls, *args, **kwargs):
        Pool().get('account.payment.journal')._dunning_actions_cache.clear()
        return super(JournalFailureDunning, cls).create(*args, **kwargs)

    @classmethod
    def write(cls, *args, **kwargs):
        Pool().get('account.payment.journal')._dunning_actions_cache.clear()
        return super(JournalFailureDunning, cls).write(*args, **kwargs)

    @classmethod
    def delete(cls, *args, **kwargs):
        Pool().get('account.payment.journal')._dunning_actions_cache.clear()
        return super(JournalFailureDunning, cls).delete(*args, **kwargs)


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    @classmethod
    def fail(cls, payments):
        super(Payment, cls).fail(payments)
        cls.fail_generate_dunnings(payments)

    @classmethod
    def fail_generate_dunnings(cls, payments):
        pool = Pool()
        Journal = pool.get('account.payment.journal')
        Dunning = pool.get('account.dunning')
        dunnings = []
        for payment in payments:
            if not payment.fail_code:
                continue
            line = payment.line
            if line is None:
                continue
            dunning_procedure = line.dunning_procedure
            if dunning_procedure is None:
                continue
            level = Journal.dunning_action(payment.journal.id,
                dunning_procedure.id, payment.fail_code)
            if not level:
                continue
            dunning = payment._set_dunning(level)
            if dunning:
                dunnings.append(dunning)
        if not dunnings:
            return
        Dunning.save(dunnings)

    def _set_dunning(self, level):
        if self.line.dunning:
            if level.sequence > self.line.dunning.level.sequence:
                self.line.dunning.level = level
                self.line.dunning.state = 'draft'
                return self.line.dunning
            return None
        return Pool().get('account.dunning')(
            line=self.line, level=level, procedure=level.procedure)
