# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import csv
import io

from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.transaction import Transaction
from trytond.modules.coog_core import model, fields


__all__ = [
    'BankDataSet',
    'BankDataSetWizard',
    ]

COLUMN_NAMES = {
    'name': {'coog_file': 'bank_name', 'swift': 'INSTITUTION NAME'},
    'branch_name': {'coog_file': 'branch_name', 'swift': 'BRANCH INFORMATION'},
    'city': {'coog_file': 'address_city', 'swift': 'CITY'},
    'zip': {'coog_file': 'address_zip', 'swift': 'ZIP CODE'},
    }


class BankDataSet(model.CoogView):
    'Bank Data Set'

    __name__ = 'bank_cog.data.set'

    file_format = fields.Selection([
            ('coog_file', 'Coog File'), ('swift', 'Swift')], 'File Format')
    use_default = fields.Boolean('Use default file', states={
        'invisible': Eval('file_format') == 'swift'})
    resource = fields.Binary('Resource', states={
            'invisible': Bool(Eval('use_default'))
            })
    data_file = fields.Char('Default Data file', states={
            'readonly': True,
            'invisible': True,
            })
    is_update = fields.Boolean('Update', help='If set to True, '
        'the existing banks will be updated')
    countries_to_import = fields.One2Many('country.country', None,
        'Countries to import', states={
            'invisible': Eval('file_format') != 'swift'}, readonly=True,
        help='Countries for which bics will be imported')

    @staticmethod
    def default_use_default():
        return True

    @fields.depends('use_default', 'file_format')
    def on_change_with_data_file(self):
        if self.use_default and self.file_format == 'coog_file':
            filename = 'bank.csv'
            top_path = os.path.abspath(os.path.dirname(__file__))
            return os.path.join(
                top_path, 'test_case_data',
                Transaction().language, filename)
        return ''

    @fields.depends('file_format')
    def on_change_with_countries_to_import(self):
        if self.file_format == 'swift':
            configuration = Pool().get('party.configuration')(1)
            return [country.id for country in configuration.bic_swift_countries]
        return []

    @fields.depends('file_format', 'use_default')
    def on_change_with_use_default(self):
        if self.file_format == 'swift':
            return False
        return self.use_default


