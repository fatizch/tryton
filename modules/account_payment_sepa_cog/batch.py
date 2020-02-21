# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import codecs
import os
from lxml import etree
from trytond.server_context import ServerContext

from sql import Null

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch, utils
from .sepa_handler import CAMT054CoogPassive

__all__ = [
    'PaymentSepaDoBatch',
    'PaymentTreatmentBatch',
    'PaymentFailBatch',
    'PaymentFailMessageCreationBatch',
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


class PaymentTreatmentBatch(metaclass=PoolMeta):
    __name__ = 'account.payment.process'

    @classmethod
    def __setup__(cls):
        super(PaymentTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0
                })

    @classmethod
    def select_ids_regroup_key(cls, payment, payment_kind):
        if payment.journal.process_method == 'sepa':
            return payment.sepa_mandate if payment_kind == 'receivable' \
                else payment.payer
        return super(PaymentTreatmentBatch, cls).select_ids_regroup_key(
            payment, payment_kind)


class PaymentFailBatch(batch.BatchRootNoSelect):
    'Payment Fail Batch'

    __name__ = 'account.payment.fail'

    @classmethod
    def __setup__(cls):
        super(PaymentFailBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 10,
                })

    @classmethod
    def get_paths_to_create(cls):
        return super().get_paths_to_create() + ['in_directory']

    @classmethod
    def select_ids(cls, in_directory=None, treatment_date=None):
        in_directory = in_directory or\
            cls.get_batch_configuration().get('in_directory', None)
        if not in_directory:
            raise Exception("'in_directory' is required")
        handler = CAMT054CoogPassive()
        files = cls.get_file_names_and_paths(in_directory)
        all_elements = []
        for file_name, file_path in files:
            with codecs.open(file_path, 'r') as _file:
                source = _file.read().encode('utf8')
                all_elements.extend(
                    [(x,) for x in handler.extract_elements(source,
                            to_string=True)])
        return all_elements

    @classmethod
    def execute(cls, objects, ids, in_directory=None, treatment_date=None):
        if not ids:
            return
        handler = CAMT054CoogPassive()
        with ServerContext().set_context(disable_auto_aggregate=True,
                treatment_date=treatment_date):
            for text_element in ids:
                element = etree.fromstring(text_element)
                handler.handle_entry(element)
        return ids


class PaymentFailMessageCreationBatch(batch.BatchRootNoSelect):
    'Payment Fail Message Creation Batch'

    __name__ = 'account.payment.fail.message.create'

    @classmethod
    def __setup__(cls):
        super(PaymentFailMessageCreationBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                })

    @classmethod
    def parse_params(cls, params):
        params = super(PaymentFailMessageCreationBatch, cls).parse_params(
            params)
        assert params.get('job_size') == 0
        return params

    @classmethod
    def execute(cls, objects, ids, in_directory=None, archive=None):
        pool = Pool()
        Message = pool.get('account.payment.sepa.message')
        Payment = pool.get('account.payment')
        if not in_directory or not archive:
            raise Exception("'in_directory' and 'archive' are required")
        files = cls.get_file_names_and_paths(in_directory)
        if os.path.isfile(in_directory):
            files = [(os.path.basename(in_directory), in_directory)]
        else:
            files = [(f, os.path.join(in_directory, f)) for f in os.listdir(
                    in_directory) if os.path.isfile(os.path.join(
                                in_directory, f))]
        handler = CAMT054CoogPassive()
        messages = []
        all_failed = []
        for file_name, file_path in files:
            with codecs.open(file_path, 'r') as _file:
                source = _file.read()
                source_bytes = source.encode('utf8')
                message = Message()
                message.company = Transaction().context.get('company')
                message.type = 'in'
                message.message = source
                message.state = 'done'
                messages.append(message)
                failed_payments = sum((handler.get_payments(element)
                    for element in handler.extract_elements(
                            source_bytes)), [])
                all_failed.extend(failed_payments)
                Payment.finalize_fail_batch(failed_payments)
        if messages:
            Message.save(messages)
        cls.archive_treated_files(files, archive, utils.today())
        return [x.id for x in all_failed]


class PaymentGroupCreationBatch(metaclass=PoolMeta):
    __name__ = 'account.payment.group.create'

    @classmethod
    def _group_payment_key(cls, payment):
        # payment.party return a new instance of Column
        # -> equality is tested using table and name fields
        return tuple((x for x in
                    super(PaymentGroupCreationBatch, cls
                        )._group_payment_key(payment) if x.name !=
                    payment.party.name or x.table != payment.party.table)) + \
            (payment.sepa_mandate, payment.sepa_mandate_sequence_type)

    @classmethod
    def get_payment_where_clause(cls, payment, payment_kind, treatment_date,
            journal_methods):
        clause = super(PaymentGroupCreationBatch,
            cls).get_payment_where_clause(payment, payment_kind, treatment_date,
                journal_methods)
        if payment_kind == 'receivable' and journal_methods == 'sepa':
            clause &= (payment.sepa_mandate != Null)
        return clause


class PaymentGroupProcessBatch(metaclass=PoolMeta):
    __name__ = 'account.payment.group.process'

    @classmethod
    def _process_group(cls, group):
        if group.journal.process_method != 'sepa':
            return super(PaymentGroupProcessBatch, cls)._process_group(group)
        group.generate_message(_save=True)


class PaymentJournalUpdateSepa(batch.BatchRootNoSelect):
    'Sepa Payment Journal Update Batch'
    __name__ = 'account.payment.journal.update.sepa'

    @classmethod
    def execute(cls, objects, ids):
        Group = Pool().get('account.payment.group')
        Group.update_last_sepa_receivable_date()
