import os

import genshi
import genshi.template

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, export

__metaclass__ = PoolMeta
__all__ = ['Journal', 'Mandate']


loader = genshi.template.TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'template'),
    auto_reload=True)


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class Journal(export.ExportImportMixin):
    __name__ = 'account.payment.journal'
    umr_sequence = fields.Many2One('ir.sequence', 'Sepa Umr Sequence',
        states={'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa'},
        domain=[
            ('code', '=', 'account.payment.sepa.umr'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ],
            ],
        context={
            'code': 'account.payment.sepa.umr',
            'company': Eval('company'),
            }, depends=['company'])


class Mandate:
    __name__ = 'account.payment.sepa.mandate'

    def get_rec_name(self, name):
        if self.identification is None or self.party is None:
            return super(Mandate, self).get_rec_name(name)
        return '%s - %s' % (self.identification, self.party.get_rec_name(None))
