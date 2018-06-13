# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from sql import Null, Cast
from sql.conditionals import Coalesce
from sql.operators import Not
from sql.aggregate import Sum
from decimal import Decimal

from trytond import backend
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.model import ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONEncoder, Bool, Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils, coog_date, coog_sql

__all__ = [
    'Agent',
    'Commission',
    'CreateInvoicePrincipal',
    'CreateInvoicePrincipalAsk',
    ]


class Agent:
    __metaclass__ = PoolMeta
    __name__ = 'commission.agent'

    insurer = fields.Many2One('insurer', 'Insurer', ondelete='RESTRICT',
        states={
            'invisible': ~Eval('is_for_insurer'),
            'required': Bool(Eval('is_for_insurer')),
            }, domain=[('party', '=', Eval('party'))],
        depends=['is_for_insurer', 'party'])
    is_for_insurer = fields.Function(
        fields.Boolean('For insurer'), 'on_change_with_is_for_insurer')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        handler = TableHandler(cls, module_name)
        to_migrate = not handler.column_exist('insurer')

        super(Agent, cls).__register__(module_name)

        # Migration from 1.10 : Store insurer
        if to_migrate:
            pool = Pool()
            to_update = cls.__table__()
            insurer = pool.get('insurer').__table__()
            party = pool.get('party.party').__table__()
            update_data = party.join(insurer, condition=(
                    insurer.party == party.id)
                ).select(insurer.id.as_('insurer_id'), party.id)
            cursor.execute(*to_update.update(
                    columns=[to_update.insurer],
                    values=[update_data.insurer_id],
                    from_=[update_data],
                    where=update_data.id == to_update.party))

    @fields.depends('party')
    def on_change_with_is_for_insurer(self, name=None):
        return self.party.is_insurer if self.party else False


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls._error_messages.update({
                'invoice_error': 'An error occured while looking for '
                'previously generated invoice (%s result found, 1 expected)',
                'invoice_line_error': 'An error occured while looking for '
                'previously generated invoice line (%s result found, '
                '1 expected), ensure there is no already existing invoice.',
                'already_generated': 'An insurer notice has already been '
                'generated today for (%s)'})

    @classmethod
    def get_insurer_invoice_type(cls, notice_kind):
        assert notice_kind == 'options', 'Invalid notice kind'
        return 'in'

    @classmethod
    def get_insurer_business_kind(cls, notice_kind):
        assert notice_kind == 'options', 'Invalid notice kind'
        return 'insurer_invoice'

    @classmethod
    def get_insurer_invoice(cls, company, insurer, journal, date, notice_kind):
        Invoice = Pool().get('account.invoice')
        date = utils.today() if date is None else date
        type_ = cls.get_insurer_invoice_type(notice_kind)
        business_kind = cls.get_insurer_business_kind(notice_kind),
        matchs = Invoice.search([
                ('company', '=', company),
                ('journal', '=', journal),
                ('party', '=', insurer.party),
                ('insurer_role', '=', insurer),
                ('invoice_date', '=', date),
                ('type', '=', type_),
                ('business_kind', '=', business_kind),
                ('state', '=', 'draft'),
                ], limit=2)
        if matchs:
            if len(matchs) != 1:
                cls.raise_user_error('invoice_error', len(matchs))
            return matchs[0]
        return Invoice(
            company=company,
            type=type_,
            journal=journal,
            party=insurer.party,
            insurer_role=insurer,
            invoice_address=insurer.party.address_get(type='invoice'),
            currency=company.currency,
            account=insurer.party.account_payable_used if type_ == 'in'
            else insurer.party.account_receivable_used,
            payment_term=insurer.party.supplier_payment_term,
            invoice_date=date,
            business_kind=business_kind,
            lines=[],
            )

    @classmethod
    def get_insurer_invoice_line(cls, account, amount=0,
            description='', invoice=None):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        if invoice:
            matchs = Line.search([
                    ('invoice', '=', invoice.id),
                    ('account', '=', account),
                    ('type', '=', 'line'),
                    ('description', '=', description),
                    ('quantity', '=', 1),
                    ('invoice.state', '=', 'draft'),
            ], limit=2)
            if len(matchs) != 1:
                cls.raise_user_error('invoice_line_error', len(matchs))
            return matchs[0]

        line = Line()
        line.type = 'line'
        line.quantity = 1
        line.unit_price = amount
        line.account = account
        line.description = description

        return line

    @classmethod
    def create_empty_invoice_line(cls, description, account, invoice,
            party=None):
        InvoiceLine = Pool().get('account.invoice.line')
        invoice_line = InvoiceLine()
        invoice_line.invoice = invoice
        invoice_line.type = 'line'
        invoice_line.description = description
        invoice_line.unit_price = 0
        invoice_line.quantity = 1
        invoice_line.account = account
        invoice_line.party = party
        return invoice_line

    @classmethod
    def get_insurer_account_description_line(cls, description, waiting_account
            ):
        return description + waiting_account.rec_name

    @classmethod
    def create_empty_insurer_invoices(cls, insurers, company, journal, date,
            desc, notice_kind):
        pool = Pool()
        Insurer = pool.get('insurer')

        for insurer, waiting_account in Insurer.get_insurers_waiting_accounts(
                insurers, notice_kind):
            invoice = cls.get_insurer_invoice(company, insurer, journal,
                date, notice_kind)
            invoice_lines = list(invoice.lines)
            invoice_line = cls.get_insurer_invoice_line(
                waiting_account, 0, desc)
            invoice_line.party = insurer.party
            invoice_line.invoice = invoice
            invoice_lines.append(invoice_line)
            invoice_lines.append(cls.create_empty_invoice_line(
                    cls.get_insurer_account_description_line('positive',
                        waiting_account), waiting_account, invoice,
                    party=insurer.party))
            invoice_lines.append(cls.create_empty_invoice_line(
                    cls.get_insurer_account_description_line('negative',
                        waiting_account), waiting_account, invoice,
                    party=insurer.party))
            invoice.lines = list(invoice_lines)
            invoice.save()

    @classmethod
    def retrieve_empty_insurer_invoices(cls, insurers, company, journal, desc,
            date, notice_kind):
        Insurer = Pool().get('insurer')
        insurers_invoices = defaultdict(list)
        for insurer, waiting_account in Insurer.get_insurers_waiting_accounts(
                insurers, notice_kind):
            invoice = cls.get_insurer_invoice(company, insurer, journal,
                date, notice_kind)
            invoice_line = cls.get_insurer_invoice_line(description=desc,
                account=waiting_account, invoice=invoice)
            positive_desc = cls.get_insurer_account_description_line(
                'positive', waiting_account)
            negative_desc = cls.get_insurer_account_description_line(
                'negative', waiting_account)
            positive_invoice_line = cls.get_insurer_invoice_line(
                description=positive_desc, account=waiting_account,
                invoice=invoice)
            negative_invoice_line = cls.get_insurer_invoice_line(
                description=negative_desc, account=waiting_account,
                invoice=invoice)
            insurers_invoices[invoice.id] += ((invoice, invoice_line,
                positive_invoice_line, negative_invoice_line),)
        return insurers_invoices

    @classmethod
    def select_lines(cls, accounts, with_data=False, max_date=None,
            invoice_ids=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Journal = pool.get('account.journal')

        invoice = Invoice.__table__()
        move = pool.get('account.move').__table__()
        move_line = pool.get('account.move.line').__table__()
        cursor = Transaction().connection.cursor()

        if invoice_ids is not None and len(invoice_ids) == 0:
            return [], []

        # For some reasons, joining on account_journal is horrendously
        # inefficient, so we get the ids first and inline them in the query.
        # For the record, the inefficiency is probably caused by the fact that
        # move.journal is indexed (so the new filter is very efficient) and
        # journal.type is not.
        commission_journals = Journal.search([('type', '=', 'commission')])
        reset_journals = Journal.search([('type', '=', 'commission_reset')])
        query_table = move_line.join(move, condition=move_line.move == move.id
            ).join(invoice,
            condition=(move.id.in_([invoice.move, invoice.cancel_move])
                & invoice.state.in_(['paid', 'cancel'])
                & Not(move.journal.in_([x.id for x in commission_journals])))
            | ((move.origin == coog_sql.TextCat('account.invoice,',
                        Cast(invoice.id, 'VARCHAR')))
                & move.journal.in_([x.id for x in reset_journals])))

        where_clause = (
            move_line.account.in_(accounts)
            & (move_line.principal_invoice_line == Null)
            & (move.state == 'posted'))
        if max_date is not None:
            where_clause &= (move.date <= max_date)
        if invoice_ids is not None:
            where_clause &= invoice.id.in_(invoice_ids)

        invoices_data = defaultdict(list)
        if with_data:
            cursor.execute(*query_table.select(
                    invoice.id, move_line.id.as_('move_line'),
                    move_line.account.as_('account'),
                    where=where_clause, order_by=invoice.id,
                    group_by=[invoice.id, move_line.id, move_line.account]))
            for invoice, line, account in cursor.fetchall():
                invoices_data[invoice].append((line, account))
            return invoices_data.keys(), invoices_data
        else:
            cursor.execute(*query_table.select(invoice.id,
                    where=where_clause, order_by=invoice.id,
                    group_by=[invoice.id]))
            return (invoice[0] for invoice in cursor.fetchall())

    @classmethod
    def retrieve_commissions(cls, invoices, until_date, insurers, notice_kind):
        pool = Pool()
        commission = pool.get('commission').__table__()
        cursor = Transaction().connection.cursor()
        line = pool.get('account.invoice.line').__table__()
        agent = pool.get('commission.agent').__table__()
        option = pool.get('offered.option.description').__table__()

        query_table = line.join(option
            .join(agent, condition=(option.insurer == agent.insurer) &
                option.insurer.in_(insurers))
            .join(commission, condition=(agent.id == commission.agent)),
            condition=(commission.origin == coog_sql.TextCat(
                    'account.invoice.line,', Cast(line.id, 'VARCHAR'))))

        query = query_table.select(
            line.invoice, commission.id, commission.date,
            option.account_for_billing,
            group_by=[commission.id, option.insurer, line.invoice,
                option.account_for_billing],
            where=line.invoice.in_(invoices) &
            (commission.invoice_line == Null))
        cursor.execute(*query)
        return cursor.fetchall()

    @classmethod
    def handle_lines_per_insurer(cls, until_date, invoices,
            invoices_data, insurers, notice_kind):
        pool = Pool()
        Commission = pool.get('commission')
        per_insurer = defaultdict(lambda: [[], []])
        to_ignore = defaultdict(list)
        to_sum = defaultdict(lambda: defaultdict(list))
        per_id = {x.id: x for x in invoices}
        remains = {x.id for x in invoices}

        for invoice_id, commission_id, date, insurer_account in \
                cls.retrieve_commissions([x for x in remains], until_date,
                    [i.id for i in insurers], notice_kind):
            if invoice_id in remains:
                remains.remove(invoice_id)
            if not date or not until_date or date <= until_date:
                # Ignore lines without date if invoice state is posted : we are
                # handling an unreconciled invoice
                if not date and per_id[invoice_id].state == 'posted':
                    continue
                to_sum[insurer_account][invoice_id].append(commission_id)
            else:
                to_ignore[insurer_account].append(invoice_id)

        for insurer_account, value in to_sum.iteritems():
            for invoice_id, commissions in value.iteritems():
                if invoice_id not in to_ignore[insurer_account]:
                    per_insurer[insurer_account][0] += Commission.browse(
                        commissions)
                    for line, account in invoices_data[invoice_id]:
                        per_insurer[account][1].append(line)
                else:
                    continue

        # Some invoices does not have any commissions
        # But we have to retrieve associated moves line
        for remain_invoice in remains:
            for line, account in invoices_data[remain_invoice]:
                per_insurer[account][1].append(line)

        return per_insurer

    @classmethod
    def write_commission_for_each_insurers(cls, per_insurer,
            insurers_invoices):
        pool = Pool()
        Line = pool.get('account.move.line')
        Account = pool.get('account.account')
        line = Line.__table__()
        Commission = pool.get('commission')
        commission = Commission.__table__()
        cursor = Transaction().connection.cursor()

        def is_positive(x):
            return not commission_invoice.type.startswith(x.type_)

        def get_insurer_empty_data(insurer_account, insurers_invoices):
            for insurer_values in insurers_invoices.values():
                for acc_values in insurer_values:
                    if acc_values[1].account.id == insurer_account:
                        return acc_values

        def update_columns(table, columns, values, from_=None, where=None):
            cursor.execute(*table.update(columns, values,
                    from_=from_, where=where))

        # Retrieve values for each insurers
        for insurer_account in per_insurer.keys():
            commission_invoice, commission_invoice_line, _, _ = \
                get_insurer_empty_data(insurer_account,
                    insurers_invoices)
            if (not per_insurer[insurer_account][0] and not
                    per_insurer[insurer_account][1]):
                continue

            update_columns(line, [line.principal_invoice_line],
                [commission_invoice_line.id],
                where=(line.id.in_(per_insurer[insurer_account][1])))

            positive_desc = cls.get_insurer_account_description_line(
                'positive', Account(insurer_account))
            negative_desc = cls.get_insurer_account_description_line(
                'negative', Account(insurer_account))
            positive_invoice_line = Commission.get_insurer_invoice_line(
                insurer_account, amount=0, description=positive_desc,
                invoice=commission_invoice)
            negative_invoice_line = Commission.get_insurer_invoice_line(
                insurer_account, amount=0, description=negative_desc,
                invoice=commission_invoice)
            positives = []
            negatives = []

            for comm in per_insurer[insurer_account][0]:
                if is_positive(comm):
                    positives.append(comm.id)
                else:
                    negatives.append(comm.id)

            if positives:
                update_columns(commission, [commission.invoice_line],
                    [positive_invoice_line.id],
                    where=commission.id.in_(positives))
            if negatives:
                update_columns(commission, [commission.invoice_line],
                    [negative_invoice_line.id],
                    where=commission.id.in_(negatives))


class CreateInvoicePrincipal(Wizard):
    'Create Invoice Principal'

    __name__ = 'commission.create_invoice_principal'

    start_state = 'ask'
    ask = StateView('commission.create_invoice_principal.ask',
        'commission_insurer.commission_create_invoice_principal_ask_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('account_invoice.act_invoice_form')

    @classmethod
    def create_empty_invoices(cls, insurers, company, journal, date,
            description, notice_kind):
        '''
        First step (insurer notice creation)
        This function creates empty invoices with three null lines:
        1. The principal line
        2. A negative line (used by the second step)
        3. A positive line (used by the second step)
        '''
        Commission = Pool().get('commission')
        Commission.create_empty_insurer_invoices(insurers, company,
            journal, date, description, notice_kind)

    @classmethod
    def link_invoices_and_lines(cls, insurers, until_date, company, journal,
            description, notice_kind, invoice_ids=None):
        '''
        Second step (insurer notice creation)
        This function makes the links betweens the invoices and the lines
        This also links positives and negatives found lines to
        the previously generated ones
        '''
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Commission = pool.get('commission')
        Insurer = pool.get('insurer')

        accounts = [x[1].id for x in Insurer.get_insurers_waiting_accounts(
                insurers, notice_kind)]
        # Retrieve invoices & invoices_data for the insurers accounts
        invoices, invoices_data = Commission.select_lines(accounts,
            with_data=True, max_date=until_date, invoice_ids=invoice_ids)
        if not invoices:
            return
        # Instanciate invoices
        invoices = Invoice.browse(invoices)

        # Returns : {<insurer_account> :
        # (<commission>, <invoice>, <invoice_line)}
        per_insurer = Commission.handle_lines_per_insurer(until_date,
            invoices, invoices_data, insurers, notice_kind)

        insurers_invoices = Commission.retrieve_empty_insurer_invoices(
            insurers, company, journal, description, until_date, notice_kind)
        Commission.write_commission_for_each_insurers(per_insurer,
            insurers_invoices)

    @classmethod
    def split_grouped_lines(cls, commission_invoice, positive_line,
            negative_line):
        pool = Pool()
        Commission = pool.get('commission')
        Product = pool.get('product.product')
        Agent = pool.get('commission.agent')
        Line = pool.get('account.invoice.line')
        commission = Commission.__table__()
        cursor = Transaction().connection.cursor()
        to_save = []

        query = commission.select(
            Sum(Coalesce(commission.amount, 0)).as_('amount'),
            commission.product, commission.agent,
            commission.invoice_line,
            group_by=[commission.agent, commission.product,
                commission.invoice_line],
            where=commission.invoice_line.in_(
                [positive_line.id, negative_line.id]))
        cursor.execute(*query)
        matches = []
        for amount, product, agent, invoice_line in cursor.fetchall():
            matches.append((product, agent))
            agent = Agent(agent)
            product = Product(product)
            new_invoice_line = Commission.create_empty_invoice_line(
                agent.rec_name, product.account_revenue_used,
                commission_invoice)
            if invoice_line == negative_line.id:
                new_invoice_line.unit_price = amount * -1
            else:
                new_invoice_line.unit_price = amount
            new_invoice_line.unit_price = Decimal(new_invoice_line.unit_price
                ).quantize(Decimal(10) ** -Line.unit_price.digits[1])
            new_invoice_line.product = product
            new_invoice_line.on_change_product()
            # JCA : Force account field, since on_change_product forces it to
            # the product account. TODO : Investigate what is it in
            # on_change_product that we need ?
            new_invoice_line.account = product.account_revenue_used
            to_save.append(new_invoice_line)
        Line.save(to_save)
        for line, (product, agent) in zip(to_save, matches):
            cursor.execute(*commission.update([commission.invoice_line],
                    [line.id], where=commission.invoice_line.in_(
                        [positive_line.id, negative_line.id])
                    & (commission.product == product)
                    & (commission.agent == agent)))

    @classmethod
    def finalize_invoices_and_lines(cls, insurers, company, journal,
            date, description, notice_kind):
        '''
        Third and last step (insurer notice creation)
        This function split the negative and positive lines,
        sets the amounts for each splitted lines and finally,
        clean the invoice and lines
        '''
        pool = Pool()
        cursor = Transaction().connection.cursor()
        Invoice = pool.get('account.invoice')
        Line = pool.get('account.invoice.line')
        MoveLine = pool.get('account.move.line')
        Commission = pool.get('commission')
        Event = pool.get('event')
        LineTable = MoveLine.__table__()
        insurers_invoices = Commission.retrieve_empty_insurer_invoices(
            insurers, company, journal, description, date, notice_kind)
        to_clean = []
        to_save = []
        commission_invoices = []
        for account_values in [account_values
                    for insurer_values in insurers_invoices.values()
                    for account_values in insurer_values]:
            commission_invoice, invoice_line, positive_invoice_line, \
                negative_invoice_line = account_values
            where_clause = (LineTable.principal_invoice_line ==
                invoice_line.id)
            cursor.execute(*LineTable.select(
                    Coalesce(Sum(Coalesce(LineTable.credit, 0)), 0)
                    .as_('tot_credit'),
                    Coalesce(Sum(Coalesce(LineTable.debit, 0)), 0)
                    .as_('tot_debit'),
                    where=where_clause))
            result = cursor.fetchone()
            if result and result != [[0, 0]]:
                total_credit, total_debit = result
                if commission_invoice.type == 'in':
                    amount = total_credit - total_debit
                elif commission_invoice.type == 'out':
                    amount = total_debit - total_credit
                invoice_line.unit_price = amount
                to_save.append(invoice_line)
            else:
                # No principal line
                to_clean.append(invoice_line)

            cls.split_grouped_lines(commission_invoice, positive_invoice_line,
                negative_invoice_line)
            to_clean.append(negative_invoice_line)
            to_clean.append(positive_invoice_line)
            commission_invoices.append(commission_invoice)
        commission_invoices = list(set(commission_invoices))
        Invoice.update_taxes(commission_invoices)
        Line.delete(set(to_clean))
        Line.save(to_save)
        Event.notify_events(commission_invoices,
            'commission_invoice_generated')
        return commission_invoices

    def create_insurers_notice(self, insurers):
        pool = Pool()
        Commission = pool.get('commission')
        Insurer = pool.get('insurer')
        if not insurers:
            return []
        self.create_empty_invoices(insurers, self.ask.company,
            self.ask.journal, self.ask.until_date, self.ask.description,
            self.ask.notice_kind)
        accounts = [x[1].id for x in Insurer.get_insurers_waiting_accounts(
                insurers, self.ask.notice_kind)]
        ids = Commission.select_lines(accounts, with_data=False,
            max_date=self.ask.until_date)
        self.link_invoices_and_lines(insurers, self.ask.until_date,
            self.ask.company, self.ask.journal, self.ask.description,
            self.ask.notice_kind, invoice_ids=[i for i in ids])
        invoices = self.finalize_invoices_and_lines(insurers, self.ask.company,
            self.ask.journal, self.ask.until_date, self.ask.description,
            self.ask.notice_kind)
        return invoices

    def get_insurers(self):
        if self.ask.notice_kind == 'options':
            insurers = Pool().get('insurer').search([
                    ('options.account_for_billing', '!=', None),
                    ('party', 'in', self.ask.insurers),
                    ])
            return insurers

    def do_create_(self, action):
        Invoice = Pool().get('account.invoice')
        invoices = []
        # Retrieve all insurers with a waiting_account according to the given
        # parties
        invoices = self.create_insurers_notice(self.get_insurers())

        if self.ask.post_invoices:
            Invoice.post(invoices)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [x.id for x in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}


class CreateInvoicePrincipalAsk(ModelView):
    'Create Invoice Principal'
    __name__ = 'commission.create_invoice_principal.ask'
    company = fields.Many2One('company.company', 'Company', required=True)
    insurers = fields.Many2Many('party.party', None, None, 'Insurers',
        required=True, domain=[('is_insurer', '=', True)])
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    description = fields.Text('Description', required=True)
    post_invoices = fields.Boolean('Post Invoices')
    until_date = fields.Date('Until Date')
    notice_kind = fields.Selection([('options', 'Premiums')], 'Notice Kind')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_journal():
        pool = Pool()
        Journal = pool.get('account.journal')
        journals = Journal.search([
                ('type', '=', 'commission'),
                ], limit=1)
        if journals:
            return journals[0].id

    @staticmethod
    def default_description():
        Invoice = Pool().get('account.invoice')
        return Invoice.raise_user_error('batch_premiums_received',
            raise_exception=False)

    @staticmethod
    def default_until_date():
        return coog_date.get_last_day_of_last_month(utils.today())

    @staticmethod
    def default_notice_kind():
        return 'options'

    @fields.depends('notice_kind', 'description')
    def on_change_with_description(self, name=None):
        if self.notice_kind == 'options':
            return self.default_description()
