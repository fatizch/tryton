# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args


__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('claim')
    def _re_claim_declaration_date(cls, args):
        return args['claim'].declaration_date

    @classmethod
    @check_args('loss')
    def _re_loss_start_date(cls, args):
        return args['loss'].start_date

    @classmethod
    @check_args('loss')
    def _re_loss_end_date(cls, args):
        return args['loss'].end_date

    @classmethod
    @check_args('claim')
    def _re_first_loss_start_date(cls, args):
        if args['claim'].losses:
            return args['claim'].losses[0].start_date

    @classmethod
    @check_args('claim', 'loss')
    def _re_last_loss_end_date(cls, args):
        res = datetime.date.min
        current_loss = args['loss']
        for loss in args['claim'].losses:
            if (current_loss.loss_desc == loss.loss_desc and
                    loss != current_loss):
                res = max(loss.end_date or datetime.date.min, res)
        return res if res != datetime.date.min else None

    @classmethod
    @check_args('loss')
    def _re_loss_desc_code(cls, args):
        return args['loss'].loss_desc.code

    @classmethod
    @check_args('loss')
    def _re_event_desc_code(cls, args):
        return args['loss'].event_desc.code
