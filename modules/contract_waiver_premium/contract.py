# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or
from trytond.modules.coog_core import fields, model


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract:
    __name__ = 'contract'

    with_waiver_of_premium = fields.Function(
        fields.Boolean('With Waiver Of Premium'),
        'get_with_waiver_of_premium')
    waivers = fields.One2Many('contract.waiver_premium', 'contract',
        'Waivers Of Premium',
        states={'invisible': ~Eval('waivers')}, readonly=True,
        delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'create_waiver': {
                    'invisible': Or(~Eval('with_waiver_of_premium'),
                        Eval('status') != 'active'),
                    },
                })

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '/form/group[@id="waiver_buttons"]',
                'states',
                {'invisible': True}
                )]

    @classmethod
    @model.CoogView.button_action(
        'contract_waiver_premium.act_create_waiver_wizard')
    def create_waiver(cls, contracts):
        pass

    def get_with_waiver_of_premium(self, name):
        all_options = self.get_all_options()
        return any((x.with_waiver_of_premium for x in all_options))

    def finalize_invoices_lines(self, lines):
        super(Contract, self).finalize_invoices_lines(lines)
        self.add_waiver_invoice_lines(lines)

    def add_waiver_invoice_lines(self, lines):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        InvoiceLineDetail = pool.get('account.invoice.line.detail')
        Waiver = pool.get('contract.waiver_premium')
        line_fields = Waiver.get_waiver_line_fields()
        line_detail_fields = Waiver.get_waiver_line_detail_fields()
        for line in list(lines):
            option = None
            if line.details and line.details[0].premium:
                option = line.details[0].premium.option
            if not option:
                continue
            waiver_option = option.get_waiver_option_for_invoice_line(line)
            if not waiver_option:
                continue
            waiver_line = InvoiceLine(**{x: getattr(line, x, None)
                    for x in line_fields})
            waiver_line.details = [
                InvoiceLineDetail(**{x: getattr(line.details[0], x, None)
                        for x in line_detail_fields})]
            waiver_line.details[0].waiver = waiver_option
            option.coverage.init_waiver_line(waiver_line, waiver_option)
            lines.append(waiver_line)

    @classmethod
    def _calculate_methods(cls, product):
        return super(Contract, cls)._calculate_methods(product) + [
            ('contract', 'create_automatic_waiver')]

    def create_automatic_waiver(self):
        pool = Pool()
        Waiver = pool.get('contract.waiver_premium')
        WaiverOption = pool.get('contract.waiver_premium-contract.option')
        options_to_waive = [o for o in self.get_all_options()
            if o.with_automatic_waiver_premium()]
        if not options_to_waive:
            return
        if self.start_date == self.initial_start_date:
            previous = []
            existings = [w for w in self.waivers if w.automatic]
        else:
            # Renewal
            previous = [w for w in self.waivers
                if w.automatic and w.start_date < self.start_date]
            existings = [w for w in self.waivers
                if w.automatic and w.start_date >= self.start_date]
        manual_waivers = [w for w in self.waivers if not w.automatic]
        if existings:
            # TODO : What if we want to have several waivers within a period
            waiver = existings[0]
        else:
            waiver = Waiver(automatic=True, waiver_options=[])

        # Remove waiver on unsubscribed options
        waiver_options = [wo for wo in waiver.waiver_options
            if wo.option in options_to_waive]
        for option in options_to_waive:
            waiver_option = [wo for wo in waiver_options
                if wo.option == option]
            if waiver_option:
                waiver_option = waiver_option[0]
            else:
                waiver_option = WaiverOption(option=option)
                waiver_options.append(waiver_option)
            res = option.calculate_automatic_premium_duration()
            if res and len(res) == 2:
                waiver_option.start_date, waiver_option.end_date = res
            else:
                waiver_option.start_date, waiver_option.end_date = None, None

        waiver.waiver_options = waiver_options
        waiver.start_date = waiver.get_start_date()
        waivers = previous + manual_waivers
        if waiver.waiver_options and waiver.start_date:
            waivers.append(waiver)
        self.waivers = waivers


class ContractOption:
    __name__ = 'contract.option'

    waivers = fields.One2Many('contract.waiver_premium-contract.option',
        'option', 'Waivers')
    with_waiver_of_premium = fields.Function(
        fields.Boolean('With Waiver Of Premium'),
        'get_with_waiver_of_premium')

    def get_with_waiver_of_premium(self, name):
        return self.coverage.with_waiver_of_premium

    def get_waiver_at_date(self, from_date, to_date):
        waiver_option = None
        overlap_waivers = []
        for waiver in self.waivers:
            if (not waiver.start_date or waiver.start_date <= to_date) and (
                    not waiver.end_date or waiver.end_date >= from_date):
                overlap_waivers.append(waiver)
        if not overlap_waivers:
            return
        assert len(overlap_waivers) == 1
        waiver_option = overlap_waivers[0]
        behaviour = \
            self.coverage.waiver_premium_rule[0].invoice_line_period_behaviour
        assert behaviour in ['one_day_overlap', 'proportion', 'total_overlap']
        if behaviour in ('one_day_overlap', 'proportion'):
            return waiver_option.waiver
        elif behaviour == 'total_overlap' and (not waiver_option.end_date
                or waiver_option.end_date >= to_date) \
                and (not waiver_option.start_date
                or waiver_option.start_date <= from_date):
            return waiver_option.waiver

    def get_waiver_option_for_invoice_line(self, line):
        return self.get_waiver_at_date(line.coverage_start, line.coverage_end)

    def calculate_automatic_premium_duration(self):
        if not self.with_waiver_of_premium:
            return [None, None]
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        return self.coverage.waiver_premium_rule[0].calculate_duration_rule(
            exec_context)

    def with_automatic_waiver_premium(self):
        return (self.coverage.with_waiver_of_premium
            and self.coverage.waiver_premium_rule[0].automatic)
