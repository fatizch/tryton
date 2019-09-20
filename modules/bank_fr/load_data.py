# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields

__all__ = [
    'BankDataSet',
    'BankDataSetWizard',
    ]


class BankDataSet(metaclass=PoolMeta):
    __name__ = 'bank_cog.data.set'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.file_format.selection.append(
            ('banque_de_france', 'Banque De France'))

    @staticmethod
    def default_file_format():
        return 'banque_de_france'

    @fields.depends('use_default', 'file_format')
    def on_change_with_data_file(self):
        if self.use_default and self.file_format == 'banque_de_france':
            filename = 'banque_de_france'
            top_path = os.path.abspath(os.path.dirname(__file__))
            return os.path.join(
                top_path, 'test_case_data',
                Transaction().language, filename)
        return super().on_change_with_data_file()


class BanqueDeFranceBankLine(object):
    def __init__(self, line):
        self._line = line

    @property
    def name(self):
        return self._line[12:52].strip()

    @property
    def commercial_name(self):
        return self._line[248:287].strip()

    @property
    def bic(self):
        unformatted_bic = self._line[237:248].strip()
        formatted_bic = ('%sXXX' % unformatted_bic if len(unformatted_bic) == 8
            else unformatted_bic)
        return formatted_bic

    @property
    def street(self):
        address_line_1 = self._line[89:121].strip()
        address_line_2 = self._line[121:153].strip()
        address_line_3 = self._line[153:185].strip()
        return '\n'.join([x for x in (address_line_1,
                address_line_2, address_line_3) if x])

    @property
    def zip_code(self):
        return self._line[185:190].strip()

    @property
    def city(self):
        return self._line[191:216].strip()


class BanqueDeFranceAgencyLine(object):
    def __init__(self, line):
        self._line = line

    @property
    def bic(self):
        unformatted_bic = self._line[234:245].strip()
        formatted_bic = ('%sXXX' % unformatted_bic if len(unformatted_bic) == 8
            else unformatted_bic)
        return formatted_bic

    @property
    def agency_state(self):
        return self._line[11:12].strip()

    @property
    def bank_code(self):
        if self.agency_state == '2':
            return self._line[72:77].strip()
        else:
            return self._line[1:6].strip()

    @property
    def origin_bank_code(self):
        return self._line[1:6].strip()

    @property
    def branch_code(self):
        if self.agency_state == '2':
            return self._line[77:82].strip()
        else:
            return self._line[6:11].strip()

    @property
    def origin_branch_code(self):
        return self._line[6:11].strip()

    @property
    def name(self):
        return self._line[52:72].strip()

    @property
    def street(self):
        address_line_1 = self._line[106:138].strip()
        address_line_2 = self._line[138:170].strip()
        address_line_3 = self._line[170:202].strip()
        return '\n'.join([x for x in (address_line_1,
            address_line_2, address_line_3) if x])

    @property
    def zip_code(self):
        return self._line[202:207].strip()

    @property
    def city(self):
        return self._line[208:233].strip()


