# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import datetime
from itertools import groupby
from collections import defaultdict
from decimal import Decimal

from sql.aggregate import Max
from sql import Literal

from trytond.pool import Pool, PoolMeta
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder
from trytond.modules.coog_core import model, fields, coog_string, utils

__all__ = [
    'SynthesisMenuInvoice',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    'PartyReplace',
    'Party',
    ]


class SynthesisMenuInvoice(model.CoogSQL):
    'Party Synthesis Menu Invoice'
    __name__ = 'party.synthesis.menu.invoice'
    name = fields.Char('Invoices')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceSynthesis = pool.get('party.synthesis.menu.invoice')
        party = pool.get('party.party').__table__()
        invoice = Invoice.__table__()
        query_table = party.join(invoice, 'LEFT OUTER', condition=(
            party.id == invoice.party))
        return query_table.select(
            party.id,
            Max(invoice.create_uid).as_('create_uid'),
            Max(invoice.create_date).as_('create_date'),
            Max(invoice.write_uid).as_('write_uid'),
            Max(invoice.write_date).as_('write_date'),
            Literal(coog_string.translate_label(InvoiceSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'invoice'

    def get_rec_name(self, name):
        InvoiceSynthesis = Pool().get('party.synthesis.menu.invoice')
        return coog_string.translate_label(InvoiceSynthesis, 'name')


class SynthesisMenu(metaclass=PoolMeta):
    __name__ = 'party.synthesis.menu'

    @classmethod
    def union_models(cls):
        res = super(SynthesisMenu, cls).union_models()
        res.extend([
            'party.synthesis.menu.invoice',
            'account.invoice',
            ])
        return res

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.invoice':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'account.invoice':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['party'])
                union_field.model_name = 'party.synthesis.menu.invoice'
                return union_field
            elif name == 'name':
                return Model._fields['number']
        return union_field

    @classmethod
    def build_sub_query(cls, model, table, columns):
        if model != 'account.invoice':
            return super(SynthesisMenu, cls).build_sub_query(model, table,
                columns)
        return table.select(*columns,
            where=(table.state == 'posted'))

    @classmethod
    def menu_order(cls, model):
        res = super(SynthesisMenu, cls).menu_order(model)
        if model == 'party.synthesis.menu.invoice':
            res = 21
        return res


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if Model.__name__ != 'party.synthesis.menu.invoice':
            return super(SynthesisMenuOpen, self).get_action(record)
        domain = PYSONEncoder().encode([('party', '=', record.id)])
        actions = {
            'res_model': 'account.invoice',
            'pyson_domain': domain,
            'views': [(Pool().get('ir.ui.view').search([('xml_id', '=',
                    'contract_insurance_invoice.premium_notice_view_list')
                        ])[0].id, 'tree'),
                    (Pool().get('ir.ui.view').search([('xml_id', '=',
                        'account_invoice.invoice_view_form')
                            ])[0].id, 'form')]
        }
        return actions


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('contract.billing_information', 'payer'),
            ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def _group_billing_per_contract(cls, billing_info):
        return billing_info.contract

    def _get_contracts_for_invoices_report(self):
        contracts = Pool().get('contract').search(['OR',
            ['billing_informations.payer', '=', self],
            [('billing_informations.payer', '=', None),
             ('subscriber', '=', self)]])
        return [contract for contract in contracts
            if contract.payer == self or contract.subscriber == self]

    @classmethod
    def _invoices_report_contract_key(cls, contract):
        billing_info = contract.billing_information
        key = (billing_info.billing_mode, billing_info.direct_debit_account
            if billing_info.direct_debit_account else False)
        return key

    def payment_schedule_report(self):
        # Method used in printing report
        contracts = self._get_contracts_for_invoices_report()
        sorted_contracts = sorted(contracts,
            key=self.__class__._invoices_report_contract_key)
        grouped_contracts_by_bill_info = groupby(sorted_contracts,
            key=self.__class__._invoices_report_contract_key)
        invoices_report_data = []
        for key, contracts in grouped_contracts_by_bill_info:
            invoices_reports = [contract.invoices_report()
                for contract in contracts]
            all_reports = [report for invoice_report in invoices_reports
                for report in invoice_report[0]]
            sorted_reports = sorted(all_reports,
                key=lambda x: x['planned_payment_date'])
            reports_per_date = defaultdict(lambda:
                {'total_amount': 0, 'components': []})
            grouped_invoices = groupby(sorted_reports,
                lambda x: x['planned_payment_date'])
            total = 0
            schedules_data = []
            for planned_date, schedules in grouped_invoices:
                for schedule in schedules:
                    reports_per_date[planned_date]['total_amount'] += schedule[
                        'total_amount']
                    reports_per_date[planned_date]['components'] += schedule[
                        'components']
                    reports_per_date[planned_date][
                        'planned_payment_date'] = planned_date
                    total += schedule['total_amount']
                schedules_data.append(reports_per_date.get(planned_date))
            taxes = defaultdict(Decimal)
            total_taxes = 0
            for report in invoices_reports:
                for k, value in report[2].items():
                    taxes[k] += value
                    total_taxes += value
            invoices_report_data.append({
                'total_amount': total,
                'billing_mode': key[0],
                'schedules': schedules_data,
                'taxes': {'total': total_taxes, 'details': dict(taxes)},
                })
        return invoices_report_data

    @classmethod
    def get_depending_contracts(cls, parties, date=None):
        to_suspend = super(Party, cls).get_depending_contracts(parties,
            date=date)
        BillingInformation = Pool().get('contract.billing_information')
        date = date or utils.today()
        billing_infos = [x
            for x in BillingInformation.search(['AND',
                [
                    ('payer', 'in', parties),
                    ('direct_debit', '=', True),
                    ], ['OR',
                        [('date', '<=', date)], ['date', '=', None]]
                    ]) if not x.suspended and x.contract_status == 'active']
        billing_infos = sorted(
            billing_infos, key=cls._group_billing_per_contract)
        to_suspend_payers = []
        # Find contracts where the payer or the future payer is in the given
        # payers
        for contract, billing_infos in groupby(billing_infos,
                key=cls._group_billing_per_contract):
            billing_infos = sorted(billing_infos, lambda x: x.date
                or datetime.date.min)
            billing_info = billing_infos[-1]
            all_billing = sorted(contract.billing_informations,
                lambda x: x.date)
            today_and_future_billings = all_billing[
                all_billing.index(contract.billing_information):]
            if billing_info in today_and_future_billings:
                to_suspend_payers.append(contract)
        return list(set(to_suspend) | set(to_suspend_payers))
