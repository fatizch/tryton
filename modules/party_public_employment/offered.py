# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'ItemDescription',
    ]


class ItemDescription(metaclass=PoolMeta):
    __name__ = 'offered.item.description'

    def _has_valid_employment_data(self, covered_element):
        res = super()._has_valid_employment_data(covered_element)
        return res or bool(
            covered_element.party.get_employment_version_data(
                'gross_index', covered_element.contract.start_date)
            ) or bool(
            covered_element.party.get_employment_version_data(
                'increased_index', covered_element.contract.start_date)
            )
