# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'InsurerSlipConfiguration',
    ]


class InsurerSlipConfiguration(metaclass=PoolMeta):
    __name__ = 'account.invoice.slip.configuration'

    @classmethod
    def _get_new_slip(cls, parameters):
        invoice = super(InsurerSlipConfiguration, cls)._get_new_slip(parameters)
        if parameters.get('insurer', None):
            invoice.product = parameters['insurer'].product
        else:
            # No idea of what to do in this case, since the configuration has
            # no reason to be linked to a particular insurer
            raise ValueError
        return invoice

    @classmethod
    def _get_slip_domain_from_parameters(cls, parameters):
        domain_ = super(InsurerSlipConfiguration,
                cls)._get_slip_domain_from_parameters(parameters)
        if parameters.get('insurer', None):
            product = parameters['insurer'].product
            domain_.append(('product', '=', product))
        return domain_
