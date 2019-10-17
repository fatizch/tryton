# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.modules.coog_core import export


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
    def __setup__(cls):
        super(Tax, cls).__setup__()
        cls.invoice_account.domain = ['OR',
            cls.invoice_account.domain,
            [('company', '=', Eval('company')),
                ('type.statement', '=', 'off-balance'),
                ('closed', '!=', True)]]
        cls.credit_note_account.domain = ['OR',
            cls.credit_note_account.domain,
            [('company', '=', Eval('company')),
                ('type.statement', '=', 'off-balance'),
                ('closed', '!=', True)]]

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return super(Tax, cls)._export_light() | {'company', 'group', 'parent',
            'invoice_account', 'credit_note_account', 'template'}

    @classmethod
    def _export_skips(cls):
        return super(Tax, cls)._export_skips() | {'childs'}


class TaxTemplate(export.ExportImportMixin):
    __name__ = 'account.tax.template'


class TaxCodeTemplate(export.ExportImportMixin):
    __name__ = 'account.tax.code.template'


class TaxCode(export.ExportImportMixin):
    __name__ = 'account.tax.code'


class TaxGroup(export.ExportImportMixin):
    __name__ = 'account.tax.group'
