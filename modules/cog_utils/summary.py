# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import coop_string
import logging

LOG = logging.getLogger(__name__)


class SummaryMixin(object):
    'Mixin to support summary in a rich text format'

    def get_summary_content(self, label, at_date=None, lang=None):
        if label is True:
            label = self.rec_name
            value = ()
        else:
            value = self.rec_name
        return (label, value)

    def get_summary(self, name):
        ret = coop_string.generate_summary(self.get_summary_content(True))
        return ret
