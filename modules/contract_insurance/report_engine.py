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
            result.append(('contract', 'Quote and Contract Documents'))
            result.append(('active_contract', 'Active Contract Documents'))
            result.append(('quote_contract', 'Quote Documents'))

        return result

    def get_style_content(self, at_date, _object):
        res = super(ReportTemplate, self).get_style_content(at_date, _object)
        if res:
            return res
        contract = getattr(_object, 'contract', None)
        if contract:
            return contract.get_report_style_content(at_date, self)
        contracts = getattr(_object, 'contracts', None)
        if contracts:
            return contracts[0].get_report_style_content(at_date, self)
