# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    def get_domain_agents(self):
        domain = super(OptionDescription, self).get_domain_agents()
        domain.append(('second_level_commission', '=', False))
        return domain
