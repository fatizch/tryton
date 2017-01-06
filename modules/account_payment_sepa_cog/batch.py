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
    'PaymentTreatmentBatch',
    'PaymentFailBatch',
    ]


class PaymentTreatmentBatch:
    __name__ = 'account.payment.process'

    @classmethod
    def __setup__(cls):
        super(PaymentTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': '0',
                })

    @classmethod
    def _group_payment_key(cls, payment):
        res = super(PaymentTreatmentBatch, cls)._group_payment_key(payment)
        journal = payment.journal
        if journal.process_method == 'sepa' and \
                journal.split_sepa_messages_by_sequence_type:
            res = res + (('sequence_type', payment.sepa_mandate_sequence_type
                    or payment.sepa_mandate.sequence_type),)
        return res

    @classmethod
    def execute(cls, objects, ids, **kwargs):
        Group = Pool().get('account.payment.group')
        groups = Group.browse(super(PaymentTreatmentBatch, cls).execute(
                objects, ids, **kwargs))
        dirpath = kwargs.get('out', None) or cls.generate_filepath()
        out_filepaths = []
        for payments_group in groups:
            if payments_group.journal.process_method == 'sepa':
                out_filepaths = payments_group.dump_sepa_messages(dirpath)
                if out_filepaths:
                    log_msg = "SEPA message of %s written to '%s'" % (
                        payments_group, out_filepaths[0])
            if len(out_filepaths) == 1:
                cls.logger.info(log_msg)
            if len(out_filepaths) > 1:
                cls.logger.warning('Only last ' + log_msg)
                raise Exception("Multiple sepa messages with "
                    "'waiting' status for  %s" % payments_group)
        return [group.id for group in groups]


class PaymentFailBatch(batch.BatchRootNoSelect):
    'Payment Fail Batch'

    __name__ = 'account.payment.fail'

    @classmethod
    def execute(cls, object, ids, **kwargs):
        in_directory = kwargs.get('in', None) or cls.get_conf_item('in')
        out_directory = kwargs.get('out', None) or cls.get_conf_item('out')
        treatment_date_str = kwargs.get('treatment_date', None)
        treatment_date = datetime.datetime.strptime(treatment_date_str,
            '%Y-%m-%d').date()
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
