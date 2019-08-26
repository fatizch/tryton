# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond import backend
from trytond.i18n import gettext
from trytond.model.exceptions import AccessError
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.rule_engine import check_args

HARDCODED_TABLES = ['pmss', 'COOG_AGIRC', 'COOG_ARRCO']

__all__ = [
    'Table',
    'DimensionValue',
    'Cell',
    'RuleEngineRuntime',
    'RuleEngine',
    ]


class Table(metaclass=PoolMeta):
    __name__ = 'table'

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        handler = TableHandler(cls, module)

        # Since we provide some reference tables, we need to make sure they are
        # up to date and accurate.
        # To do so, we wipe them in order to avoid conflict with values that
        # could have been created manually by the clients

        clean_up_default_tables = handler.table_exist('table')

        super().__register__(module)

        if clean_up_default_tables:
            pool = Pool()
            dimensions = pool.get('table.dimension.value').__table__()
            cells = pool.get('table.cell').__table__()
            data = pool.get('ir.model.data').__table__()
            cursor = Transaction().connection.cursor()

            # Find the tables / dimensions / cells
            cursor.execute(*data.select(data.db_id,
                    where=(data.module == 'claim_salary_fr')
                    & data.fs_id.in_(HARDCODED_TABLES)))
            table_ids = [x[0] for x in cursor.fetchall()]

            if not table_ids:
                return

            cursor.execute(*dimensions.select(dimensions.id,
                    where=dimensions.definition.in_(table_ids)))
            dimensions_ids = [x[0] for x in cursor.fetchall()]

            cursor.execute(*cells.select(cells.id,
                    where=cells.definition.in_(table_ids)))
            cells_ids = [x[0] for x in cursor.fetchall()]

            # Clean up cells
            if cells_ids:
                cursor.execute(*data.delete(
                        where=(data.module == 'claim_salary_fr')
                        & (data.model == 'table.cell')
                        & data.db_id.in_(cells_ids)))
                cursor.execute(*cells.delete(
                        where=cells.id.in_(cells_ids)))

            # Clean up dimensions
            if dimensions_ids:
                cursor.execute(*data.delete(
                        where=(data.module == 'claim_salary_fr')
                        & (data.model == 'table.dimension.value')
                        & data.db_id.in_(dimensions_ids)))
                cursor.execute(*dimensions.delete(
                        where=dimensions.id.in_(dimensions_ids)))


class DimensionValue(metaclass=PoolMeta):
    __name__ = 'table.dimension.value'

    @classmethod
    def create(cls, vlist):
        Table = Pool().get('table')

        if Transaction().user != 0:
            hardcoded_tables = [
                Table.get_table_by_code(code) for code in HARDCODED_TABLES]
            hardcoded_tables_ids = [x.id for x in hardcoded_tables if x]
            if any(x.get('definition', 0) in hardcoded_tables_ids
                    for x in vlist):
                raise AccessError(gettext(
                        'claim_salary_fr.msg_modify_configuration_table'))
        return super().create(vlist)


class Cell(metaclass=PoolMeta):
    __name__ = 'table.cell'

    @classmethod
    def create(cls, vlist):
        Table = Pool().get('table')

        if Transaction().user != 0:
            hardcoded_tables = [
                Table.get_table_by_code(code) for code in HARDCODED_TABLES]
            hardcoded_tables_ids = [x.id for x in hardcoded_tables if x]
            if any(x.get('definition', 0) in hardcoded_tables_ids
                    for x in vlist):
                raise AccessError(gettext(
                        'claim_salary_fr.msg_modify_configuration_table'))
        return super().create(vlist)


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('benefit_net_salary_calculation',
                'Benefit: Net Salary Calculation'))


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('curr_salary')
    def _re_get_range_by_name(cls, args, range_name=None, fixed=False,
            codes_list=None):
        return args['curr_salary'].get_range(range_name, fixed, codes_list)

    @classmethod
    @check_args('service')
    def _re_get_gross_salary(cls, args):
        if 'curr_salary' in args:
            return args['curr_salary'].gross_salary
        else:
            return args['service'].gross_salary

    @classmethod
    @check_args('service')
    def _re_get_net_salary(cls, args):
        service = args['service']
        if 'curr_salary' in args:
            return args['curr_salary'].net_salary
        else:
            if service.net_salary:
                return service.net_salary
            else:
                for s in reversed([x for x in service.claim.delivered_services
                            if x != service]):
                    if s.net_salary:
                        return s.net_salary
        return Decimal(0)

    @classmethod
    @check_args('service')
    def _re_basic_salary(cls, args, salaries_def, with_revaluation=True):
        current_salary = args.get('curr_salary', None)
        return args['service'].calculate_basic_salary(salaries_def,
            current_salary=current_salary,
            args=args if with_revaluation else None)

    @classmethod
    @check_args('service')
    def _re_is_net_limite(cls, args):
        return args['service'].benefit.benefit_rules[0]. \
            option_benefit_at_date(args['service'].option,
                args['service'].loss.start_date).net_salary_mode

    @classmethod
    @check_args('service')
    def _re_revaluation_on_basic_salary(cls, args):
        return args['service'].benefit.benefit_rules[
            0].process_revaluation_on_basic_salary(args['service'])
