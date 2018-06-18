# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext

from trytond.modules.coog_core import utils


__all__ = [
    'CreateIndemnification',
    ]


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    def possible_services(self, claim):
        return [x
            for x in super(CreateIndemnification, self).possible_services(claim)
            if x.is_main_service]

    def transition_select_service_needed(self):
        res = super(CreateIndemnification,
            self).transition_select_service_needed()
        if (res != 'select_service' and
                not self.definition.service.is_main_service):
            self.definition.service = self.definition.service.parent_service
        return res

    def default_definition(self, name):
        values = super(CreateIndemnification, self).default_definition(name)
        if (not values or 'extra_data' not in values or
                'service' not in values or 'start_date' not in values):
            return values
        main_service = Pool().get('claim.service')(values['service'])
        new_extra_data = {}
        for sub_service in main_service.sub_services:
            extra_data = utils.get_value_at_date(sub_service.extra_datas,
                values['start_date']).extra_data_values
            with ServerContext().set_context(service=sub_service):
                new_data = sub_service.benefit.refresh_extra_data(extra_data)
            for k, v in new_data.items():
                if k not in extra_data:
                    extra_data[k] = v
            new_extra_data.update(extra_data)
        # Put the extra data for the main service at the end to make them the
        # default values in case of conflict
        new_extra_data.update(values['extra_data'])
        values['extra_data'] = new_extra_data
        return values

    def clear_indemnifications(self):
        super(CreateIndemnification, self).clear_indemnifications()
        sub_services = self.definition.service.sub_services
        if sub_services:
            if self.definition.is_period:
                input_start_date = self.definition.start_date
            else:
                input_start_date = self.definition.indemnification_date
            Pool().get('claim.service').cancel_indemnification(
                sub_services, input_start_date, self.definition.end_date)

    def update_service_extra_data(self, values):
        main_service = self.definition.service
        date = self.definition.start_date or main_service.loss.start_date
        super(CreateIndemnification, self).update_service_extra_data(values)
        sub_services = main_service.sub_services
        if not sub_services:
            return
        for service in sub_services:
            service.update_extra_data(date, values)
        Pool().get('claim.service').save(sub_services)

    def init_indemnifications(self):
        Indemnification = Pool().get('claim.indemnification')
        previous = super(CreateIndemnification, self).init_indemnifications()
        indemnifications = []
        for master in previous:
            if not master.service.is_main_service:
                continue
            indemnifications.append(master)
            for sub_service in master.service.sub_services:
                sub_indemnification = Indemnification(service=sub_service)
                self.update_indemnification(sub_indemnification)
                indemnifications.append(sub_indemnification)
        return indemnifications
