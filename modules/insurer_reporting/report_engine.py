from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate:
    __name__ = 'report.template'

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'contract':
            result.append(('insurer_report_contract',
                    'Insurer Report Contract'))
            result.append(('insurer_report_covered', 'Insurer Report Covered'))
        elif self.on_model.model == 'account.invoice':
            result.append(('insurer_report_commission',
                    'Insurer Report Commission'))
            result.append(('broker_report', 'Broker Report'))
        return result
