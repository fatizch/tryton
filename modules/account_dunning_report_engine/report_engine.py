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
        if self.on_model.model == 'account.dunning':
            result.append(('dunning_letter', 'Dunning Letter'))
        return result
