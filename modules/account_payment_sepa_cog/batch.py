# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import codecs
import os
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__metaclass__ = PoolMeta
__all__ = [
    'PaymentSepaDoBatch',
    'PaymentTreatmentBatch',
    'PaymentFailBatch',
    'PaymentGroupCreationBatch',
    'PaymentGroupProcessBatch',
    'PaymentJournalUpdateSepa',
    ]


class PaymentSepaDoBatch(batch.BatchRoot):
    'Payment Sepa Do Batch'
    __name__ = 'account.payment.do_sepa_messages'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment.sepa.message'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.payment.sepa.message'

    @classmethod
    def get_batch_domain(cls, **kwargs):
        return [('type', '=', 'out'), ('state', '=', 'waiting')]

    @classmethod
    def execute(cls, objects, ids, **kwargs):
        Message = Pool().get('account.payment.sepa.message')
        Message.do(objects)
        return [o.id for o in objects]


class PaymentTreatmentBatch:
    __name__ = 'account.payment.process'

    @classmethod
    def __setup__(cls):
        super(PaymentTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0
                })

    @classmethod
    def _group_payment_key(cls, payment):
        res = super(PaymentTreatmentBatch, cls)._group_payment_key(payment)
        journal = payment.journal
        if (journal.process_method == 'sepa' and
                journal.split_sepa_messages_by_sequence_type):
            res = res + (('sequence_type', payment.sepa_mandate_sequence_type
                    or payment.sepa_mandate.sequence_type),)
        return res


class PaymentFailBatch(batch.BatchRootNoSelect):
    'Payment Fail Batch'

    __name__ = 'account.payment.fail'

    @classmethod
    def execute(cls, object, ids, **kwargs):
        in_directory = kwargs.get('in', None) or cls.get_conf_item('in')
        out_directory = kwargs.get('out', None) or cls.get_conf_item('out')
        treatment_date = kwargs.get('treatment_date', None)
        if not in_directory or not out_directory:
            raise Exception("'in' and 'out' are required")
        files = cls.get_file_names_and_paths(in_directory)
        if os.path.isfile(in_directory):
            files = [(os.path.basename(in_directory), in_directory)]
        else:
            files = [(f, os.path.join(in_directory, f)) for f in os.listdir(
                    in_directory) if os.path.isfile(os.path.join(
                                in_directory, f))]
        Message = Pool().get('account.payment.sepa.message')
        messages = []
        for file_name, file_path in files:
            message = Message()
            message.state = 'draft'
            message.company = Transaction().context.get('company')
            message.type = 'in'
            with codecs.open(file_path, 'r', 'utf-8') as _file:
                message.message = _file.read().decode('utf-8')
                messages.append(message)
        if messages:
            Message.save(messages)
            Message.wait(messages)
            Message.do(messages)
        cls.archive_treated_files(files, out_directory, treatment_date)


class PaymentGroupCreationBatch:
    __name__ = 'account.payment.group.create'

    @classmethod
    def _group_payment_key(cls, payment):
        return super(PaymentGroupCreationBatch, cls)._group_payment_key(
            payment) + (payment.sepa_mandate,
                payment.sepa_mandate_sequence_type)

    @classmethod
    def group_by_key_func(cls, payment_row):
        res = super(PaymentGroupCreationBatch, cls).group_by_key_func(
            payment_row)
        Journal = Pool().get('account.payment.journal')
        journal = Journal(payment_row[1])
        Mandate = Pool().get('account.payment.sepa.mandate')
        if (journal.process_method == 'sepa' and payment_row[2] == 'receivable'
                and journal.split_sepa_messages_by_sequence_type):
            # index 4 is the sequence_type and index 3 is the mandate
            return res + tuple([payment_row[4] or
                Mandate(payment_row[3]).sequence_type])
        return res

    @classmethod
    def get_payment_where_clause(cls, payment, payment_kind, treatment_date,
            journal_methods):
        clause = super(PaymentGroupCreationBatch,
            cls).get_payment_where_clause(payment, payment_kind, treatment_date,
                journal_methods)
        if payment_kind == 'receivable' and journal_methods == 'sepa':
            clause &= (payment.sepa_mandate != None)
        return clause


class PaymentGroupProcessBatch:
    __name__ = 'account.payment.group.process'

    @classmethod
    def _process_group(cls, group):
        if group.journal.process_method != 'sepa':
            return super(PaymentGroupProcessBatch, cls)._process_group(group)
        Payment = Pool().get('account.payment')
        Payment.write(list(group.payments), {'state': 'processing'})
        group.generate_message(_save=True)


class PaymentJournalUpdateSepa(batch.BatchRootNoSelect):
    'Sepa Payment Journal Update Batch'
    __name__ = 'account.payment.journal.update.sepa'

    @classmethod
    def execute(cls, objects, ids):
        Group = Pool().get('account.payment.group')
        Group.update_last_sepa_receivable_date()
