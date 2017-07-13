# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import groupby
from sql.aggregate import Sum, Max, Min
from sql import Literal, Null

from trytond import backend
from trytond.transaction import Transaction
from trytond.model import Workflow, ModelView, Unique
from trytond.wizard import StateView, Button, StateTransition, Wizard
from trytond.wizard import StateAction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, In, Bool, PYSONEncoder, And

from trytond.modules.account_payment.payment import KINDS
from trytond.modules.coog_core import export, fields, model
from trytond.modules.coog_core import coog_date, utils, coog_string
from trytond.modules.report_engine import Printable
from trytond.modules.currency_cog import ModelCurrency

__metaclass__ = PoolMeta

__all__ = [
    'Payment',
    'MergedPaymentsMixin',
    'MergedPayments',
    'FilterPaymentsPerMergedId',
    'Configuration',
    'Journal',
    'JournalFailureAction',
    'RejectReason',
    'Group',
    'PaymentFailInformation',
    'ManualPaymentFail',
    'PaymentMotive',
    'ProcessManualFailPament',
    'ProcessPayment',
    ]


class Journal(export.ExportImportMixin):
    __name__ = 'account.payment.journal'
    _func_key = 'name'

    failure_actions = fields.One2Many('account.payment.journal.failure_action',
        'journal', 'Failure Actions',
        context={'default_fee_id': Eval('default_reject_fee')},
        depends=['default_reject_fee'])
    default_reject_fee = fields.Many2One('account.fee',
        'Default Fee', ondelete='RESTRICT')
    allow_group_deletion = fields.Boolean('Allow Group Deletion')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls._error_messages.update({
                'fail_payment_kind': 'Trying to fail different kind of'
                ' payments at the same time',
                })

    def process_actions_when_payments_failed(self, payments):
        return True

    def needs_bank_account(self):
        return False

    def get_fail_actions(self, payments):
        """
        Payments is a list of payments processed in the same payment
        transaction
        """
        if not self.process_actions_when_payments_failed(payments):
            return []
        reject_code = payments[0].fail_code
        payment_reject_number = max(len(payment.line.payments) for payment in
            payments)
        if len(set([p.kind for p in payments])) != 1:
            self.raise_user_error('fail_payment_kind')
        kind = payments[0].kind
        possible_actions = [action for action in self.failure_actions
            if action.reject_reason.code == reject_code
            and action.payment_kind == kind]
        possible_actions.sort(key=lambda x: x.reject_number, reverse=True)
        actions = []
        for action in possible_actions:
            actions += action.get_actions(reject_number=payment_reject_number)
        return actions or [('manual',)]

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'currency', 'company',
            'default_reject_fee'}

    def get_next_possible_payment_date(self, line, day):
        return coog_date.get_next_date_in_sync_with(
            max(line.maturity_date, utils.today()), day)


