# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    @classmethod
    def __register__(cls, module_name):
        model_data = Pool().get('ir.model.data').__table__()
        cursor = Transaction().connection.cursor()
        # Migration from 2.2: Move default commission reporting templates from
        # insurer_reporting module
        cursor.execute(*model_data.select(
                model_data.fs_id, model_data.id,
                where=(model_data.module == 'insurer_reporting')
                & model_data.fs_id.in_([
                        'default_commission_reporting_template',
                        'default_commission_reporting_fr_version',
                        'default_commission_reporting_en_version',
                        'default_insurer_reporting_template',
                        'default_insurer_reporting_fr_version',
                        'default_insurer_reporting_en_version'
                        ])))
        existing = {}
        for target_fs_id, target_id in cursor.fetchall():
            existing[target_fs_id] = target_id
        if existing:
            assert len(existing) == 6
            cursor.execute(*model_data.update(
                [model_data.module],
                ['commission_insurer'],
                where=(
                    model_data.id.in_(list(existing.values()))
                    )))
        # Migration from 1.14: Change invoice kinds
        super(ReportTemplate, cls).__register__(module_name)
        table = cls.__table__()
        cursor.execute(*table.update(
                columns=[table.kind],
                values=['broker_invoice'],
                where=table.kind == 'broker_report',
                ))
        cursor.execute(*table.update(
                columns=[table.kind],
                values=['insurer_invoice'],
                where=table.kind == 'insurer_report_commission',
                ))

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'account.invoice':
            result.append(('all_insurer_invoices', gettext(
                        'commission_insurer.msg_all_insurer_invoices')))
            result.append(('broker_invoice', gettext(
                        'commission_insurer.msg_broker_invoice')))
            result.append(('insurer_invoice', gettext(
                        'commission_insurer.msg_insurer_invoice')))
        return result
