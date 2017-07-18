# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

__all__ = [
    'Service',
    'Indemnification',
    ]


class Service:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    def calculate(self):
        if not self.is_main_service:
            return
        return super(Service, self).calculate()

    def create_missing_indemnifications(self, until):
        if not self.is_main_service:
            return []
        return super(Service, self).create_missing_indemnifications(until)

    def new_indemnifications(self, start, end):
        indemnifications = super(Service, self).new_indemnifications(start, end)
        with ServerContext().set_context(master_indemnification=self):
            return sum([x.new_indemnifications(start, end)
                    for x in self.sub_services], indemnifications)


class Indemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    @classmethod
    def indemn_order_key(cls, indemnification):
        return (indemnification.start_date or datetime.date.min,
            indemnification.end_date or datetime.date.max)

    @classmethod
    def do_calculate(cls, indemnifications):
        if ServerContext().get('master_indemnification', None):
            return super(Indemnification, cls).do_calculate(indemnifications)

        # Assume all master / slaves are here
        per_service = defaultdict(list)
        for indemnification in indemnifications:
            per_service[indemnification.service].append(indemnification)

        master_slave = {}
        for service, values in per_service.items():
            if not service.is_main_service:
                continue
            subs = []
            for sub_service in service.sub_services:
                subs += per_service[sub_service]
            if not subs:
                master_slave.update({x: [] for x in values})
                continue

            # Group by dates to match master and slaves
            values.sort(key=cls.indemn_order_key)
            subs.sort(key=cls.indemn_order_key)

            counter = 0
            for value in values:
                cur_subs = []
                val_start = value.start_date or datetime.date.min
                val_end = value.end_date or datetime.date.max
                if (subs[counter].start_date or datetime.date.min) < val_start:
                    cls.raise_user_error('bad_subs')
                while counter < len(subs) and (
                        (subs[counter].start_date or datetime.date.min)
                        >= val_start) and (
                        (subs[counter].end_date or datetime.date.max)
                        <= val_end):
                    cur_subs.append(subs[counter])
                    counter += 1
                if counter < len(subs) and (
                        (subs[counter].start_date or datetime.date.min)
                        <= val_end) and (
                        (subs[counter].end_date or datetime.date.max)
                        <= val_end):
                    cls.raise_user_error('bad_subs')
                master_slave[value] = cur_subs
            if counter != len(values):
                cls.raise_user_error('bad_subs')

        result = []
        for master, slaves in master_slave.iteritems():
            super(Indemnification, cls).do_calculate([master])
            with ServerContext().set_context(master_indemnification=master):
                cls.do_calculate(slaves)
            result += [master] + slaves
        return result
