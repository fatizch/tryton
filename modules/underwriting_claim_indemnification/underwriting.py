# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'UnderwritingDecisionType',
    'UnderwritingResult',
    ]


class UnderwritingDecisionType:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting.decision.type'

    reduction_percentage = fields.Numeric('Reduction Percentage',
        digits=(16, 2), domain=['OR', [('reduction_percentage', '=', None)],
            [('reduction_percentage', '>=', 0),
                ('reduction_percentage', '<=', 1)]],
        states={'invisible': Eval('decision') != 'reduce_indemnification',
            'required': Eval('decision') == 'reduce_indemnification'},
        depends=['decision'])

    @classmethod
    def __setup__(cls):
        super(UnderwritingDecisionType, cls).__setup__()
        cls.decision.selection += [
            ('block_indemnification', 'Block Indemnifications'),
            ('reduce_indemnification', 'Reduce Indemnifications'),
            ]

    @fields.depends('decision', 'reduction_percentage')
    def on_change_decision(self):
        if self.decision != 'reduce_indemnification':
            self.reduction_percentage = 0
        elif not self.reduction_percentage:
            self.reduction_percentage = Decimal('0.5')


class UnderwritingResult:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting.result'

    last_indemnification_date = fields.Function(
        fields.Date('Last Indemnification Date', states={
                'invisible': ~Eval('service')}, depends=['service']),
        'on_change_with_last_indemnification_date')

    @classmethod
    def __setup__(cls):
        super(UnderwritingResult, cls).__setup__()
        cls._error_messages.update({
                'will_schedule': 'This action will schedule the following '
                'indemnifications: \n\n%s',
                'will_reject': 'This action will reject the following '
                'indemnifications: \n\n%s, because the underwriting decision '
                'implies a reduction.',
                'rejected_after_reduction': 'Rejected after reduction decision',
                })

    @fields.depends('service')
    def on_change_with_last_indemnification_date(self, name=None):
        if not self.service:
            return None
        return self.service.last_indemnification_date

    @classmethod
    def do_finalize(cls, results):
        super(UnderwritingResult, cls).do_finalize(results)
        cls.handle_indemnifications(results)

    @classmethod
    def handle_indemnifications(cls, results):
        sorted_indemnifications = cls._get_impacted_indemnifications(results)
        cls.reject_indemnifications(
            sorted_indemnifications.get('reduce_indemnification', []))
        cls.schedule_indemnifications(
            sorted_indemnifications.get('nothing', []))

    @classmethod
    def _get_impacted_indemnifications(cls, results):
        impacted = defaultdict(list)
        for res in results:
            if not res.service or not res.final_decision:
                continue
            for indemnification in res.service.indemnifications:
                if indemnification.status != 'calculated':
                    continue
                try:
                    decision = \
                        next(indemnification.service.underwritings_at_date(
                                indemnification.start_date,
                                indemnification.end_date))
                except StopIteration:
                    continue
                if decision.state != 'finalized':
                    continue
                decision = res.final_decision.decision
                impacted[decision].append(indemnification)
        return impacted

    @classmethod
    def reject_indemnifications(cls, indemnifications):
        if not indemnifications:
            return
        Indemnification = Pool().get('claim.indemnification')
        cls.raise_user_warning('will_reject_' + ','.join((str(x.id) for
                x in indemnifications)), 'will_reject',
               '\n'.join(x.rec_name for x in indemnifications))
        to_reject = {x: {'note': cls.raise_user_error(
            'rejected_after_reduction', raise_exception=False)}
            for x in indemnifications}
        Indemnification.reject_indemnification(to_reject)

    @classmethod
    def schedule_indemnifications(cls, indemnifications):
        if not indemnifications:
            return
        Indemnification = Pool().get('claim.indemnification')
        cls.raise_user_warning('will_schedule_' + ','.join((str(x.id) for
                x in indemnifications)), 'will_schedule',
               '\n'.join(x.rec_name for x in indemnifications))
        Indemnification.schedule_indemnifications(indemnifications)
