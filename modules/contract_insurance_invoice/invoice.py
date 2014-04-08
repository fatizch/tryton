from trytond.model import fields
from trytond.pool import Pool, PoolMeta

__all__ = ['InvoiceLine']
__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = 'account.invoice.line'
    # XXX maybe change for the description
    contract_insurance_start = fields.Date('Start Date')
    contract_insurance_end = fields.Date('End Date')

    @property
    def origin_name(self):
        pool = Pool()
        Premium = pool.get('contract.premium')
        name = super(InvoiceLine, self).origin_name
        if isinstance(self.origin, Premium):
            name = self.origin.get_parent().rec_name
        return name

    @classmethod
    def _get_origin(cls):
        return super(InvoiceLine, cls)._get_origin() + [
            'contract.premium']
