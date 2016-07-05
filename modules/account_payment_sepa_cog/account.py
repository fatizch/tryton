# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'account.configuration'

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        values = super(Configuration, self).export_json(skip_fields,
            already_exported, output, main_object, configuration)

        if 'sepa_mandate_sequence' not in values:
            return values
        field_value = getattr(self, 'sepa_mandate_sequence')
        values['sepa_mandate_sequence'] = {'_func_key': getattr(
            field_value, field_value._func_key)}
        return values
