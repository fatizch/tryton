# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or
from trytond.modules.cog_utils import fields, model, utils


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

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'create_waiver': {
                    'invisible': Or(~Eval('with_waiver_of_premium'),
                        Eval('status') != 'active'),
                    },
                })
        cls._error_messages.update({
                'waiver_line': 'Waiver of Premium',
                })

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '/form/group[@id="waiver_buttons"]',
                'states',
                {'invisible': True}
                )]

    @classmethod
    @model.CoopView.button_action(
        'contract_waiver_premium.act_create_waiver_wizard')
    def create_waiver(cls, contracts):
        pass

    def get_with_waiver_of_premium(self, name):
        all_options = self.options + self.covered_element_options
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
            waiver = option.get_waiver_for_invoice_line(line)
            if not waiver:
                continue
            waiver_line = InvoiceLine(**{x: getattr(line, x, None)
                    for x in line_fields})
            waiver_line.details = [
                InvoiceLineDetail(**{x: getattr(line.details[0], x, None)
                        for x in line_detail_fields})]
            waiver_line.details[0].waiver = waiver
            waiver_line.taxes = [x.id for x in
                option.coverage.taxes_for_waiver]
            waiver_line.account = \
                option.coverage.get_account_for_waiver_line()
            waiver_line.unit_price *= -1
            waiver_line.description += ' - ' + self.raise_user_error(
                'waiver_line', raise_exception=False)
            lines.append(waiver_line)


class ContractOption:
    __name__ = 'contract.option'

    waivers = fields.Many2Many(
        'contract.waiver_premium-contract.option', 'option',
        'waiver', 'Waivers')
    with_waiver_of_premium = fields.Function(
        fields.Boolean('With Waiver Of Premium'),
        'get_with_waiver_of_premium')

    def get_with_waiver_of_premium(self, name):
        return bool(self.coverage.with_waiver_of_premium !=
            'without_waiver_of_premium')

    def get_waiver_at_date(self, date):
        return utils.get_good_version_at_date(self, 'waivers',
            at_date=date)

    def get_waiver_for_invoice_line(self, line):
        return self.get_waiver_at_date(line.coverage_start)
