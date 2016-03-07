import csv

from trytond.pool import Pool


class AgenciesLoader:

    @classmethod
    def load_agencies(cls):
        # TODO : improve this method to deal with cache issues
        pool = Pool()
        Agency = pool.get('bank.agency')
        result = {x.bank.bic + x.branch_code + x.bank_code: x
            for x in Agency.search([])}
        return result

    @classmethod
    def load_banks(cls):
        pool = Pool()
        Bank = pool.get('bank')
        result = {x.bic: x for x in Bank.search([])}
        return result

    @classmethod
    def execute(cls, agencies_file_path, logger):
        pool = Pool()
        Agency = pool.get('bank.agency')
        Address = pool.get('party.address')
        existing_agencies = cls.load_agencies()
        agencies_ids = set(existing_agencies.keys())
        existing_banks = cls.load_banks()
        agencies_to_create = []
        agencies_to_link = []
        agencies_to_rename = []
        addresses_to_create = []
        addresses_to_update = []
        already_treated = set([])
        addresses_by_name_and_party_bank = {}

        with open(agencies_file_path, 'rb') as f:
            reader = csv.reader(f, delimiter=';')
            for row in reader:
                bank_code, branch_code, bic, agency_name, _, street, \
                    streetbis, zip_and_city = [x.strip() for x in row]
                zip_, city = zip_and_city.split(None, 1)
                agency_id = bic + branch_code + bank_code
                if bic not in existing_banks:
                    continue
                bank = existing_banks[bic]
                address_values = {'street': street, 'streetbis': streetbis,
                    'zip': zip_, 'city': city, 'name': agency_name,
                    'party': bank.party.id}
                if agency_id not in agencies_ids:
                    agencies_to_create.append({'bank_code': bank_code,
                            'name': agency_name, 'bank': bank.id,
                            'branch_code': branch_code})
                    addresses_to_create.append(address_values)
                else:
                    agency = existing_agencies[agency_id]
                    old_address = agency.address
                    if old_address:
                        address_values.pop('party')
                        identical = all([getattr(old_address, k, None) == v
                                for k, v in address_values.iteritems()])
                        if (not identical and (agency_name, bank.id)
                                not in already_treated):
                            # in case two agencies of the same bank
                            # share the same address (and the same name)
                            # do not update twice
                            addresses_to_update.append([old_address])
                            addresses_to_update.append(address_values)
                        if agency.name != agency_name:
                            agency.name = agency_name
                            agencies_to_rename.append(agency)
                        already_treated.add((agency_name, bank.id))
                    else:
                        agency.name = agency_name
                        agencies_to_link.append(agency)
                        addresses_to_create.append(address_values)
            if addresses_to_create:
                created_address = Address.create(addresses_to_create)
                if logger:
                    logger.info('Created %s new addresses',
                        str(len(addresses_to_create)))
                addresses_by_name_and_party_bank.update({(x.name, x.party.id):
                        x for x in created_address})
            if agencies_to_create:
                new_agencies = Agency.create(agencies_to_create)
                agencies_to_link.extend(new_agencies)
                if logger:
                    logger.info('Created %s new agencies',
                        str(len(agencies_to_create)))
            if addresses_to_update:
                Address.write(*addresses_to_update)
                if logger:
                    logger.info('Updated %s addresses',
                        str(len(addresses_to_update) / 2))
            if agencies_to_link:
                for agency in agencies_to_link:
                    agency.address = addresses_by_name_and_party_bank[
                        (agency.name, agency.bank.party.id)]
            to_save = agencies_to_rename + agencies_to_link
            if to_save:
                Agency.save(to_save)
                if logger:
                    logger.info('Updated %s agencies', str(len(to_save)))
