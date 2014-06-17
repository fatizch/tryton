from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import export


__metaclass__ = PoolMeta
__all__ = [
    'Move',
    'Account',
    'AccountTemplate',
    'AccountKind',
    'AccountTypeTemplate',
    'Journal',
    'FiscalYear',
    'Period',
    'Configuration',
    ]


class Move(export.ExportImportMixin):
    __name__ = 'account.move'


class AccountKind(export.ExportImportMixin):
    __name__ = 'account.account.type'

    @classmethod
    def _export_keys(cls):
        return set(['name', 'company.party.name'])


class AccountTypeTemplate(export.ExportImportMixin):
    __name__ = 'account.account.type.template'


class Account(export.ExportImportMixin):
    __name__ = 'account.account'

    @classmethod
    def _export_keys(cls):
        return set(['code', 'name', 'company.party.name'])

    @classmethod
    def _export_skips(cls):
        res = super(Account, cls)._export_skips()
        res.add('left')
        res.add('right')
        res.add('taxes')
        return res


class AccountTemplate(export.ExportImportMixin):
    __name__ = 'account.account.template'


class Journal(export.ExportImportMixin):
    __name__ = 'account.journal'

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.credit_account.domain = export.clean_domain_for_import(
            cls.credit_account.domain, 'company')
        cls.debit_account.domain = export.clean_domain_for_import(
            cls.debit_account.domain, 'company')

    @classmethod
    def _export_skips(cls):
        result = super(Journal, cls)._export_skips()
        result.add('view')
        return result


class FiscalYear(export.ExportImportMixin):
    'Fiscal Year'

    __name__ = 'account.fiscalyear'

    @classmethod
    def __setup__(cls):
        super(FiscalYear, cls).__setup__()
        cls.company.domain = export.clean_domain_for_import(
            cls.company.domain, 'company')

    @classmethod
    def _export_skips(cls):
        result = super(FiscalYear, cls)._export_skips()
        result.add('close_lines')
        return result

    @classmethod
    def _export_force_recreate(cls):
        res = super(FiscalYear, cls)._export_force_recreate()
        res.remove('periods')
        return res

    @classmethod
    def _export_keys(cls):
        return set(['company.party.name', 'code'])


class Period(export.ExportImportMixin):
    __name__ = 'account.period'

    @classmethod
    def write(cls, periods, vals):
        # Overwritten to check for moves only if start_date / end_date /
        # fiscalyear actually changes
        found = [x for x in ('start_date', 'end_date', 'fiscalyear')
                if x in vals]
        if not found:
            return super(Period, cls).write(periods, vals)
        for period in periods:
            if ('start_date' in found and period.start_date !=
                    vals['start_date']) or ('end_date' in found and
                    period.end_date != vals['end_date']) or (
                    'fiscalyear' in found and period.fiscalyear.id !=
                        vals['fiscalyear']):
                if period.moves:
                    cls.raise_user_error('modify_del_period_moves', (
                        period.rec_name))
        for x in found:
            del vals[x]
        return super(Period, cls).write(periods, vals)

    @classmethod
    def _export_keys(cls):
        return set(['code', 'fiscalyear.code',
                'fiscalyear.company.party.name'])

    def check_dates(self):
        if not '__importing__' in Transaction().context:
            return super(Period, self).check_dates()
        return True


class Configuration(export.ExportImportMixin):
    __name__ = 'account.configuration'

    @classmethod
    def _export_keys(cls):
        # Account Configuration is a singleton, so the id is an acceptable
        # key
        return set(['id'])

    @classmethod
    def _export_must_export_field(cls, field_name, field):
        # Function field are not exported by default
        if field_name in ('default_account_receivable',
                'default_account_payable'):
            return True
        return super(Configuration, cls)._export_must_export_field(
            field_name, field)

    def _export_default_account(self, name, exported, result, my_key):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')
        company_id = Transaction().context.get('company')
        account_field, = ModelField.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', name[8:]),
            ], limit=1)
        properties = Property.search([
            ('field', '=', account_field.id),
            ('res', '=', None),
            ('company', '=', company_id),
            ], limit=1)
        if properties:
            prop, = properties
            prop._export_json(exported, result)
        return None

    def _export_override_default_account_receivable(self, exported, result,
            my_key):
        return self._export_default_account('default_account_receivable',
            exported, result, my_key)

    def _export_override_default_account_payable(self, exported, result,
            my_key):
        return self._export_default_account('default_account_payable',
            exported, result, my_key)

    @classmethod
    def _import_default_account(cls, name, instance_key, good_instance,
            field_value, values, created, relink):
        if not field_value:
            return
        _account_field, _company, _value = field_value
