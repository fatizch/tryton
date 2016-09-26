# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'CoveredElement',
    'Contract',
    ]


class CoveredElement:
    __name__ = 'contract.covered_element'

    @classmethod
    def __register__(cls, module_name):
        super(CoveredElement, cls).__register__(module_name)
        # Migration from 1.8: Drop law_madelin column
        TableHandler = backend.get('TableHandler')
        covered_element = TableHandler(cls)
        if covered_element.column_exist('is_law_madelin'):
            covered_element.drop_column('is_law_madelin')


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({
                'ssn_required': ('SSN is required for covered element %s'),
                })

    @classmethod
    def validate(cls, contracts):
        super(Contract, cls).validate(contracts)
        cls.check_ssn_on_covered_elements(contracts)

    @classmethod
    def check_ssn_on_covered_elements(cls, contracts):
        for contract in contracts:
            for covered in contract.covered_elements:
                if covered.party.get_SSN_required() and not \
                        covered.party.ssn:
                    cls.raise_user_error('ssn_required', covered.rec_name)
