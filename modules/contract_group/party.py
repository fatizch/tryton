# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.model import fields as tryton_fields
from trytond.modules.coog_core import fields
from trytond.pyson import Eval


__all__ = [
    'Party',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    companies = fields.Function(
        fields.Many2Many('party.party', None, None, 'Companies',
            states={'invisible': ~Eval('is_person')},
            domain=[('is_person', '=', False)]),
        'get_companies', searcher='search_companies')

    def get_companies(self, name):
        res = [covered.main_contract.subscriber.id
            for covered in self.covered_elements
            if not covered.main_contract.subscriber.is_person]
        return res

    @classmethod
    def search_companies(cls, name, clause):
        pool = Pool()
        _, operator, value = clause
        contract = pool.get('contract').__table__()
        covered_element = pool.get('contract.covered_element').__table__()
        covered_element2 = pool.get('contract.covered_element').__table__()
        Operator = tryton_fields.SQL_OPERATORS[operator]
        assert operator in ('in', 'not in')
        where_clause = Operator(contract.subscriber,
            getattr(cls, name).sql_format(value))
        query = contract.join(covered_element, condition=(
                contract.id == covered_element.contract)
            ).join(covered_element2, condition=(
                covered_element2.parent == covered_element.id))
        return [('id', 'in', query.select(
                    covered_element2.party, where=(where_clause)))]
