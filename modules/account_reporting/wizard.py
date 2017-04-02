# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from sql.aggregate import Sum
from sql.functions import DateTrunc
from sql.conditionals import Coalesce

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.wizard import (Wizard, StateView, StateReport, Button)
from trytond.tools import cursor_dict

from trytond.modules.coog_core import fields, utils, model, coog_date

__all__ = [
    'PrintMoveLineAggregatedReport',
    'PrintMoveLineAggregatedReportStart',
    'MoveLineAggregatedReport',
    ]


class PrintMoveLineAggregatedReportStart(model.CoogView):
    'Print Aggregated Move Lines Report Start'
    __name__ = 'account.move_line_aggregated_report.print.start'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[('company', '=', Eval('company'))],
        depends=['company']
    )
    products = fields.Many2Many('offered.product', None, None, 'Products')
    company = fields.Many2One('company.company', 'Company', required=True)

    @staticmethod
    def default_end_date():
        return utils.today()

    @staticmethod
    def default_account():
        AccountConfiguration = Pool().get('account.configuration')
        account_config, = AccountConfiguration.search([], limit=1)
        if account_config and account_config.default_account_receivable:
            return account_config.default_account_receivable.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class PrintMoveLineAggregatedReport(Wizard):
    'Print Move Lines Aggregated by Product Report'
    __name__ = 'account.move_line_aggregated_report.print'

    start = StateView('account.move_line_aggregated_report.print.start',
        'account_reporting.reporting_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport(
        'account.move_line_aggregated.report')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'start_date': self.start.start_date,
            'end_date': self.start.end_date,
            'account': self.start.account.id,
            'product_ids': [p.id for p in self.start.products],
            }
        return action, data

    def transition_print_(self):
        return 'end'


class MoveLineAggregatedReport(Report):
    __name__ = 'account.move_line_aggregated.report'

    @classmethod
    def format_records(cls, records_src, start_date, end_date):
        def month(yyyy_mm_dd):
            return str(yyyy_mm_dd)[0:7]

        records = []
        all_dates = [coog_date.add_month(start_date, n)
            for n in range(coog_date.number_of_months_between(
                    start_date, end_date) + 1)]
        month_sum = {month(m): 0 for m in all_dates}
        # Workaround 'Incoherent column repetition found' error that occurs at
        # document generation  when trying to create header row "properly",
        # ie by iterating on a separate report_context value containing the
        # months list.
        header_recs = [{'amount': month(d)} for d in all_dates + ['Total']]
        records.append({
                'product': '',
                'by_month': header_recs,
                'total': '',
                })
        for product, _recs in groupby(records_src,
                key=lambda rec: rec['product']):
            recs = sorted(list(_recs), key=lambda x: x['_month'])
            for r in recs:
                month_sum[month(r['_month'])] += r['amount']
            records.append({
                    'product': product,
                    'total': sum([r['amount'] for r in recs]),
                    'by_month': recs,
                    })
        # Fill missing months in products amounts lists
        for prod_rec in records[1:]:
            recs = prod_rec['by_month'][:]
            all_recs = []
            for d in all_dates:
                if not recs or month(d) != month(recs[0]['_month']):
                    all_recs.append({'amount': 0, '_month': d})
                else:
                    all_recs.append(recs.pop(0))
            prod_rec['by_month'] = all_recs
        footer_recs = [{'amount': month_sum[k]}
            for k in sorted(month_sum.keys())]
        records.append({
                'product': 'Total',
                'total': '',
                'by_month': footer_recs,
                })
        return records

    @classmethod
    def get_query_table(cls):
        pool = Pool()
        account_move_line = pool.get('account.move.line').__table__()
        account_move = pool.get('account.move').__table__()
        contract = pool.get('contract').__table__()
        product = pool.get('offered.product').__table__()
        account = pool.get('account.account').__table__()
        invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        # TODO: perfs
        query = invoice.join(contract_invoice, condition=(
                 invoice.id == contract_invoice.invoice)
            ).join(contract, condition=(
                contract_invoice.contract == contract.id)
            ).join(product, condition=(
                contract.product == product.id)
            ).join(account, condition=(
                account.id == invoice.account)
            ).join(account_move_line, condition=(
                contract.id == account_move_line.contract)
            ).join(account_move, condition=(
                account_move_line.move == account_move.id)
            )

        return query, {
            'account.move.line': account_move_line,
            'account.move': account_move,
            'contract': contract,
            'product': product,
            'invoice': invoice,
            'account': account,
            }

    @classmethod
    def get_where_clause(cls, tables, values):
        product_ids = values.get('product_ids', None)
        start_date = values.get('start_date', None)
        end_date = values.get('end_date', None)
        where_clause = (tables['account.move'].state == values.get('state'))
        if start_date:
            where_clause &= tables['invoice'].create_date >= start_date
        if end_date:
            where_clause &= tables['invoice'].create_date <= end_date
        if product_ids:
            where_clause &= tables['product'].id.in_(product_ids)
        return where_clause

    @classmethod
    def get_columns(cls, tables):
        account_move_line = tables['account.move.line']
        product = tables['product']
        invoice = tables['invoice']
        columns = [
            Sum(Coalesce(account_move_line.credit, 0) -
                Coalesce(account_move_line.debit, 0)).as_('amount'),
            product.name.as_('product'),
            DateTrunc('month', invoice.create_date).as_('_month'),
            ]
        return columns

    @classmethod
    def get_group_by(cls, tables):
        return [tables['product'].name,
            DateTrunc('month', tables['invoice'].create_date)]

    @classmethod
    def aggregated_move_lines(cls, **kwargs):
        query, tables = cls.get_query_table()
        product = tables['product']
        columns = cls.get_columns(tables)
        where_clause = cls.get_where_clause(tables, {
                'product_ids': kwargs.get('product_ids'),
                'state': 'posted',
                'start_date': kwargs.get('start_date'),
                'end_date': kwargs.get('end_date'),
                })
        cursor = Transaction().connection.cursor()
        cursor.execute(*query.select(*columns,
                where=where_clause,
                group_by=cls.get_group_by(tables),
                order_by=(product.name)))
        return cursor_dict(cursor)

    @classmethod
    def get_context(cls, records, data):
        report_context = super(MoveLineAggregatedReport,
            cls).get_context(records, data)
        Company = Pool().get('company.company')
        records = cls.aggregated_move_lines(**data)
        report_context['records'] = cls.format_records(records,
            data['start_date'], data['end_date'])
        report_context['company'] = Company(data['company'])

        return report_context