class JournalFailureAction(model.CoogSQL, model.CoogView):
    'Journal Failure Action'

    __name__ = 'account.payment.journal.failure_action'
    _rec_name = 'reject_reason'
    _func_key = 'func_key'

    reject_reason = fields.Many2One('account.payment.journal.reject_reason',
        'Reject Reason', required=True, ondelete='RESTRICT')
    journal = fields.Many2One('account.payment.journal', 'Journal',
        required=True, ondelete='CASCADE', select=True)
    action = fields.Selection([
            ('manual', 'Manual'),
            ('retry', 'Retry'),
            ], 'Action')
    rejected_payment_fee = fields.Many2One('account.fee',
        'Fee', ondelete='RESTRICT')
    is_fee_required = fields.Function(fields.Boolean('Fee Required'),
        'on_change_with_is_fee_required', setter='setter_void')
    reject_number = fields.Integer('Reject Number', help='Filter the action '
        'according to the number of rejects for a given payment. If empty, '
        'action will be used for all rejects')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    report_template = fields.Many2One('report.template', 'Report Template',
        domain=[('kind', '=', 'reject_payment')],
        ondelete='RESTRICT')
    payment_kind = fields.Function(
        fields.Selection(KINDS, 'Payment Kind'),
        'on_change_with_payment_kind', searcher='search_payment_kind')
    report_template_if_exceeded = fields.Many2One('report.template',
        'Report Template If Reject Number Exceeded',
        domain=[('kind', '=', 'reject_payment')],
        states={'invisible': ~Bool(Eval('reject_number'))},
        depends=['reject_number'],
        ondelete='RESTRICT', help='This template will be printed '
        'if the reject number is positive and the number of rejects '
        'for a given payment exceeds its value.')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.3: Drop code_unique constraint
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)
        table.drop_constraint('code_unique')
        super(JournalFailureAction, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        cls._error_messages.update({
                'unknown_reject_reason_code': 'Unknown reject code : %s',
                })
        cls._fail_actions_order = ['manual', 'retry', 'print']

    @classmethod
    def _export_light(cls):
        return super(JournalFailureAction, cls)._export_light() | {
            'reject_reason', 'rejected_payment_fee', 'report_template'}

    def get_actions(self, **kwargs):
        reject_number = kwargs.get('reject_number', 0)
        actions = []
        if not self.reject_number or self.reject_number == reject_number:
            actions.append((self.action,))
            if self.report_template:
                actions.append(('print', self.report_template))
        elif (self.report_template_if_exceeded and self.reject_number and
                reject_number > self.reject_number):
            actions += [('manual',),
                ('print', self.report_template_if_exceeded)]
        return actions

    @classmethod
    def get_rejected_payment_fee(cls, code, payment_kind='receivable'):
        if not code:
            return
        # TODO : Add cache on this method
        JournalFailureAction = Pool().get(
            'account.payment.journal.failure_action')
        failure_actions = JournalFailureAction.search([
                ('reject_reason.code', '=', code),
                ('payment_kind', '=', payment_kind),
                ])
        if len(failure_actions) == 0:
            cls.raise_user_error('unknown_reject_reason_code', (code))
        for failure_action in failure_actions:
            if failure_action.rejected_payment_fee:
                return failure_action.rejected_payment_fee

    @fields.depends('rejected_payment_fee')
    def on_change_with_is_fee_required(self, name=None):
        return self.rejected_payment_fee is not None

    @fields.depends('is_fee_required', 'rejected_payment_fee')
    def on_change_is_fee_required(self):
        if not self.is_fee_required:
            self.rejected_payment_fee = None
        else:
            self.rejected_payment_fee = Transaction().context.get(
                'default_fee_id', None)

    @fields.depends('reject_reason')
    def on_change_with_payment_kind(self, name=None):
        return self.reject_reason.payment_kind if self.reject_reason else None

    def get_func_key(self, name):
        return '%s|%s|%s' % (self.journal.name, self.reject_reason.code,
            self.reject_number)

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 3:
                journal_name, reject_reason_code, number = clause[2].split('|')
                return [('journal.name', clause[1], journal_name),
                    ('reject_reason.code', clause[1], reject_reason_code),
                    ('reject_number', clause[1], number)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('journal.name',) + tuple(clause[1:])],
                [('reject_reason.code',) + tuple(clause[1:])],
                ]

    @classmethod
    def search_payment_kind(cls, name, clause):
        return [('reject_reason.payment_kind',) + tuple(clause[1:])]


class RejectReason(model.CoogSQL, model.CoogView):
    'Payment Journal Reject Reason'
    __name__ = 'account.payment.journal.reject_reason'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    description = fields.Char('Description', required=True, translate=True)
    process_method = fields.Selection('get_process_method',
        'Process method', required=True)
    payment_kind = fields.Selection(KINDS, 'Payment Kind')
    failure_actions = fields.One2Many('account.payment.journal.failure_action',
        'reject_reason', 'Failure Actions', delete_missing=True,
        target_not_indexed=True)

    @classmethod
    def __setup__(cls):
        super(RejectReason, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique_per_kind', Unique(t, t.code, t.payment_kind),
                'The code must be unique'),
            ]
        cls._order = [('process_method', 'ASC'), ('code', 'ASC')]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        super(RejectReason, cls).__register__(module_name)

        table = TableHandler(cls, module_name)

        # Migration from 1.6 constraint code_unique has been renamed
        table.drop_constraint('code_unique')

    @staticmethod
    def default_payment_kind():
        return 'receivable'

    @classmethod
    def is_master_object(cls):
        return True

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.description)

    @classmethod
    def get_process_method(cls):
        Journal = Pool().get('account.payment.journal')
        return Journal.process_method.selection

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('code',) + tuple(clause[1:]),
            ('description',) + tuple(clause[1:])
            ]


class FilterPaymentsPerMergedId(Wizard):
    'Filter Payments per cheque'

    __name__ = 'account.payment.merged.open_detail'

    start_state = 'filter_payments'
    filter_payments = StateAction('account_payment.act_payment_form')

    def do_filter_payments(self, action):
        # The following active_id represents the max payment id and the
        # intermediate sql-view object id.
        payment = Pool().get('account.payment')(
            Transaction().context.get('active_id'))
        merged_id = payment.merged_id

        domain = [('merged_id', '=', merged_id)]
        action.update({'pyson_domain': PYSONEncoder().encode(domain)})
        action.update({'sequence': 40})
        return action, {}


