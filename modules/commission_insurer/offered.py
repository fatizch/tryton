# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    def get_domain_agents(self):
        super_domain = super(OptionDescription, self).get_domain_agents()
        domain_agent = super_domain[:]
        domain_agent.append(('type_', '!=', 'principal'))
        domain_principal = super_domain[:]
        domain_principal.append(('type_', '=', 'principal'))
        domain_principal.append(('party', '=', self.insurer.party))
        return ['OR', domain_agent, domain_principal]
