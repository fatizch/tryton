# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if self.on_model == 'user.connection':
            result.append(('connections', 'Users connections'))
        return result
