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


class OptionDisplayer:
    __metaclass__ = PoolMeta
    __name__ = 'contract.manage_options.option_displayer'

    has_coverage_amount = fields.Boolean('Has Coverage Amount', readonly=True)
    free_coverage_amount = fields.Boolean('Free Coverage Amount',
        readonly=True)
    coverage_amount = fields.Numeric('Coverage Amount', digits=(16, 2),
        states={'invisible': ~Eval('has_coverage_amount') |
            ~Eval('free_coverage_amount')})
    coverage_amount_selection = fields.Selection('select_coverage_amounts',
        'Coverage Amount', states={'invisible': ~Eval('has_coverage_amount') |
            ~~Eval('free_coverage_amount')})

    @fields.depends('action', 'coverage_amount', 'effective_date',
        'cur_option_id', 'has_coverage_amount')
    def on_change_action(self):
        super(OptionDisplayer, self).on_change_action()
        if self.action not in ('modified', 'added'):
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

    @fields.depends('has_coverage_amount', 'free_coverage_amount',
        'coverage_amount', 'cur_option_id', 'effective_date', 'manager',
        'coverage_id')
    def select_coverage_amounts(self):
        pool = Pool()
        Option = pool.get('contract.option')
        RuleEngine = pool.get('rule_engine')
        selection, values = [('', '')], []
        if not self.has_coverage_amount:
            return selection
        if self.cur_option_id:
            option = Option(self.cur_option_id)
        else:
            option = Option(coverage=self.coverage,
                currency=self.coverage.currency,
                has_coverage_amount=self.has_coverage_amount)
        if not self.free_coverage_amount:
            with ServerContext().set_context(
                    endorsement_context=RuleEngine.build_endorsement_context(
                        self.manager, action='in_progress')):
                values = option.get_coverage_amount_rule_result(
                    self.effective_date)
            if values:
                selection += map(
                    lambda x: (str(x), option.currency.amount_as_string(x)),
                    values)
        if self.coverage_amount and self.coverage_amount not in values:
            selection.append((str(self.coverage_amount),
                    option.currency.amount_as_string(self.coverage_amount)))
        return selection

    @fields.depends('coverage_amount', 'has_coverage_amount')
    def _check_modified(self, option, version):
        modified = super(OptionDisplayer, self)._check_modified(option,
            version)
        if not modified and self.has_coverage_amount:
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
        displayer.has_coverage_amount = bool(
            option.coverage.coverage_amount_rules)
        displayer.free_coverage_amount = False
        if displayer.has_coverage_amount:
            displayer.free_coverage_amount = \
                option.coverage.coverage_amount_rules[0].free_input
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
