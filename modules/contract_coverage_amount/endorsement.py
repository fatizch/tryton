# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields

__all__ = [
    'OptionDisplayer',
    ]


class OptionDisplayer(metaclass=PoolMeta):
    __name__ = 'contract.manage_options.option_displayer'

    coverage_amount_mode = fields.Char('Coverage Amount Mode')
    coverage_amount_label = fields.Char('Coverage Amount Label')
    coverage_amount = fields.Numeric('Coverage Amount', digits=(16, 2),
        states={
            'invisible': Eval('coverage_amount_mode') == 'selection',
            'readonly': Eval('coverage_amount_mode') == 'calculated_amount',
            })
    coverage_amount_selection = fields.Selection('select_coverage_amounts',
        'Coverage Amount', states={
            'invisible': Eval('coverage_amount_mode') != 'selection',
            })

    @fields.depends('action', 'coverage_amount', 'effective_date',
        'cur_option_id', 'coverage_amount_mode')
    def on_change_action(self):
        super(OptionDisplayer, self).on_change_action()
        if self.action not in ('modified', 'added'):
            if self.coverage_amount_mode != 'calculated_amount':
                self.coverage_amount = Pool().get('contract.option')(
                    self.cur_option_id).get_version_at_date(
                    self.effective_date).coverage_amount
            self.coverage_amount_selection = str(self.coverage_amount or '')

    @fields.depends('coverage_amount_selection', methods=['on_change_action'])
    def on_change_coverage_amount_selection(self):
        self.coverage_amount = Decimal(self.coverage_amount_selection or 0)
        self.update_action()

    @fields.depends(methods=['on_change_action'])
    def on_change_coverage_amount(self):
        self.coverage_amount_selection = str(self.coverage_amount or '')
        self.update_action()

    @fields.depends('coverage_amount_mode', 'coverage_amount', 'cur_option_id',
        'effective_date', 'manager', 'coverage_id')
    def select_coverage_amounts(self):
        pool = Pool()
        Option = pool.get('contract.option')
        RuleEngine = pool.get('rule_engine')
        selection, values = [('', '')], []
        if self.coverage_amount_mode is None:
            return selection
        if self.cur_option_id:
            option = Option(self.cur_option_id)
        else:
            option = Option(coverage=self.coverage,
                currency=self.coverage.currency,
                coverage_amount_mode=self.coverage_amount_mode)
        if self.coverage_amount_mode == 'selection':
            with ServerContext().set_context(
                    endorsement_context=RuleEngine.build_endorsement_context(
                        self.manager, action='in_progress')):
                values = option.get_coverage_amount_rule_result(
                    self.effective_date)
            if values:
                selection += [(str(x), option.currency.amount_as_string(x))
                    for x in values]
        if self.coverage_amount and self.coverage_amount not in values:
            selection.append((str(self.coverage_amount),
                    option.currency.amount_as_string(self.coverage_amount)))
        return selection

    @fields.depends('coverage_amount', 'coverage_amount_mode')
    def _check_modified(self, option, version):
        modified = super(OptionDisplayer, self)._check_modified(option,
            version)
        if not modified and self.coverage_amount_mode is not None:
            modified = self.coverage_amount != version.coverage_amount
        return modified

    @classmethod
    def _option_fields_to_extract(cls):
        result = super(OptionDisplayer, cls)._option_fields_to_extract()
        result['contract.option.version'].append('coverage_amount')
        return result

    @classmethod
    def new_displayer(cls, option, effective_date):
        displayer = super(OptionDisplayer, cls).new_displayer(option,
            effective_date)
        displayer.coverage_amount_mode = option.coverage_amount_mode
        displayer.coverage_amount_label = option.coverage_amount_label
        if displayer.coverage_amount_mode == 'calculated_amount':
            displayer.coverage_amount = option.get_coverage_amount_rule_result(
                effective_date)
        else:
            displayer.coverage_amount = getattr(
                option.get_version_at_date(effective_date), 'coverage_amount',
                None)
        displayer.coverage_amount_selection = str(displayer.coverage_amount
             or '')
        return displayer

    def to_version(self, previous_version=None):
        version = super(OptionDisplayer, self).to_version(previous_version)
        version.coverage_amount = getattr(self, 'coverage_amount', None)
        return version

    def update_from_new_option(self, new_option):
        super(OptionDisplayer, self).update_from_new_option(new_option)
        self.coverage_amount = getattr(new_option, 'coverage_amount', {})
