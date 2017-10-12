# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = [
    'DocumentRequestLine',
    ]


class DocumentRequestLine:
    __metaclass__ = PoolMeta
    __name__ = 'document.request.line'

    @classmethod
    def update_values_from_target(cls, data_dict):
        underwritings = []
        for target, values in data_dict.iteritems():
            if target.startswith('underwriting,'):
                underwritings.append(int(target.split(',')[1]))
        if underwritings:
            for underwriting in Pool().get('underwriting').browse(
                    underwritings):
                data_dict[str(underwriting.on_object)] = data_dict[
                    str(underwriting)]
                del data_dict[str(underwriting)]
            # Force a new analysis
            cls.update_values_from_target(data_dict)
        else:
            super(DocumentRequestLine, cls).update_values_from_target(
                data_dict)

    @classmethod
    def for_object_models(cls):
        return super(DocumentRequestLine, cls).for_object_models() + \
            ['underwriting']
