# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


class ExtraData(metaclass=PoolMeta):
    __name__ = 'extra_data'

    used_by_api = fields.Selection([
            ('', ''),
            ('simulation', 'Simulation'),
            ('quote_creation', 'Quote creation'),
            ('activation', 'Activation'),
            ], 'Used by API',
            states={'invisible': ~Eval('kind').in_([
                    'contract', 'product', 'party_person', 'party_company',
                    'package', 'option', 'covered_element'])})

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        do_migrate = False
        table_handler = TableHandler(cls)
        if not table_handler.column_exist('used_by_api'):
            do_migrate = True
        super(ExtraData, cls).__register__(module_name)
        if not do_migrate:
            return
        table = cls.__table__()
        cursor.execute(*table.update(columns=[table.used_by_api],
            values=['simulation'], where=(
                table.kind.in_(['contract', 'product', 'party_person',
                'party_company', 'package', 'option', 'covered_element']))))

    @classmethod
    def filter_extra_for_validation_level(cls, extra):
        validation_level = ServerContext().get('contract_validation_level',
            None)
        if validation_level is None:
            return extra
        # If an API validation level is given,
        # We do not need to check for the presence
        # of extra_data whose level ( field: used_by_api)
        # is higher than the given validation level
        levels = [x[0] for x in cls.used_by_api.selection]
        level_idx = levels.index(validation_level)
        idx_by_keys = {x.name: levels.index(x.used_by_api or '')
            for x in cls.search([('name', 'in', sorted(list(extra)))])}
        filtered = {}
        for k in extra:
            if idx_by_keys[k] > level_idx:
                continue
            filtered[k] = extra[k]
        return filtered

    @classmethod
    def check_for_consistency(cls, recomputed, extra):
        if recomputed != extra:
            filtered_recomputed = cls.filter_extra_for_validation_level(
                recomputed)
            filtered_extra = cls.filter_extra_for_validation_level(extra)
            return filtered_recomputed == filtered_extra
        return True
