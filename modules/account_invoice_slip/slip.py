# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Null, Cast
from sql.conditionals import Coalesce
from sql.aggregate import Sum
from sql.operators import Not

from trytond import backend
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields, coog_sql, utils, export

__all__ = [
    'InvoiceSlipConfiguration',
    'InvoiceSlipAccount',
    ]


class InvoiceSlipConfiguration(model.CoogSQL, model.CoogView,
        export.ExportImportMixin):
    'Invoice Slip Configuration'

    __name__ = 'account.invoice.slip.configuration'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        required=True)
    accounts = fields.Many2Many('account.invoice.slip.account',
        'slip_configuration', 'account', 'Accounts')
    slip_kind = fields.Selection([('slip', 'Slip')],
        'Slip kind')
    name = fields.Char('Name', required=True, help='The value of this field '
        'will be used as the description of the generated slip')
    journal = fields.Many2One('account.journal', 'Journal', ondelete='RESTRICT',
        required=True)
    accounts_names = fields.Function(
        fields.Char('Accounts Names'),
        'on_change_with_accounts_names')

    @classmethod
    def _export_light(cls):
        return super(InvoiceSlipConfiguration, cls)._export_light() | {
            'party', 'journal', 'accounts'}

    @classmethod
    def __setup__(cls):
        super(InvoiceSlipConfiguration, cls).__setup__()
        cls._error_messages.update({
                'duplicate_slip': 'More than one draft slip for parameters:'
                '\nParty: %(party)s\nKind: %(business_kind)s'
                '\nDate: %(invoice_date)s',
                })

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')

        # Migration from 2.0: Move default reset journal from commission_insurer
        # module. Detecting the table existence is the easiest and safest way
        if not TableHandler.table_exist(cls._table):
            # Look for existing model data in the commission_insurer module
            model_data = Pool().get('ir.model.data').__table__()
            journal = Pool().get('account.journal').__table__()
            cursor = Transaction().connection.cursor()

            cursor.execute(*model_data.select(
                    model_data.model, model_data.id, model_data.db_id,
                    where=(model_data.module == 'commission_insurer')
                    & model_data.fs_id.in_(['journal_type_commission_reset',
                            'journal_commission_reset'])))

            existing = {}
            for target_model, target_id, target_db_id in cursor.fetchall():
                existing[target_model] = (target_id, target_db_id)
            if existing:
                # If this is False, there is a problem (because we know that
                # both values are supposed to be consistently created /
                # deleted)
                assert len(existing) == 2
                cursor.execute(*model_data.update(
                        [model_data.module, model_data.fs_id],
                        ['account_invoice_slip',
                            'journal_type_principal_line_reset'],
                        where=(
                            model_data.id ==
                            existing['account.journal.type'][0])
                        ))
                cursor.execute(*model_data.update(
                        [model_data.module, model_data.fs_id],
                        ['account_invoice_slip',
                            'journal_principal_line_reset'],
                        where=model_data.id == existing['account.journal'][0]
                        ))
                cursor.execute(*model_data.update(
                        [model_data.module, model_data.fs_id],
                        ['account_invoice_slip',
                            'journal_principal_line_reset'],
                        where=model_data.id == existing['account.journal'][0]
                        ))
                cursor.execute(*journal.update(
                        [journal.type], ['principal_line_reset'],
                        where=journal.id == existing['account.journal'][1]))

        super(InvoiceSlipConfiguration, cls).__register__(module)

    @fields.depends('accounts')
    def on_change_with_accounts_names(self, name=None):
        return ', '.join(x.rec_name for x in self.accounts or [])

    def get_params_dict(self):
        return {
            'party': self.party,
            'accounts': list(self.accounts),
            'slip_kind': self.slip_kind,
            'journal': self.journal,
            'slip_name': self.name,
            }

    @classmethod
    def check_parameters(cls, parameters):
        # Some queries are mutualized for all slips, so it is easier if we
        # assume the date is identical. Allowing for different dates is
        # possible, but will require some looping
        assert len({x['date'] for x in parameters}) == 1
        assert len({x['journal'] for x in parameters}) == 1
        assert len({x['slip_kind'] for x in parameters}) == 1
        accounts = sum([x['accounts'] for x in parameters], [])
        # TODO : Same check but across parties rather than global
        assert len(set(accounts)) == len(accounts)

    @classmethod
    def generate_slips(cls, slip_parameters):
        '''
            Will generate slips according to the given parameters list. Each
            parameter is a dictionary with the following keys:

            - 'party': The party which should be used for the invoice
            - 'accounts': The accounts to analyze
            - 'date': The maximum date for the lines to include in the slip
            - 'slip_kind': The kind of invoice that will be generated
            - 'journal': The journal that will be used for the invoice
        '''
        cls.create_empty_slips(slip_parameters)

        # We simulate the same behavior as that of the batch, a first select to
        # find the invoices, which will be reused in
        # update_slips_from_invoices to find their actual data
        invoices_ids = cls.select_invoices(slip_parameters)

        cls.update_slips_from_invoices(slip_parameters, invoices_ids)
        return cls.finalize_slips(slip_parameters)

    @classmethod
    def create_empty_slips(cls, slip_parameters):
        '''
            Step 1: Create the empty invoices for each given set of parameters.
        '''
        Invoice = Pool().get('account.invoice')
        invoices = []

        cls.check_parameters(slip_parameters)

        for parameters in slip_parameters:
            invoices.append(cls._get_slip(parameters))
        if invoices:
            Invoice.save(invoices)
        return invoices

    @classmethod
    def _get_slip(cls, parameters):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        party = parameters['party']
        invoice_type = cls._get_invoice_type(parameters)
        business_kind = cls._get_invoice_business_kind(parameters)
        matches = Invoice.search([
                ('party', '=', party),
                ('journal', '=', parameters['journal']),
                ('invoice_date', '=', parameters['date'] or utils.today()),
                ('type', '=', invoice_type),
                ('business_kind', '=', business_kind),
                ('state', '=', 'draft')
                ], limit=2)
        if matches:
            # If there already is a slip matching the given configuration, we
            # return it. If there is more than one, there probably is a problem
            # somewhere
            if len(matches) > 1:
                cls.raise_user_error('duplicate_slip', {
                        'business_kind': business_kind,
                        'invoice_date': parameters['date'] or utils.today(),
                        'party': party.rec_name,
                        })
            return matches[0]
        return cls._get_new_slip(parameters)

    @classmethod
    def _get_new_slip(cls, parameters):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        party = parameters['party']
        company = parameters['accounts'][0].company
        account = cls._get_invoice_account(parameters)
        invoice_type = cls._get_invoice_type(parameters)
        business_kind = cls._get_invoice_business_kind(parameters)
        invoice = Invoice()
        invoice.description = parameters.get('name', '')
        invoice.company = company
        invoice.type = invoice_type
        invoice.journal = parameters['journal']
        invoice.party = party
        invoice.invoice_address = party.address_get(type='invoice')
        invoice.currency = company.currency
        invoice.account = account
        invoice.payment_term = party.supplier_payment_term
        invoice.invoice_date = parameters['date'] or utils.today()
        invoice.business_kind = business_kind
        invoice.state = 'draft'
        invoice_lines = []
        for account in parameters['accounts']:
            invoice_lines += cls._get_slip_lines(account, parameters)
        invoice.lines = invoice_lines
        return invoice

    @classmethod
    def _get_invoice_account(cls, parameters):
        if cls._get_invoice_type(parameters) == 'in':
            return parameters['party'].account_payable_used
        return parameters['party'].account_receivable_used

    @classmethod
    def _get_invoice_type(cls, parameters):
        return 'in'

    @classmethod
    def _get_invoice_business_kind(cls, parameters):
        return parameters['slip_kind']

    @classmethod
    def _get_slip_lines(cls, account, parameters):
        return [cls._get_slip_line(account, account.rec_name, parameters)]

    @classmethod
    def _get_slip_line(cls, account, description, parameters):
        line = Pool().get('account.invoice.line')()
        line.party = parameters['party']
        line.type = 'line'
        line.quantity = 1
        line.unit_price = 0
        line.account = account
        line.description = description
        return line

    @classmethod
    def select_invoices(cls, slip_parameters, invoices_ids=None):
        '''
            Step 2: Look for invoices that match the parameters.

            Filtering is done on:
            - Lines matching the accounts
            - Lines not yet included in a slip
            - Paid / De-paid (paid then unreconciled) / Cancelled invoices

            When invoice_ids is not set, the function will return a generator
            over all the invoice ids that match the parameters.

            When invoice_ids is set, the function will return a dictionary with
            invoice ids as keys, and a list of tuples
                        (move_line_id, move_line_account)
            as values.

            The separation is necessary in order to be able to separate the
            slip generation in batches. We can first call the method without
            any invoice ids to get all invoices to consider, then we can split
            the ids to treat, and feed them back to the method in order to get
            the associated data.
        '''
        pool = Pool()
        invoice = pool.get('account.invoice').__table__()
        move = pool.get('account.move').__table__()
        move_line = pool.get('account.move.line').__table__()
        cursor = Transaction().connection.cursor()

        cls.check_parameters(slip_parameters)

        accounts = set(sum([x['accounts'] for x in slip_parameters], []))
        date = slip_parameters[0]['date']

        ignore_journals = cls._select_lines_ignore_journals(slip_parameters)
        reset_journals = cls._select_lines_reset_journals(slip_parameters)

        invoice_condition = (move.id.in_([invoice.move, invoice.cancel_move])
            & invoice.state.in_(['paid', 'cancel']))

        if ignore_journals:
            invoice_condition &= Not(move.journal.in_(
                    [x.id for x in ignore_journals]))

        if reset_journals:
            invoice_condition |= ((
                    move.origin == coog_sql.TextCat('account.invoice,',
                    Cast(invoice.id, 'VARCHAR')))
                & move.journal.in_([x.id for x in reset_journals]))

        query_table = move_line.join(move, condition=move_line.move == move.id
            ).join(invoice, condition=invoice_condition)

        where_clause = (
            move_line.account.in_([x.id for x in accounts])
            & (move_line.principal_invoice_line == Null)
            & (move.state == 'posted')
            )

        if date:
            where_clause &= (move.date <= date)

        if invoices_ids is not None:
            invoices_ids_list = [x for x in invoices_ids]
            if not invoices_ids_list:
                return {}
            invoices_data = defaultdict(list)
            where_clause &= invoice.id.in_(invoices_ids_list)
            cursor.execute(*query_table.select(
                    invoice.id, move_line.id, move_line.account,
                    where=where_clause, order_by=invoice.id,
                    group_by=[invoice.id, move_line.id, move_line.account]))
            for invoice, line, account in cursor.fetchall():
                invoices_data[invoice].append((line, account))
            return invoices_data
        else:
            cursor.execute(*query_table.select(invoice.id,
                    where=where_clause, order_by=invoice.id,
                    group_by=[invoice.id]))
            return (invoice[0] for invoice in cursor.fetchall())

    @classmethod
    def _select_lines_ignore_journals(cls, slip_parameters):
        return Pool().get('account.journal').search(
            [('id', 'in', [x['journal'].id for x in slip_parameters])])

    @classmethod
    def _select_lines_reset_journals(cls, slip_parameters):
        return Pool().get('account.journal').search(
            [('type', 'like', '%reset')])

    @classmethod
    def update_slips_from_invoices(cls, slip_parameters, invoices_ids):
        '''
            Step 3: Analyze invoice related move lines and attach them to the
            matching slip lines
        '''
        invoices_data = cls.select_invoices(slip_parameters,
            invoices_ids=invoices_ids)
        invoices_data = cls._get_invoices_data(slip_parameters, invoices_data)

        current_slips = cls._retrieve_empty_slips(slip_parameters)
        cls._update_backrefs(slip_parameters, invoices_data, current_slips)

    @classmethod
    def _get_invoices_data(cls, slip_parameters, invoices_data):
        '''
            Returns a dictionary with, per account found in the parameters,
            another dictionary with the list of account lines:

                {
                    account_1: {'lines': [line1, line2]},
                    account_2: {'lines': [line3]},
                }

            The 'dictionary' approach for the values is needed to allow more
            customization in other modules (ex: commissions)
        '''
        per_account = defaultdict(lambda: {'lines': []})
        for line, account in sum(invoices_data.values(), []):
            per_account[account]['lines'].append(line)

        return per_account

    @classmethod
    def _retrieve_empty_slips(cls, slip_parameters):
        '''
            Returns a dictionary with all the accounts in the parameters as
            keys, and another dictionary with the invoice and invoice line
            matching the account in the current slip as values.
        '''
        per_account = {}
        for parameter in slip_parameters:
            invoice = cls._get_slip(parameter)

            for account in parameter['accounts']:
                data = {}
                # The finalize slip method relies on the invoice being the same
                # technical object for all account data
                data['invoice'] = invoice
                data['invoice_line'] = cls._find_slip_line(
                    account, account.rec_name, invoice)
                per_account[account] = data

        return per_account

    @classmethod
    def _find_slip_line(cls, account, description, invoice):
        for line in invoice.lines:
            if line.account == account and line.description == description:
                return line
        raise KeyError

    @classmethod
    def _update_backrefs(cls, slip_parameters, invoices_data, current_slips):
        '''
            Will update all data which must be included in the slip by setting
            its backref field to the matching slip line.

            For move lines, that will be the principal_invoice_line field
        '''
        cls._update_move_lines(slip_parameters, invoices_data,
            current_slips)

    @classmethod
    def _update_move_lines(cls, slip_parameters, invoices_data,
            current_slips):
        for account, account_data in current_slips.iteritems():
            account_invoice_data = invoices_data[account.id]
            if account_invoice_data.get('lines', None):
                cls._update_base_line(account_data['invoice_line'],
                    account_invoice_data['lines'])

    @classmethod
    def _update_base_line(cls, invoice_line, move_lines):
        cursor = Transaction().connection.cursor()
        line = Pool().get('account.move.line').__table__()

        cursor.execute(*line.update([line.principal_invoice_line],
                [invoice_line.id], where=line.id.in_(move_lines)))

    @classmethod
    def finalize_slips(cls, slip_parameters):
        '''
            Step 4: Set the total amount on each invoice line by summing all
            the lines attached to it
        '''
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Event = pool.get('event')

        cls.check_parameters(slip_parameters)

        slips = set()
        slips_data = cls._retrieve_empty_slips(slip_parameters)

        # The original idea was to only update the line amounts, then do a mass
        # save at the end of the loop. However, this does not work out nicely
        # with the commission_insurer module, because it adds new lines which
        # must be saved so that commissions can reference them.
        #
        # This forces to do the saves in the _finalize_*_lines methods rather
        # than only once at the end :'(
        for account, account_data in slips_data.iteritems():
            cls._finalize_invoice_lines(slip_parameters, account_data)
            slips.add(account_data['invoice'])
        Invoice.update_taxes(slips)

        Event.notify_events(slips,
            cls._event_code_from_slip_kind(slip_parameters[0]['slip_kind']))
        return slips

    @classmethod
    def _finalize_invoice_lines(cls, slip_parameters, account_data):
        cls._finalize_principal_line(slip_parameters, account_data)

    @classmethod
    def _finalize_principal_line(cls, slip_parameters, account_data):
        if 'invoice_line' not in account_data:
            return

        pool = Pool()
        MoveLine = pool.get('account.move.line')
        InvoiceLine = pool.get('account.invoice.line')
        LineTable = MoveLine.__table__()

        cursor = Transaction().connection.cursor()
        where_clause = (LineTable.principal_invoice_line ==
            account_data['invoice_line'].id)
        cursor.execute(*LineTable.select(
                Coalesce(Sum(Coalesce(LineTable.credit, 0)), 0)
                .as_('tot_credit'),
                Coalesce(Sum(Coalesce(LineTable.debit, 0)), 0)
                .as_('tot_debit'),
                where=where_clause))
        move_line_total = cursor.fetchone()

        amount = 0
        if move_line_total and move_line_total != [[0, 0]]:
            total_credit, total_debit = move_line_total
            if account_data['invoice'].type == 'in':
                amount = total_credit - total_debit
            elif account_data['invoice'].type == 'out':
                amount = total_debit - total_credit

            account_data['invoice_line'].unit_price = amount

            # Read the comment in finalize_slips before trying to optimize this
            account_data['invoice_line'].save()
        else:
            InvoiceLine.delete([account_data['invoice_line']])

    @classmethod
    def _event_code_from_slip_kind(cls, slip_kind):
        if slip_kind == 'slip':
            return 'slips_generated'


class InvoiceSlipAccount(model.CoogSQL):
    'Invoice Slip Account Relation'

    __name__ = 'account.invoice.slip.account'

    slip_configuration = fields.Many2One('account.invoice.slip.configuration',
        'Slip Configuration', ondelete='CASCADE', required=True, select=True)
    account = fields.Many2One('account.account', 'Account', ondelete='CASCADE',
        required=True, select=True)
