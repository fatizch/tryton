# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import os

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch


__all__ = [
    'GenerateAgedBalance',
    ]


class GenerateAgedBalance(batch.BatchRootNoSelect):
    'Generate Aged Balace'

    __name__ = 'account.aged_balance.generate'

    logger = logging.getLogger(__name__)

    @classmethod
    def parse_params(cls, params):
        params = super(GenerateAgedBalance, cls).parse_params(params)
        params['term1'] = int(params.get('term1'))
        params['term2'] = int(params.get('term2'))
        params['term3'] = int(params.get('term3'))
        params['posted'] = bool(params.get('posted', True))
        return params

    @classmethod
    def build_context(cls, treatment_date, parameters):
        context_ = {}
        context_['term0'] = 0
        context_['term1'] = parameters.get('term1')
        context_['term2'] = parameters.get('term2')
        context_['term3'] = parameters.get('term3')
        context_['unit'] = parameters.get('unit')
        context_['type'] = parameters.get('type')
        context_['posted'] = parameters.get('posted')
        context_['date'] = treatment_date
        return context_

    @classmethod
    def check_context(cls, context_):
        pool = Pool()
        AgedBalanceContext = pool.get('account.aged_balance.context')
        ActionReport = pool.get('ir.action.report')
        report_, = ActionReport.search([
                ('report', '=', 'account_cog/aged_balance.ods'),
                ('report_name', '=', 'account.aged_balance'),
                ])
        context_['action_id'] = report_.action.id
        available_units = [x[0] for x in AgedBalanceContext.unit.selection]
        available_types = [x[0] for x in AgedBalanceContext.type.selection]
        assert context_.get('unit') in available_units, ('Invalid unit '
            '(%s not in %s)' % (context_.get('unit'), str(available_units)))
        assert context_.get('type') in available_types, ('Invalid type '
            '(%s not in %s)' % (context_.get('type'), str(available_types)))

    @classmethod
    def get_filename(cls, treatment_date, **kwargs):
        ActionReport = Pool().get('ir.action.report')
        report_, = ActionReport.search([
                ('report', '=', 'account_cog/aged_balance.ods'),
                ('report_name', '=', 'account.aged_balance'),
                ])
        return 'aged_balance-%s.%s' % (treatment_date.strftime('%Y-%m-%d'),
                report_.extension)

    @classmethod
    def get_output_dir(cls, treatment_date, **kwargs):
        return kwargs.get('output_dir')

    @classmethod
    def execute(cls, objects, ids, treatment_date, **kwargs):
        pool = Pool()
        AgedBalanceReport = pool.get('account.aged_balance', type='report')
        AgedBalance = pool.get('account.aged_balance')
        output_dir = cls.get_output_dir(treatment_date, **kwargs)
        filename = cls.get_filename(treatment_date, **kwargs)
        possible_days = kwargs.get('possible_days', None)

        possible_days = possible_days.split(',') if possible_days else []
        if not possible_days or (possible_days
                    and not str(treatment_date.day) in possible_days):
            return []

        context_ = cls.build_context(treatment_date, kwargs)
        cls.check_context(context_)
        with Transaction().set_context(**context_):
            type_, report, print_, name = AgedBalanceReport.execute(
                [x.id for x in AgedBalance.search([('balance', '!=', 0)])],
                context_)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        with open(os.path.join(output_dir, filename), 'wb') as f_:
            f_.write(report)