class MergedPaymentsMixin(model.CoogSQL, model.CoogView, ModelCurrency,
        Printable):
    'Merged payments Mixin'

    merged_id = fields.Char('Merged id', readonly=True)
    amount = fields.Numeric('Amount', readonly=True,
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    journal = fields.Many2One('account.payment.journal', 'Journal',
        readonly=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('processing', 'Processing'),
            ('succeeded', 'Succeeded'),
            ('failed', 'Failed'),
            ], 'State', readonly=True)
    payments = fields.Function(
        fields.Many2Many('account.payment', None, None, 'Payments'),
        'get_payments')

    @classmethod
    def __setup__(cls):
        super(MergedPaymentsMixin, cls).__setup__()
        cls._order = [('merged_id', 'DESC')]

    @classmethod
    def _table_models(cls):
        return ['account.payment']

    @classmethod
    def get_tables(cls):
        return {x: Pool().get(x).__table__() for x in cls._table_models()}

    @classmethod
    def get_query_table(cls, tables):
        return tables['account.payment']

    @classmethod
    def get_group_by_clause(cls, tables):
        payment_table = tables['account.payment']
        return {'merged_id': payment_table.merged_id,
            'journal': payment_table.journal,
            'party': payment_table.party,
            'state': payment_table.state}

    @classmethod
    def get_where_clause(cls, tables):
        payment_table = tables['account.payment']
        return (payment_table.merged_id != Null)

    @classmethod
    def get_select_fields(cls, tables):
        payment_table = tables['account.payment']
        return {
            'id': Max(payment_table.id).as_('id'),
            'merged_id': payment_table.merged_id.as_('merged_id'),
            'journal': payment_table.journal.as_('journal'),
            'party': payment_table.party.as_('party'),
            'state': payment_table.state.as_('state'),
            'create_uid': Literal(0).as_('create_uid'),
            'create_date': Literal(0).as_('create_date'),
            'write_uid': Literal(0).as_('write_uid'),
            'write_date': Literal(0).as_('write_date'),
            'amount': Sum(payment_table.amount).as_('amount')}

    @classmethod
    def table_query(cls):
        tables = cls.get_tables()
        query_table = cls.get_query_table(tables)
        return query_table.select(
            *cls.get_select_fields(tables).values(),
            where=cls.get_where_clause(tables),
            group_by=cls.get_group_by_clause(tables).values())

    @classmethod
    def get_payments(cls, merged_payments, name):
        raise NotImplementedError

    def get_currency(self, name=None):
        return self.journal.currency if self.journal else None

    def get_contact(self):
        return self.party

    def get_sender(self):
        return self.journal.company.party

    def get_object_for_contact(self):
        # Do not reference a virtual model
        return None


class MergedPayments(MergedPaymentsMixin):
    'Merged payments'

    __name__ = 'account.payment.merged'

    @classmethod
    def get_payments(cls, merged_payments, name):
        payment = Pool().get('account.payment').__table__()
        cursor = Transaction().connection.cursor()
        res = {x.merged_id: [x.id, []] for x in merged_payments}
        cursor.execute(*payment.select(payment.id, payment.merged_id,
                where=payment.merged_id.in_(res.keys())))
        for payment_id, merged_id in cursor.fetchall():
            res[merged_id][1].append(payment_id)
        return {v[0]: v[1] for v in res.values()}

    @classmethod
    def __setup__(cls):
        super(MergedPayments, cls).__setup__()
        cls._buttons.update({
                'button_fail_merged_payments': {
                    'invisible': Not(In(Eval('state'),
                            ['processing', 'succeeded'])),
                    'icon': 'tryton-cancel',
                    }
                })

    @classmethod
    @ModelView.button_action(
        'account_payment_cog.manual_merged_payments_fail_wizard')
    def button_fail_merged_payments(cls, merged_payments):
        pass


