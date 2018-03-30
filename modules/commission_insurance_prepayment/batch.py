# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import logging

from trytond.pool import Pool
from trytond.tools import grouped_slice

from trytond.modules.coog_core import batch, utils, coog_string


__all__ = [
    'DesynchronizedPrepaymentReport',
    ]


class DesynchronizedPrepaymentReport(batch.BatchRoot):
    "Prepayment Synchronization Batch"

    __name__ = 'desynchronized.prepayment.report'

    logger = logging.getLogger(__name__)

    @classmethod
    def _get_fields_name(cls):
        return ('contract', 'party', 'agent', 'paid_amount',
            'generated_amount', 'actual_amount', 'theoretical_amount',
            'deviation_amount', 'number_of_date', 'dates', 'description',
            'codes')

    @classmethod
    def write_headers(cls, filename):
        Model = Pool().get('prepayment.sync.show.displayer')
        fields_ = cls._get_fields_name()
        fields_string = (getattr(Model, x).string for x in fields_)
        with utils.safe_open(filename, 'ab') as fo_:
            fo_.write(';'.join([coog_string.translate(Model, f, fs, 'field'
                            ).encode('utf-8')
                        for f, fs in zip(fields_, fields_string)]) + '\n')

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date, filename, auto_adjust):
        commissions = Pool().get('commission').search([
                ('commissioned_contract', '!=', None),
                ('agent.plan.is_prepayment', '=', True),
                ])
        ids = list({(x.commissioned_contract.id,) for x in commissions})
        if ids:
            cls.write_headers(filename)
            if auto_adjust:
                splitted_fname = os.path.splitext(filename)
                filename = '%s%s' % (splitted_fname[0] + '_auto_adjsut',
                    splitted_fname[1] or '')
                cls.write_headers(filename)
            return ids

    @classmethod
    def flush(cls, lines, filename):
        with utils.safe_open(filename, 'ab') as fo_:
            line_def = ';'.join(['{' + x + '}' for x in
                cls._get_fields_name()])
            fo_.write('\n'.join([line_def.format(**line)
                        for line in lines]))
            fo_.write('\n')

    @classmethod
    def beautify(cls, obj):
        obj['contract'] = obj['contract'].contract_number.encode('utf-8')
        obj['party'] = obj['party'].rec_name.encode('utf-8')
        obj['agent'] = obj['agent'].rec_name.encode('utf-8')
        obj['description'] = obj['description'].encode('utf-8').replace(
            '\n', ' ')
        obj['codes'] = obj['codes'].encode('utf-8').replace('\n', ', ')
        obj['dates'] = ', '.join(obj['dates'])

    @classmethod
    def execute(cls, objects, ids, treatment_date, filename, auto_adjust):
        Contract = Pool().get('contract')
        for sliced_objects in grouped_slice(objects):
            lines_to_write = []
            per_contracts = Contract.get_prepayment_deviations(sliced_objects)
            for contract, deviations in per_contracts.items():
                if auto_adjust:
                    contract.try_adjust_prepayments(deviations)
                Contract._add_prepayment_deviations_description(deviations)
                lines_to_write += (deviations)
            for obj in lines_to_write:
                cls.beautify(obj)
            if lines_to_write:
                cls.flush(lines_to_write, filename)
        if auto_adjust:
            splitted_fname = os.path.splitext(filename)
            filename = '%s%s' % (splitted_fname[0] + '_auto_adjust',
                splitted_fname[1] or '')
            cls.execute(objects, ids, treatment_date, filename, False)