class BankDataSetWizard(metaclass=PoolMeta):
    __name__ = 'bank_cog.data.set.wizard'

    _SAVE_SIZE = 200

    def get_file_reader(self):
        if self.configuration.use_default:
            with open(self.configuration.data_file, 'r') as _file:
                return _file.readlines()
        else:
            return [line.decode('utf-8')
                for line in self.configuration.resource.split(b'\n')]

    def transition_set_(self):
        # This method overloads bank_cog behavior to allow uploading
        # Banque de France standard file. This file contains banks and bank
        # agencies to create/update. As it is not possible to reference non
        # existing banks from agencies, this method first parses all bank lines
        # and saves them before parsing all agency lines and saving them.
        pool = Pool()
        Bank = pool.get('bank')
        Country = pool.get('country.country')
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        Agency = pool.get('bank.agency')

        france, = Country.search([
                ('code', '=', 'FR')])

        def load_existing(existing_banks, existing_parties):
            for x in Bank.search([]):
                existing_banks[x.bic] = x
                existing_parties[x.bic[:8]] = x.party

        existing_banks, existing_parties = {}, {}
        treated_banks = set([''])
        load_existing(existing_banks, existing_parties)
        agencies_to_create = []
        agencies_to_update = []
        addresses_to_create = []
        addresses_to_update = []
        first_agency = False

        if self.configuration.file_format == 'banque_de_france':
            saver_bank = model.Saver(Bank)
            saver_address = model.Saver(Address)
            for line in self.get_file_reader():
                if not line:
                    continue
                if line[0] == '1':
                    clean_line = BanqueDeFranceBankLine(line=line)
                    bic, name, commercial_name, street, zip_code, city = \
                        clean_line.bic, clean_line.name, \
                        clean_line.commercial_name, clean_line.street, \
                        clean_line.zip_code, clean_line.city
                    if bic in treated_banks:
                        continue
                    party = existing_parties.get(bic[:8], None) or Party(
                        name=name,
                        commercial_name=commercial_name,
                        addresses=[])
                    addr_dict = {
                        'street': street,
                        'city': city,
                        'zip': zip_code,
                        }
                    address = self.check_addresses(party, addr_dict,
                        france)
                    if address is None:
                        address = Address(
                            street=street,
                            city=city,
                            country=france,
                            party=party)
                        saver_address.append(address)
                    bank = None
                    if bic in existing_banks:
                        bank = existing_banks[bic]
                        bank.bic = bic
                        bank.party = party
                        bank.name = name
                        bank.commercial_name = commercial_name
                        bank.address = address
                    else:
                        bank = Bank(
                            bic=bic,
                            party=party,
                            name=name,
                            address=address)
                    treated_banks.add(bic)
                    saver_bank.append(bank)
                elif line[0] == '3':
                    if first_agency is False:
                        saver_address.finish()
                        saver_bank.finish()
                        load_existing(existing_banks, existing_parties)
                        existing_agencies = {';'.join(
                                [x.bank.bic, x.branch_code, x.bank_code]): x
                            for x in Agency.search([()])}
                        first_agency = True
                    clean_line = BanqueDeFranceAgencyLine(line=line)
                    bic = clean_line.bic
                    if bic == '':
                        continue
                    if bic in existing_banks:
                        agency_bank = existing_banks[bic]
                    else:
                        continue
                    bank_code = clean_line.bank_code
                    branch_code = clean_line.branch_code
                    if bank_code == '' or branch_code == '':
                        continue
                    agency_name = clean_line.name
                    agency_street = clean_line.street
                    agency_zip = clean_line.zip_code
                    agency_city = clean_line.city

                    agency = existing_agencies.get(';'.join([bic,
                                clean_line.origin_branch_code,
                                clean_line.origin_bank_code]), None)
                    if agency:
                        agency_address = agency.address
                        agency_address.street = agency_street
                        agency_address.city = agency_city
                        agency_address.zip = agency_zip
                        agency_address.party = agency_bank.party
                        agency.name = agency_name
                        agency.bank_code = bank_code
                        agency.branch_code = branch_code
                        agency.address = agency_address
                        agencies_to_update.append(agency)
                        addresses_to_update.append(agency_address)
                    else:
                        if (agency_zip == '' or agency_city == ''
                                or agency_street == ''):
                            agency_address = agency_bank.address
                        else:
                            agency_address = Address(
                                street=agency_street,
                                city=agency_city,
                                zip=agency_zip,
                                country=france,
                                party=agency_bank.party)
                            addresses_to_create.append(agency_address)
                        agency = Agency(
                            bank=agency_bank,
                            name=agency_name,
                            bank_code=bank_code,
                            branch_code=branch_code,
                            address=agency_address)
                        agencies_to_create.append(agency)
                else:
                    continue
            if addresses_to_create:
                self.create_by_slices(Address, addresses_to_create,
                    self._SAVE_SIZE)
            if addresses_to_update:
                self.write_by_slices(Address, addresses_to_update,
                    self._SAVE_SIZE)
            if agencies_to_create:
                self.create_by_slices(Agency, agencies_to_create,
                    self._SAVE_SIZE)

            if agencies_to_update:
                self.write_by_slices(Agency, agencies_to_update,
                    self._SAVE_SIZE)
            return 'end'
        else:
            return super().transition_set_()

    def check_addresses(self, party, addr_dict, country):
        result = None
        if party:
            for address in party.addresses:
                if (address.street == addr_dict.get('street', '') and
                        address.zip == addr_dict.get('zip', '') and
                        address.city == addr_dict.get('city', '') and
                        address.country.id == country.id):
                    result = address
        return result

    def create_by_slices(self, model, records, size):
        records_size = len(records)
        cur = 0
        while cur < records_size:
            model.create([x._save_values for x in records[cur:(cur + size)]
                    if x._save_values])
            cur = cur + size
        model.create([x._save_values for x in records[cur:records_size]
                if x._save_values])

    def write_by_slices(self, model, records, size):
        records_size = len(records)
        cur = 0
        while cur < records_size:
            model.save(records[cur:(cur + size)])
            cur = cur + size
        model.save(records[cur:records_size])