class Payment(export.ExportImportMixin, Printable,
        model.FunctionalErrorMixIn):
    __name__ = 'account.payment'
    _func_key = 'id'

    manual_reject_code = fields.Char('Manual Reject Code')
    manual_fail_status = fields.Selection([
        ('', ''),
        ('pending', 'Pending'),
        ('done', 'Done')
        ], 'Manual Fail Status', states={
            'invisible': ~Bool(Eval('manual_fail_status'))})
    reject_description = fields.Function(
        fields.Char('Reject Description', states={
                'invisible': ~Eval('reject_description')}),
        'get_reject_description')
    merged_id = fields.Char('Merged ID', select=True,
        states={'readonly': Eval('state') != 'draft'},
        depends=['state'])
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
    color = fields.Function(fields.Char('Color'), 'get_color')
    related_invoice = fields.Function(fields.Many2One(
            'account.invoice', 'Related Invoice'), 'get_related_invoice')
    related_invoice_business_kind = fields.Function(fields.Char(
            'Related Invoice Business Kind'),
        'get_related_invoice_business_kind')
    journal_method = fields.Function(fields.Char(
            'Journal Method'),
        'get_journal_method')
    can_approve = fields.Function(fields.Boolean('Can Approve'),
        'get_can_approve')
    line_reconciled = fields.Function(fields.Boolean(
            'Line Reconciled'),
        'get_line_reconciled', searcher='search_line_reconciled')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.6: Renaming column
        TableHandler = backend.get('TableHandler')
        payment_h = TableHandler(cls, module_name)

        if payment_h.column_exist('sepa_merged_id'):
            payment_h.column_rename('sepa_merged_id', 'merged_id')
        super(Payment, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls.line.select = True
        cls._error_messages.update({
                'payments_blocked_for_party': 'Payments blocked for party %s',
                'missing_payments': 'Payments with same merged_id must '
                'be failed at the same time.',
                'transition_approve_refused': 'The transition to the approved '
                'state is not allowed on the payment with the merged id '
                '%(merged_id)s'
                })
        cls._buttons.update({
                'button_fail_payments': {
                    'invisible': Not(In(Eval('state'),
                            ['processing', 'succeeded'])),
                    'icon': 'tryton-cancel',
                    },
                'process_payments': {
                    'invisible': Eval('state') != 'approved',
                    'icon': 'tryton-go-next'
                    },
                'button_process_fail_payments': {
                    'invisible': Eval('manual_fail_status') != 'pending',
                    'icon': 'tryton-go-next'
                    },
                })
        cls.state_string = cls.state.translated('state')
        approve_states = cls._buttons['approve']['invisible']
        cls._buttons['approve']['invisible'] = And(
            approve_states, ~Eval('can_approve'))

        cls._transitions |= set((
                ('processing', 'approved'),
                ))

    @classmethod
    def view_attributes(cls):
        return super(Payment, cls).view_attributes() + [(
                '/tree',
                'colors',
                Eval('color', 'black')
                ), (
                '/form/field[@name="state"]',
                'states',
                {'field_color': Eval('color')}
                ), (
                '/form/group[@id="state_buttons"]',
                'states',
                {'invisible': True}
                )]

    def get_can_approve(self, name):
        if self.journal and self.journal.allow_group_deletion:
            return self.state in ('draft', 'processing')
        return self.state == 'draft'

    def get_line_reconciled(self, name):
        if self.line:
            return bool(self.line.reconciliation)

    @classmethod
    def search_line_reconciled(cls, name, clause):
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[1] in reverse:
            if clause[2]:
                return [('line.reconciliation', reverse[clause[1]], None)]
            else:
                return [('line.reconciliation', clause[1], None)]
        else:
            return []

    def get_journal_method(self, name):
        if self.journal:
            return self.journal.process_method

    def get_reject_description(self, name):
        pool = Pool()
        RejectReason = pool.get('account.payment.journal.reject_reason')
        if not self.fail_code:
            return ''
        reject_reasons = RejectReason.search([
                ('code', '=', self.fail_code),
                ('payment_kind', '=', self.kind),
                ])
        return reject_reasons[0].description if reject_reasons else None

    def get_icon(self, name=None):
        icon_names = ['payment']
        if self.journal and self.journal.process_method != 'manual':
            icon_names.append('auto')
            icon_names.append({'payable': 'out', 'receivable': 'in'}[self.kind])
        elif self.journal and self.journal.process_method == 'manual':
            icon_names.append('manual')
        if self.fail_code:
            icon_names.append('cancel')
        return '_'.join(icon_names)

    def get_color(self, name=None):
        key = self.state
        if key == 'failed':
            key = '%s_%s' % (key, 'reconciled' if self.line.reconciliation else
                'not_reconciled')
        return {
            'draft': 'grey',
            'processing': 'blue',
            'succeeded': 'green',
            'failed_not_reconciled': 'red',
            'failed_reconciled': 'grey',
            }.get(key, 'black')

    def get_synthesis_rec_name(self, name):
        Date = Pool().get('ir.date')
        if self.date and self.state == 'succeeded':
            return '%s - %s - %s' % (self.journal.rec_name,
                Date.date_as_string(self.date),
                self.currency.amount_as_string(self.amount))
        elif self.date:
            return '%s - %s - %s - [%s]' % (self.journal.rec_name,
                Date.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                self.state_string)
        else:
            return '%s - %s - [%s]' % (
                Date.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                self.state_string)

    def _get_transaction_key(self):
        """
        Return the key to identify payments processed in one transaction
        Overriden in account_payment_sepa_cog
        """
        return (self, self.journal)

    @classmethod
    @model.CoogView.button_action(
        'account_payment_cog.act_process_payments_button')
    def process_payments(cls, payments):
        pass

    def get_related_invoice(self, name=None):
        if self.line:
            return self.line.move.invoice.id

    def get_related_invoice_business_kind(self, name=None):
            return (self.related_invoice.business_kind if
                self.related_invoice else None)

    @property
    def fail_code(self):
        return self.manual_reject_code

    @classmethod
    @ModelView.button
    @Workflow.transition('failed')
    def fail(cls, payments):
        pool = Pool()
        Line = pool.get('account.move.line')
        Event = pool.get('event')
        FailureAction = pool.get('account.payment.journal.failure_action')
        payments = [pm for pm in payments if pm.state != 'failed']

        super(Payment, cls).fail(payments)
        Event.notify_events(payments, 'fail_payment')

        # Remove payment_date on payment line
        lines = [payment.line for payment in payments
            if payment.line is not None]
        Line.write(lines, {'payment_date': None})

        actions = defaultdict(list)
        payments_keys = [(x._get_transaction_key(), x) for x in payments]
        payments_keys = sorted(payments_keys, key=lambda x: x[0])
        for key, payments in groupby(payments_keys, key=lambda x: x[0]):
            payments_list = [payment[1] for payment in payments]
            reject_actions = key[1].get_fail_actions(payments_list)
            for action in reject_actions:
                if action[0] == 'print':
                    actions['fail_print'].extend([(action[1],
                        payments_list)])
                else:
                    actions['fail_%s' % action[0]].extend(payments_list)

        for action in FailureAction._fail_actions_order:
            getattr(cls, 'fail_%s' % action)(actions['fail_%s' % action])

    @classmethod
    def fail_manual(cls, payments):
        cls.write(payments, {
                'manual_fail_status': 'pending',
                })

    @classmethod
    def fail_retry(cls, payments):
        pass

    @classmethod
    def get_objects_for_fail_prints(cls, report, payments):
        MergedPayment = Pool().get('account.payment.merged')
        if report.on_model.model == 'account.payment.merged':
            merged_ids = list(set(x.merged_id for x in payments))
            payments = MergedPayment.search(
                [('merged_id', 'in', merged_ids)])
        return payments

    @classmethod
    def fail_print(cls, to_prints):
        for report, payments in to_prints:
            to_print = cls.get_objects_for_fail_prints(report, payments)
            report.produce_reports(to_print)

    @fields.depends('line')
    def on_change_line(self):
        super(Payment, self).on_change_line()
        if self.line:
            self.date = self.line.payment_date

    @classmethod
    def is_master_object(cls):
        return True

    def get_description(self, lang=None):
        return self.description

    @classmethod
    def approve(cls, payments):
        with model.error_manager():
            for payment in payments:
                if (payment.kind == 'payable'
                        and payment.party.block_payable_payments):
                    cls.append_functional_error(
                        'payments_blocked_for_party', payment.party.rec_name)
                if not payment.can_approve:
                    cls.append_functional_error(
                        'transition_approve_refused', {
                            'merged_id': payment.merged_id,
                            })
        super(Payment, cls).approve(payments)

    @classmethod
    def _set_group(cls, payment_ids, group):
        cls.write(cls.browse(payment_ids), {'group': group.id})

    @classmethod
    def set_description(cls, payments):
        to_write = []
        for payment in payments:
            description = payment.get_description()
            if description != payment.description:
                to_write += [[payment], {'description': description}]
        if to_write:
            cls.write(*to_write)

    @classmethod
    @Workflow.transition('processing')
    def process(cls, payments, group):
        pool = Pool()
        Event = pool.get('event')
        group = super(Payment, cls).process(payments, group)
        cls.set_description(payments)
        Event.notify_events([group], 'payment_group_created')
        Event.notify_events(payments, 'process_payment')
        return group

    @classmethod
    def succeed(cls, payments):
        pool = Pool()
        Event = pool.get('event')
        super(Payment, cls).succeed(payments)
        cls.write(payments, {
            'manual_reject_code': None,
            'manual_fail_status': ''})
        Event.notify_events(payments, 'succeed_payment')

    def get_doc_template_kind(self):
        res = super(Payment, self).get_doc_template_kind()
        res.append('reject_payment')
        return res

    def get_contact(self):
        return self.party

    def get_sender(self):
        return self.company.party

    @classmethod
    def payments_fields_to_update_after_fail(cls, reject_reason):
        return {'manual_reject_code': reject_reason.code}

    def get_grouping_key(self):
        return self.merged_id if self.merged_id else self.id

    @classmethod
    def manual_set_reject_reason(cls, payments, reject_reason):
        merged_ids = set([p.merged_id for p in payments if p.merged_id])
        if merged_ids:
            all_payments = cls.search([
                    ('merged_id', 'in', merged_ids)])
            if len(all_payments) != len(
                    [x for x in payments if x.merged_id]):
                cls.raise_user_error('missing_payments')
        fields = cls.payments_fields_to_update_after_fail(reject_reason)
        cls.write(payments, fields)

    @classmethod
    @ModelView.button_action('account_payment_cog.manual_payment_fail_wizard')
    def button_fail_payments(cls, payments):
        pass

    @classmethod
    @ModelView.button_action(
        'account_payment_cog.process_manual_payment_fail_wizard')
    def button_process_fail_payments(cls, payments):
        pass


class Configuration:
    __name__ = 'account.configuration'

    direct_debit_journal = fields.Property(
        fields.Many2One('account.payment.journal', 'Direct Debit Journal',
            domain=[('process_method', '!=', 'manual')]))
    reject_fee_journal = fields.Property(
        fields.Many2One('account.journal', 'Reject Fee Journal',
            domain=[('type', '=', 'write-off')]))

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        values = super(Configuration, self).export_json(skip_fields,
            already_exported, output, main_object, configuration)

        if 'direct_debit_journal' not in values:
            return values
        field_value = getattr(self, 'direct_debit_journal')
        values['direct_debit_journal'] = {'_func_key': getattr(
            field_value, field_value._func_key)}
        return values

    def get_payment_journal(self, line):
        return self.direct_debit_journal


class Group(Workflow, ModelCurrency, export.ExportImportMixin, Printable,
        model.FunctionalErrorMixIn):
    __name__ = 'account.payment.group'

    _func_key = 'number'

    processing_payments = fields.One2ManyDomain('account.payment', 'group',
        'Processing Payments',
        domain=[('state', '=', 'processing')])
    amount = fields.Function(
        fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount')
    payment_dates = fields.Function(
        fields.Char('Payment Dates'),
        'get_payment_dates')
    state = fields.Selection([
            ('processing', 'Processing'),
            ('to_acknowledge', 'To Acknowledge'),
            ('acknowledged', 'Acknowledged'),
            ('failed', 'Failed'),
            ], 'State', readonly=True, select=True)
    payment_date_min = fields.Function(fields.Date(
            'Payment Date Min'),
        'get_payment_date_min', searcher='search_payment_date_min')
    process_method = fields.Function(
        fields.Char('Process Method'), 'on_change_with_process_method')
    color = fields.Function(fields.Char('color'), 'get_color')

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._transitions |= set((
                ('processing', 'to_acknowledge'),
                ('processing', 'failed'),
                ('to_acknowledge', 'acknowledged'),
                ('to_acknowledge', 'failed'),
                ('failed', 'acknowledged'),
                ('to_acknowledge', 'processing'),
                ('processing', 'acknowledged'),
                ))
        cls._buttons.update({
                'processing': {
                    'invisible': (Eval('state') == 'acknowledged') |
                    (Eval('state') == 'processing') |
                    (Eval('state') == 'failed'),
                    },
                'to_acknowledge': {
                    'invisible': (Eval('state') == 'acknowledged') |
                    (Eval('state') == 'to_acknowledge') |
                    (Eval('state') == 'failed'),
                    },
                'acknowledge': {
                    'invisible': (Eval('state') == 'acknowledged'),
                    },
                'fail': {
                    'invisible': (Eval('state') == 'failed') |
                    (Eval('state') == 'to_acknowledge'),
                    },
                })
        cls._error_messages.update({
                'reject_reason_not_found': 'The reason code on journal %s '
                'is not found',
                'prematurely_ack_group': 'The payment group %(number)s '
                'should not be acknowledged: %(date)s < %(payment_date)s',
                'non_deletable': 'The payment group %(number)s is not '
                'deletable',
                'group_with_invalid_payments': 'The payment group %(number)s '
                'has payment(s) which does not allow the deletion',
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        group_h = TableHandler(cls, module_name)
        to_migrate = not group_h.column_exist('state')
        super(Group, cls).__register__(module_name)
        if to_migrate:
            pool = Pool()
            cursor = Transaction().connection.cursor()
            payment = pool.get('account.payment').__table__()
            group = cls.__table__()

            group_selection = payment.select(payment.group,
                where=((payment.state == 'succeeded') &
                    (payment.group != Null)))

            cursor.execute(*group.update(columns=[group.state],
                values=[Literal('acknowledged')],
                where=group.id.in_(group_selection)))
            cursor.execute(*group.update(columns=[group.state],
                    values=[Literal('processing')],
                    where=group.state == Null))

    @classmethod
    def view_attributes(cls):
        return super(Group, cls).view_attributes() + [
            ('/tree', 'colors', Eval('color')),
            ]

    @classmethod
    def delete(cls, instances):
        cls.delete_payments(instances)
        super(Group, cls).delete(instances)

    @classmethod
    def _export_skips(cls):
        return super(Group, cls)._export_skips() | {'payments',
            'processing_payments'}

    @classmethod
    def _export_light(cls):
        return super(Group, cls)._export_light() | {'journal', 'company'}

    @staticmethod
    def default_state():
        return 'processing'

    def get_color(self, name):
        if self.state == 'processing':
            return 'blue'
        elif self.state == 'failed':
            return 'grey'
        return 'black'

    @classmethod
    @Workflow.transition('failed')
    def _failed(cls, groups):
        pass

    @classmethod
    @ModelView.button_action('account_payment_cog.manual_payment_fail_wizard')
    def fail(cls, groups):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    def processing(cls, groups):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('to_acknowledge')
    def to_acknowledge(cls, groups):
        Pool().get('event').notify_events(groups, 'group_acknowledge_planned')

    @classmethod
    @ModelView.button
    @Workflow.transition('acknowledged')
    def acknowledge(cls, groups):
        Payment = Pool().get('account.payment')
        payments = []
        with model.error_manager():
            for group in groups:
                if group.payment_date_min > utils.today():
                    cls.append_functional_error('prematurely_ack_group', {
                            'number': group.number,
                            'payment_date': group.payment_date_min,
                            'date': utils.today(),
                            })
                payments.extend(group.processing_payments)
        if payments:
            Payment.succeed(payments)

    @classmethod
    def delete_payments(cls, groups):
        to_process = defaultdict(list)

        def order_state(p):
            return p.state
        with model.error_manager():
            for group in groups:
                group.check_deletable()
                payments = sorted(group.payments, key=order_state)
                for state, payments in groupby(payments, order_state):
                    to_process[state].extend(list(payments))
        actions = cls.get_delete_actions()
        for state, payments in to_process.iteritems():
            next_state = state
            while next_state:
                function, next_state = actions[next_state]
                function(payments)

    @classmethod
    def get_delete_actions(cls):
        Payment = Pool().get('account.payment')
        return {
            'processing': (lambda x: Payment.approve(x), 'approved'),
            'approved': (lambda x: Payment.draft(x), 'draft'),
            'draft': (lambda x: Payment.delete(x), None),
            }

    def is_deletable(self):
        if self.journal:
            return self.journal.allow_group_deletion

    def check_deletable(self):
        if not self.is_deletable():
            self.append_functional_error('non_deletable',
                {'number': self.number})
        if any(x.state in ('succeeded', 'failed')
                for x in self.payments):
            self.append_functional_error('group_with_invalid_payments',
                {'number': self.number})

    @classmethod
    def update_payments(cls, groups, method_name, state=None):
        super(Group, cls).update_payments(groups, method_name, state)
        if method_name == 'fail':
            cls.write(groups, {'state': 'acknowledged'})

    @classmethod
    def reject_payment_group(cls, groups, reject_code, *args):
        pool = Pool()
        RejectReason = pool.get('account.payment.journal.reject_reason')
        Payment = pool.get('account.payment')
        Group = pool.get('account.payment.group')

        def group_per_journal(g):
            return g.journal

        groups = sorted(groups, key=group_per_journal)
        for journal, sub_groups in groupby(groups, group_per_journal):
            sub_groups = list(sub_groups)
            reject_reasons = RejectReason.search([
                    ('code', '=', reject_code),
                    ('failure_actions.journal', '=', journal.id)
                    ])
            if not reject_reasons:
                cls.raise_user_error('reject_reason_not_found', journal.name)
            reject_reason, = reject_reasons
            payments = sum(
                [list(g.processing_payments) for g in sub_groups], [])
            Payment.manual_set_reject_reason(payments, reject_reason)
            Group.update_payments(sub_groups, 'fail')

    @classmethod
    def succeed_payment_group(cls, groups, **kwargs):
        cls.to_acknowledge(groups)

    def get_currency(self):
        return self.journal.currency if self.journal else None

    @classmethod
    def get_amount(cls, groups, name):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        account_payment = pool.get('account.payment').__table__()
        result = {x.id: None for x in groups}

        cursor.execute(*account_payment.select(
                account_payment.group, Sum(account_payment.amount),
                where=account_payment.group.in_([x.id for x in groups]),
                group_by=[account_payment.group]))

        for group_id, amount in cursor.fetchall():
            result[group_id] = amount
        return result

    @classmethod
    def get_payment_dates(cls, groups, name):
        pool = Pool()
        Date = pool.get('ir.date')
        return {k: ', '.join([Date.date_as_string(x) for x in v])
            for k, v in cls.get_payment_dates_per_group(groups, name
                ).iteritems()}

    @classmethod
    def get_payment_dates_per_group(cls, groups, name):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        account_payment = pool.get('account.payment').__table__()
        res_dict = {x.id: [] for x in groups}

        cursor.execute(*account_payment.select(
                account_payment.group, account_payment.date,
                where=account_payment.group.in_([x.id for x in groups]),
                group_by=[account_payment.group, account_payment.date]))

        for group_id, date in cursor.fetchall():
            res_dict[group_id].append(date)
        return res_dict

    @classmethod
    def search_payment_date_min(cls, name, clause):
        group = cls.__table__()
        Payment = Pool().get('account.payment')
        payment = Payment.__table__()
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        query = payment.join(
            group, condition=(payment.group == group.id)).select(
            group.id, group_by=[group.id], having=Operator(
                Min(payment.date), Payment.date.sql_format(value)))
        return [('id', 'in', query)]

    @classmethod
    def get_payment_date_min(cls, groups, name=None):
        res = {}
        if not groups:
            return res
        cursor = Transaction().connection.cursor()
        group = cls.__table__()
        payment = Pool().get('account.payment').__table__()
        query_table = payment.join(group, condition=(
                payment.group == group.id))
        cursor.execute(*query_table.select(group.id, Min(payment.date),
                where=group.id.in_([x.id for x in groups]),
                group_by=[group.id]))
        for group_id, min_date in cursor.fetchall():
            res[group_id] = min_date
        return res

    def merge_payment_key(self, payment):
        return (('merged_id', payment.merged_id),
            ('party', payment.party),
            ('currency', payment.currency),
            )

    def get_contact(self):
        return self.journal.company.party

    def get_sender(self):
        return self.journal.company.party

    @fields.depends('journal')
    def on_change_with_process_method(self, name=None):
        return self.journal.process_method if self.journal else None


class PaymentMotive(model.CoogSQL, model.CoogView):
    'Payment Motive'

    __name__ = 'account.payment.motive'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)

    @classmethod
    def __setup__(cls):
        super(PaymentMotive, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


class PaymentFailInformation(model.CoogView):
    'Payment Fail Information'
    __name__ = 'account.payment.fail_information'

    reject_reason = fields.Many2One('account.payment.journal.reject_reason',
        'Reject Reason', depends=['process_method', 'payment_kind'],
        domain=[
            ('process_method', '=', Eval('process_method')),
            ('payment_kind', '=', Eval('payment_kind')),
            ],
        required=True)
    payments = fields.One2Many('account.payment', None, 'Payments',
        readonly=True)
    process_method = fields.Char('Process Method')
    payment_kind = fields.Char('Payment Kind')

    @classmethod
    def __setup__(cls):
        super(PaymentFailInformation, cls).__setup__()
        cls._error_messages.update({
                'mixing_payment_methods': 'Trying to fail different payment'
                ' methods at the same time',
                'mixing_payment_kinds': 'Trying to fail different payment'
                ' kinds at the same time',
                })

    @fields.depends('payments')
    def on_change_payments(self):
        if not self.payments:
            return
        methods = set([p.journal.process_method for p in self.payments])
        if len(methods) == 1:
            self.process_method = list(methods)[0]
        else:
            self.raise_user_error('mixing_payment_methods')
        kinds = set([p.kind for p in self.payments])
        if len(kinds) == 1:
            self.payment_kind = list(kinds)[0]
        else:
            self.raise_user_error('mixing_payment_kinds')


class ManualPaymentFail(model.CoogWizard):
    'Fail Payment'
    __name__ = 'account.payment.manual_payment_fail'

    start_state = 'fail_information'
    fail_information = StateView('account.payment.fail_information',
        'account_payment_cog.payment_fail_information_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Fail Payments', 'fail_payments', 'tryton-ok', default=True)
            ])
    fail_payments = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ManualPaymentFail, cls).__setup__()
        cls._error_messages.update({
                'not_same_payment_method': 'Selected payments must have the '
                'same payment method.',
                'payment_must_be_succeed_processing': 'Selected payments '
                'status must be succeeded or processing',
                'multiple_journal_fail': 'You cannot fail payments with '
                'differents journal process methods at the same time',
                })

    def default_fail_information(self, values):
        pool = Pool()
        Payment = pool.get('account.payment')
        active_model = Transaction().context.get('active_model')
        active_ids = Transaction().context.get('active_ids')
        if active_model == 'account.payment.merged':
            payments = Payment.browse(active_ids)
            merged_ids = [x.merged_id for x in payments]
            active_ids = [x.id for x in Payment.search(
                    [('merged_id', 'in', merged_ids)])]
        if active_model == 'account.payment.group':
            Group = pool.get('account.payment.group')
            groups = Group.browse(active_ids)
            if len({x.process_method for x in groups}) > 1:
                self.raise_user_error('multiple_journal_fail')
            active_ids = [p.id for group in groups for p in group.payments]
        if any([x.state not in ('succeeded', 'processing')
                for x in Payment.browse(active_ids)]):
            self.raise_user_error('payment_must_be_succeed_processing')
        return {
            'payments': active_ids
            }

    def transition_fail_payments(self):
        pool = Pool()
        active_model = Transaction().context.get('active_model')
        Payment = pool.get('account.payment')
        if not self.fail_information.process_method:
            self.raise_user_error('not_same_payment_method')
        Payment.manual_set_reject_reason(list(self.fail_information.payments),
            self.fail_information.reject_reason)
        Payment.fail(list(self.fail_information.payments))
        if active_model == 'account.payment.group':
            Group = pool.get('account.payment.group')
            groups = list({p.group for p in self.fail_information.payments})
            Group._failed(groups)
        return 'end'


class ProcessManualFailPament(model.CoogWizard):
    'Process Manual Fail Payment'
    __name__ = 'account.payment.process_manual_fail_payment'

    start_state = 'set_fail_status'
    set_fail_status = StateTransition()

    def transition_set_fail_status(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        active_ids = Transaction().context.get('active_ids')
        Payment.write(Payment.browse(active_ids),
            {'manual_fail_status': 'done'})
        return 'end'


class ProcessPayment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.process'

    pre_process = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ProcessPayment, cls).__setup__()
        for button in cls.start.buttons:
            if button.state == 'process':
                button.state = 'pre_process'
                break

    def default_start(self, name):
        return super(ProcessPayment, self).default_start(name)

    def transition_pre_process(self):
        return 'process'
