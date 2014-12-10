# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os

import genshi
import genshi.template

from trytond.pool import PoolMeta
from trytond.modules.account_payment_sepa import payment as sepa_payment


__metaclass__ = PoolMeta
__all__ = ['Journal', 'Group']


class Journal:
    __name__ = 'account.payment.journal'

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        receivable_flavor_cfonb = ('pain.008.001.02-cfonb',
            'pain.008.001.02 CFONB')
        if receivable_flavor_cfonb not in cls.sepa_receivable_flavor.selection:
            cls.sepa_receivable_flavor.selection.append(
                receivable_flavor_cfonb)

loader = genshi.template.TemplateLoader([
        os.path.join(os.path.dirname(__file__), 'template'),
        os.path.join(
            os.path.dirname(
                sepa_payment.__file__), 'template'),
        ], auto_reload=True)


class Group:
    __name__ = 'account.payment.group'

    def get_sepa_template(self):
        if (self.kind == 'receivable'
                and self.journal.sepa_receivable_flavor.endswith('-cfonb')):
            return loader.load('%s.xml' % self.journal.sepa_receivable_flavor)
        return super(Journal, self).get_sepa_template()
