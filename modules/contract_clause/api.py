# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA

__all__ = [
    'APIContract',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        pool = Pool()
        ContractClause = pool.get('contract.clause')

        clauses = []
        for clause_data in contract_data.get('clauses', []):
            clause = ContractClause()
            clause.clause = clause_data['clause']
            if not clause.clause.customizable:
                clause.text = clause.clause.content
            else:
                clause.text = clause_data.get('customized_text',
                    clause.clause.content)
            clauses.append(clause)

        contract.clauses = clauses

        return contract

    @classmethod
    def _contract_convert(cls, data, options, parameters, minimum=False):
        super()._contract_convert(data, options, parameters, minimum=minimum)

        API = Pool().get('api')

        product_clauses = {x.id for x in data['product'].clauses}
        for clause_data in data.get('clauses', []):
            clause = API.instantiate_code_object('clause',
                clause_data['clause'])
            if 'customized_text' in clause_data and not clause.customizable:
                API.add_input_error({
                        'type': 'non_customizable_clause',
                        'data': {
                            'clause': clause.code,
                            },
                        })
            if clause.id not in product_clauses:
                API.add_input_error({
                        'type': 'unauthorized_product_clause',
                        'data': {
                            'product': data['product'].code,
                            'clause': clause.code,
                            },
                        })
            clause_data['clause'] = clause

    @classmethod
    def _contract_schema(cls, minimum=False):
        schema = super()._contract_schema(minimum=minimum)
        schema['properties']['clauses'] = {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'clause': CODED_OBJECT_SCHEMA,
                    'customized_text': {'type': 'string'},
                    },
                'required': ['clause'],
                },
            }
        return schema
