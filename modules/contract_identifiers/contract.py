# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from itertools import groupby

from trytond import backend
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import sequence_ordered, Unique
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.tools import grouped_slice

from trytond.modules.coog_core import fields, model, coog_string

__all__ = [
    'Contract',
    'ContractIdentifier',
    'ContractIdentifierType',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    identifiers = fields.One2Many('contract.identifier', 'contract',
        'Identifiers', states={'readonly': Eval('status') != 'quote'},
        depends=['status'], delete_missing=True,
        help="Add other identifiers of the contract.")
    external_number = fields.Function(
        fields.Char('External Number',
            states={'readonly': Eval('status') != 'quote'},
            depends=['status']),
        'getter_external_number', 'setter_external_number',
        searcher='search_external_number')
    identifiers_as_string = fields.Function(
        fields.Char('Identifiers'),
        'getter_identifiers_as_string',
        searcher='searcher_identifiers_as_string')

    @classmethod
    def copy(cls, contracts, default=None):
        default = default.copy() if default else {}
        default.setdefault('identifiers', [])
        return super(Contract, cls).copy(contracts, default=default)

    @classmethod
    def getter_external_number(cls, contracts, name):
        cursor = Transaction().connection.cursor()
        res = {contract.id: '' for contract in contracts}
        identifier = Pool().get('contract.identifier').__table__()
        cursor.execute(*identifier.select(identifier.contract, identifier.code,
                where=(identifier.contract.in_([x.id for x in contracts])) &
                (identifier.identifier_type == "external_number"),
                order_by=identifier.contract
                ))
        for contract_id, code in cursor.fetchall():
            res[contract_id] = code
        return res

    @classmethod
    def search_external_number(cls, name, clause):
        _, operator, value = clause
        domain = [
            ('identifiers', 'where', [
                    ('code', operator, value),
                    ('type', '=', 'external_number'),
                    ]),
            ]
        # Add contract without external number
        if ((operator == '=' and value is None)
                or (operator == 'in' and None in value)):
            domain = ['OR',
                domain, [
                    ('identifiers', 'not where', [
                            ('type', '=', 'external_number'),
                            ]),
                    ],
                ]
        return domain

    @classmethod
    def getter_identifiers_as_string(cls, contracts, name):
        cursor = Transaction().connection.cursor()
        res = {contract.id: '' for contract in contracts}
        identifier = Pool().get('contract.identifier').__table__()
        cursor.execute(*identifier.select(identifier.contract, identifier.code,
                where=identifier.contract.in_([x.id for x in contracts]),
                order_by=identifier.contract
                ))
        for contract_id, ids in groupby(cursor.fetchall(), key=lambda x: x[0]):
            res[contract_id] = ', '.join([ident[1] for ident in ids])
        return res

    @classmethod
    def searcher_identifiers_as_string(cls, name, clause):
        _, operator, value = clause
        domain = [
            ('identifiers', 'where', [
                    ('code', operator, value)
                    ]),
            ]
        return domain

    @classmethod
    def search_rec_name(cls, name, clause):
        domain = [('identifiers.code',) + tuple(clause[1:])]
        return super(Contract, cls).search_rec_name(name, clause) + domain

    @classmethod
    def setter_external_number(cls, contracts, name, value):
        pool = Pool()
        ContractIdentifier = pool.get('contract.identifier')

        with model.error_manager():
            for contract_slice in grouped_slice(contracts):
                to_save = []
                for contract in contract_slice:
                    to_save.append(contract)
                    external_number_identifier = None
                    for identifier in contract.identifiers:
                        if identifier.identifier_type == 'external_number':
                            external_number_identifier = identifier
                            external_number_identifier.code = value
                            break
                    contract.identifiers = contract.identifiers or ()
                    if not external_number_identifier:
                        contract.identifiers += (ContractIdentifier(code=value,
                                identifier_type='external_number'),)
        cls.save(to_save)

    def get_identifier_value(self, identifier_type, default=None):
        # This method is used by templates to get more easily
        # identifiers values from its type
        for identifier in self.identifiers:
            if identifier.identifier_type == identifier_type:
                return identifier.code
        return '' if default is None else default


class ContractIdentifier(sequence_ordered(), model.CoogSQL, model.CoogView,
        metaclass=PoolMeta):
    'Contract Identifier'
    __name__ = 'contract.identifier'
    _rec_name = 'code'
    _func_key = 'code'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        required=True, select=True,
        help="The contract identified by this record.")
    identifier_type = fields.Selection('get_identifier_types', 'Type',
        states={'readonly': Eval('contract_status') != 'quote'},
        required=True, depends=['contract_status'])
    identifier_type_string = identifier_type.translated('type')
    code = fields.Char('Code',
        states={'readonly': Eval('contract_status') != 'quote'}, required=True,
        depends=['contract_status'])
    contract_status = fields.Function(
        fields.Char('Contract Status'),
        'on_change_with_contract_status')

    _identifier_type_cache = Cache('contract.identifier.get_identifier_types',
        context=False)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Contract = pool.get('contract')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        contract = Contract.__table__()

        super(ContractIdentifier, cls).__register__(module_name)

        # migration from 2.0
        contract_h = TableHandler(Contract, module_name)
        if (contract_h.column_exist('external_number')):
            cursor.execute(*contract.select(
                    contract.id, contract.external_number,
                    where=(contract.external_number != Null)))
            for sliced_fetch in grouped_slice(cursor.fetchall()):
                identifiers = []
                for contract_id, number in sliced_fetch:
                    if not number:
                        continue
                    identifiers.append(cls(contract=contract_id,
                        code=number, identifier_type='external_number'))
                cls.save(identifiers)
            contract_h.drop_column('external_number')

        # Adding index on (code, type)
        table = TableHandler(cls, module_name)
        table.index_action(['code', 'identifier_type'], 'add')

    @classmethod
    def _get_base_identifier_types(cls):
        return [('external_number',
                gettext('contract_identifiers.msg_external_number_label'))]

    @classmethod
    def get_identifier_types(cls):
        ContractIdentifierType = Pool().get('contract.identifier.type')
        lang = Transaction().language
        res = cls._identifier_type_cache.get(lang)
        if res is not None:
            return list(res)
        res = cls._get_base_identifier_types()
        for identifier_type in ContractIdentifierType.search([]):
            res.append((identifier_type.code,
                    coog_string.translate_value(identifier_type, 'name')))
        cls._identifier_type_cache.set(lang, res)
        return list(res)

    @fields.depends('contract')
    def on_change_with_contract_status(self, name=None):
        return self.contract.status if self.contract else ''


class ContractIdentifierType(model.CoogSQL, model.CoogView, metaclass=PoolMeta):
    'Contract Identifier Type'

    __name__ = 'contract.identifier.type'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)

    @classmethod
    def __setup__(cls):
        super(ContractIdentifierType, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('contract_identifier_type_code_unique', Unique(t, t.code),
                'contract_identifiers.msg_code_unique'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        return (coog_string.slugify(self.name)
            if self.name and not self.code else self.code)

    @classmethod
    def delete(cls, instances):
        pool = Pool()
        ContractIdentifier = pool.get('contract.identifier')
        if ContractIdentifier.search(
                [('identifier_type', 'in', [x.code for x in instances])]):
            raise AccessError(gettext(
                    'contract_identifiers.msg_type_is_used'))
        Pool().get('contract.identifier')._identifier_type_cache.clear()
        super(ContractIdentifierType, cls).delete(instances)

    @classmethod
    def create(cls, vlist):
        Pool().get('contract.identifier')._identifier_type_cache.clear()
        return super(ContractIdentifierType, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        Pool().get('contract.identifier')._identifier_type_cache.clear()
        super(ContractIdentifierType, cls).write(*args)
