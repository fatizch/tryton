from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    def get_template_holders_sub_domains(self):
        result = super(Contract, self).get_template_holders_sub_domains()
        if not self.com_product:
            return result
        result.append([('com_products', '=', self.com_product.id)])
        return result

    def get_report_style_content(self, at_date, template):
        content = None
        if self.com_product:
            content = self.com_product.get_report_style_content(at_date,
                template, self)
        return content or super(Contract, self).get_report_style_content(
            at_date, template)
