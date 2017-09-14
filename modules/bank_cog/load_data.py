# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import csv
from io import BytesIO
from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.transaction import Transaction
from trytond.modules.coog_core import model, fields


__all__ = [
    'BankDataSet',
    'BankDataSetWizard',
    ]


class BankDataSet(model.CoogView):
    'Bank Data Set'

    __name__ = 'bank_cog.data.set'

    use_default = fields.Boolean('Use default file')
    resource = fields.Binary('Resource', states={
            'invisible': Bool(Eval('use_default'))
            })
    data_file = fields.Char('Default Data file', states={
            'readonly': True,
            'invisible': True,
            })

    @staticmethod
    def default_data_file():
        filename = 'bank.csv'
        top_path = os.path.abspath(os.path.dirname(__file__))
        data_path = os.path.join(
            top_path, 'test_case_data',
            Transaction().language, filename)
        return data_path

    @staticmethod
    def default_use_default():
        return True


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
        if self.configuration.use_default is True:
            with open(self.configuration.data_file, 'rb') as _file:
                data = BytesIO(_file.read())
        else:
            data = BytesIO(self.configuration.resource)

        reader = csv.DictReader(data, delimiter=';')
        for row in reader:
            yield row

    def address_compare(self, address, bank_row, country):
        return ((not address.street and not bank_row['address_street'] or
                address.street == bank_row['address_street']) and
            (not address.zip and not bank_row['address_zip'] or
                address.zip == bank_row['address_zip']) and
            (not address.city and not bank_row['address_city'] or
                address.city == bank_row['address_city']) and
            (not address.country and not country or
                address.country.id == country.id))

    def transition_set_(self):
        pool = Pool()
        Bank = pool.get('bank')
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        Country = pool.get('country.country')

        banks = []
        existing_banks = dict((x.bic, x) for x in Bank.search([]))
        parties = dict((x.bank_role[0].bic[0:4], [x, list(x.addresses)])
            for x in Party.search([('is_bank', '=', True)]))
        for bank_row in self.read_resource_file():
            bic = ('%sXXX' % bank_row['bic']
                if len(bank_row['bic']) == 8 else bank_row['bic'])
            if bic in existing_banks:
                continue

            addresses = []
            address = None
            country = None
            countries = Country.search(
                [('code', '=', bank_row['address_country'].upper())],
                limit=1)
            if countries:
                country = countries[0]
            try:
                party, addresses = parties[bic[0:4]]
                for cur_address in addresses:
                    if (self.address_compare(cur_address, bank_row, country)):
                        address = cur_address
                        break
            except KeyError:
                party = Party(name=bank_row['bank_name'])
                parties[bic[0:4]] = [party, addresses]

            if not address:
                address = Address(
                    street=bank_row['address_street'],
                    city=bank_row['address_city'],
                    zip=bank_row['address_zip'],
                    country=country,
                    party=party)
                parties[bic[0:4]][1].append(address)

            bank = Bank(
                bic=bank_row['bic'],
                party=party,
                name=bank_row['branch_name'].strip('()'),
                address=address)
            banks.append(bank)
            existing_banks[bank.bic] = bank

        Bank.create([x._save_values for x in banks])
        return 'end'