class BankDataSetWizard(Wizard):
    'Bank Database Set Wizard'

    __name__ = 'bank_cog.data.set.wizard'

    start_state = 'configuration'
    configuration = StateView('bank_cog.data.set',
        'bank_cog.bank_data_set_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Set', 'set_', 'tryton-ok', default=True),
            ])
    set_ = StateTransition()

    def read_resource_file(self):
        if self.configuration.file_format == 'coog_file':
            with open(self.configuration.data_file, 'r') as _file:
                reader = csv.DictReader(_file, delimiter=';')
                for row in reader:
                    yield row
        else:
            data = self.configuration.resource
            delimiter = ';'
            if self.configuration.file_format == 'swift':
                delimiter = '\t'
                data = io.StringIO(data.decode())
            reader = csv.DictReader(data, delimiter=delimiter)
            for row in reader:
                yield row

    def address_compare(self, address, bank_row, country, street):
        file_format = self.configuration.file_format
        return ((not address.street and not street or address.street == street)
            and (not address.zip and not bank_row.get(COLUMN_NAMES['zip'][
                file_format]) or address.zip == bank_row.get(COLUMN_NAMES[
                    'zip'][file_format])) and
            (not address.city and not bank_row.get(COLUMN_NAMES['city'][
                file_format]) or address.city == bank_row.get(COLUMN_NAMES[
                    'city'][file_format])) and
            (not address.country and not country or
                address.country.id == country.id))

    def get_address(self, bank_row, country, party):
        file_format = self.configuration.file_format
        street = bank_row['address_street'] if file_format == 'coog_file' else \
            f'{bank_row["STREET ADDRESS 1"]}\n{bank_row["STREET ADDRESS 2"]}' \
            f'\n{bank_row["STREET ADDRESS 3"]}\n{bank_row["STREET ADDRESS 4"]}'
        address = None
        for cur_address in party.addresses:
            if (self.address_compare(cur_address, bank_row, country, street)):
                address = cur_address
                break

        if not address:
            Address = Pool().get('party.address')
            address = Address(
                street=street,
                city=bank_row.get(COLUMN_NAMES['city'][file_format]),
                zip=bank_row.get(COLUMN_NAMES['zip'][file_format]),
                country=country,
                party=None)

        return address

    def _update_bank(self, bank, party, bank_row, country, banks):
        address = self.get_address(bank_row, country, party)
        bank.party = party
        bank.address = address
        banks.append(bank)

    def _update_existing_bank(self, bank, bank_row, country, parties, bic,
            parties_to_save, banks):
        key = COLUMN_NAMES['name'][self.configuration.file_format]
        Party = Pool().get('party.party')
        if bic[0:8] in parties:
            party = parties[bic[0:8]]
            if party.name == bank_row[key]:
                self._update_bank(bank, party, bank_row, country, banks)
            else:
                existing_party = Party.search(
                    ['name', '=', bank_row[key]], limit=1)
                if existing_party:
                    party = existing_party[0]
                else:
                    party = Party(name=bank_row[key],
                                  addresses=[], all_addresses=None)
                    parties_to_save.append(party)
                self._update_bank(bank, party, bank_row, country, banks)
                parties[bic[0:8]] = party
        else:
            party = Party(name=bank_row[key], addresses=[],
                          all_addresses=None)
            self._update_bank(bank, party, bank_row, country, banks)
            parties[bic[0:8]] = party
            parties_to_save.append(party)

    def _create_bank(self, bank_row, country, parties, bic, parties_to_save,
            banks, existing_banks):
        file_format = self.configuration.file_format
        pool = Pool()
        Bank = pool.get('bank')
        Party = pool.get('party.party')
        bic = bic if file_format == 'swift' else bank_row['bic']
        try:
            party = parties[bic[0:8]]
        except KeyError:
            party = Party(name=bank_row[COLUMN_NAMES['name'][file_format]],
                addresses=[], all_addresses=None)
            parties_to_save.append(party)
            parties[bic[0:8]] = party

        address = self.get_address(bank_row, country, party)

        bank = Bank(
            bic=bic,
            party=party,
            name=bank_row[COLUMN_NAMES['branch_name'][file_format]].strip('()'),
            address=address)
        banks.append(bank)
        existing_banks[bank.bic] = bank

    @staticmethod
    def _save_data(parties_to_save, banks):
        pool = Pool()
        Bank = pool.get('bank')
        Party = pool.get('party.party')
        Party.save(parties_to_save)
        addresses_to_save = []
        for bank in banks:
            if bank.address.party is None:
                bank.address.party = bank.party
                addresses_to_save.append(bank.address)

        if addresses_to_save:
            pool.get('party.address').save(addresses_to_save)
        Bank.save(banks)

    def import_coog_file(self):
        pool = Pool()
        Bank = pool.get('bank')
        Party = pool.get('party.party')
        Country = pool.get('country.country')
        banks = []
        existing_banks = dict((x.bic, x) for x in Bank.search([]))
        parties = {x.bank_role[0].bic[0:8]: x
                   for x in Party.search([('is_bank', '=', True)])}
        parties_to_save = list(parties.values())
        for bank_row in self.read_resource_file():
            bic = ('%sXXX' % bank_row['bic']
                   if len(bank_row['bic']) == 8 else bank_row['bic'])
            country = Country.get_instance_from_code(
                bank_row['address_country'].upper())
            if bic in existing_banks:
                if not self.configuration.is_update:
                    continue
                bank = existing_banks[bic]
                if bank.party.name == bank_row['bank_name']:
                    continue
                self._update_existing_bank(bank, bank_row, country,
                    parties, bic, parties_to_save, banks)
                continue
            self._create_bank(bank_row, country, parties, bic,
                parties_to_save, banks, existing_banks)
        self.__class__._save_data(parties_to_save, banks)

    def import_swift(self):
        pool = Pool()
        Party = pool.get('party.party')
        Bank = pool.get('bank')
        Country = pool.get('country.country')
        banks = []
        existing_banks = dict((x.bic, x) for x in Bank.search([]))
        parties = {x.bank_role[0].bic[0:8]: x
                   for x in Party.search([('is_bank', '=', True)])}
        parties_to_save = []
        for bank_row in self.read_resource_file():
            if bank_row.get('BIC') or bank_row.get('BIC8'):
                country_code = bank_row['ISO COUNTRY CODE']
                if country_code in [country.code for country in
                        self.configuration.countries_to_import]:
                    country = Country.get_instance_from_code(country_code)
                    bic = bank_row.get('BIC') or (bank_row.get('BIC8') + (
                            bank_row.get('BRANCH BIC') or 'XXX'))
                    if bic in existing_banks:
                        bank = existing_banks[bic]
                        if bank.party.name == bank_row['INSTITUTION NAME']:
                            continue
                        self._update_existing_bank(bank, bank_row, country,
                            parties, bic, parties_to_save, banks)
                        continue
                    self._create_bank(bank_row, country, parties, bic,
                        parties_to_save, banks, existing_banks)
        self.__class__._save_data(parties_to_save, banks)

    def transition_set_(self):
        if self.configuration.file_format == 'coog_file':
            self.import_coog_file()
        else:
            self.import_swift()
        return 'end'
