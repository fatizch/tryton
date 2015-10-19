from trytond.modules.cog_utils import export


__all__ = [
    'Tax',
    'TaxTemplate',
    'TaxCodeTemplate',
    'TaxCode',
    'TaxGroup',
    ]


class Tax(export.ExportImportMixin):
    __name__ = 'account.tax'

    @classmethod
    def is_master_object(cls):
        return True


class TaxTemplate(export.ExportImportMixin):
    __name__ = 'account.tax.template'


class TaxCodeTemplate(export.ExportImportMixin):
    __name__ = 'account.tax.code.template'


class TaxCode(export.ExportImportMixin):
    __name__ = 'account.tax.code'


class TaxGroup(export.ExportImportMixin):
    __name__ = 'account.tax.group'
