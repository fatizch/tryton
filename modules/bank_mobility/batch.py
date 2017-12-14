# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import codecs

from io import BytesIO
from datetime import datetime, date
from collections import defaultdict

from trytond.pool import Pool

from trytond.modules.coog_core import batch, utils
from trytond.modules.endorsement.wizard import EndorsementWizardStepMixin
from .bank_mobility_handler import FLOW5


class BankMobilityBatch(batch.BatchRootNoSelect):
    'Bank Mobility Batch'

    __name__ = 'bank.mobility'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(BankMobilityBatch, cls).__setup__()
        cls._error_messages.update({
                'bic_not_found': 'No bank found for BIC %(bic)s',
                'bank_account_not_found': 'No account number found for '
                'IBAN:%(iban)s, BIC:%(bic)s',
                'mandate_not_found': 'No valid mandate found for'
                ' identification:%(identification)s',
                'mandate_signature_date_in_future': 'Mandate with'
                ' identification:%(identification)s has been signed on '
                '%(mandate_signature_date)s, after mobility signature '
                'date on %(mobility_signature_date)s',
                'mandate_amendment_date_in_future': 'Mandate with '
                'identification:%(identification)s has been amended on '
                '%(amendment_date)s, after mobility signature date on '
                '%(mobility_signature_date)s'
                })
        cls._default_config_items.update({
                'job_size': 1,
                })

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return [x for x in ids]

    @classmethod
    def get_file_handler(cls):
        return FLOW5()

    @classmethod
    def parse_params(cls, params):
        params = super(BankMobilityBatch, cls).parse_params(params)
        assert params['in_directory'], "'in_directory' is missing in batch arguments"
        assert params['archive'], "'archive' is missing in batch arguments"
        return params

    @classmethod
    def select_ids(cls, in_directory, archive):
        files = cls.get_file_names_and_paths(in_directory)
        if not files:
            cls.logger.info('No file found in directory %s' % in_directory)
            return []
        all_elements = []
        for file_name, file_path in files:
            with codecs.open(file_path, 'r') as _file:
                source = _file.read()
                f = BytesIO(source)
                handler = cls.get_file_handler()
                all_elements.extend(handler.handle_file(f))
        cls.archive_treated_files(files, archive, utils.today())
        return all_elements

    @classmethod
    def execute(cls, objects, ids, in_directory=None, archive=None):
        if not ids:
            return
        for x in ids:
            cls.treat_mobility_modification(
                x['message_id'],
                x['modification_id'],
                datetime.strptime(x['date_of_signature'],
                    '%Y-%m-%d').date(),
                x['original_iban'],
                x['original_bic'],
                x['updated_iban'],
                x['updated_bic'],
                x['mandate_identification'])
        return ids

    @classmethod
    def get_endorsement_definition(cls):
        pool = Pool()
        EndorsementDefinition = pool.get('endorsement.definition')
        definition, = EndorsementDefinition.search([
                ('code', '=', 'mobilite_bancaire'),
                ('active', 'in', [True, False])])
        return definition

    @classmethod
    def treat_mobility_modification(cls, message_id, modification_id,
            date_of_signature, original_iban, original_bic, updated_iban,
            updated_bic, mandate_identification):
        # search original bank account
        orgl_bank_account = cls.find_bank_account(original_iban, original_bic)
        if not orgl_bank_account:
            cls.raise_user_error('bank_account_not_found', {
                    'iban': original_iban, 'bic': original_bic})

        # search sepa mandates to amend
        sepa_mandates = cls.find_sepa_mandates(mandate_identification,
            orgl_bank_account)
        if not sepa_mandates and mandate_identification:
            cls.raise_user_error('mandate_not_found',
                {'identification':', '.join(mandate_identification)})
        for mandate in sepa_mandates:
            if mandate.signature_date >= date_of_signature:
                cls.raise_user_error('mandate_signature_date_in_future',
                    {'identification': mandate.identification,
                        'mandate_signature_date': mandate.signature_date,
                        'mobility_signature_date': date_of_signature})
            if mandate.start_date and mandate.start_date >= date_of_signature:
                cls.raise_user_error('mandate_amendment_date_in_future',
                    {'identification': mandate.identification,
                        'amendment_date': mandate.start_date,
                        'mobility_signature_date': date_of_signature})
        # update original bank account
        if (orgl_bank_account.end_date is None or
                orgl_bank_account.end_date > date_of_signature):
            orgl_bank_account.end_date = date_of_signature
            orgl_bank_account.save()
        # create new bank account. Owners are sepa mandates parties
        # or original bank account owners
        owners = []
        if sepa_mandates:
            owners = [m.party for m in sepa_mandates]
        else:
            owners = orgl_bank_account.owners
        owners = list(set(owners))
        updt_bank_account = cls.create_or_update_bank_account(updated_iban,
            updated_bic, date_of_signature, owners)

        # amend sepa madates
        new_mandates = {}
        for mandate in sepa_mandates:
            if mandate.account_number != updt_bank_account.numbers[0]:
                new_mandate = cls.amend_mandate(mandate, updt_bank_account,
                    date_of_signature)
                new_mandates[mandate.identification] = new_mandate
            else:
                new_mandates[mandate.identification] = mandate

        # endorse contracts related to mandates
        cls.endorse_contracts(sepa_mandates, new_mandates, date_of_signature,
            message_id, modification_id)

    @classmethod
    def endorse_contracts(cls, prev_mandates, new_mandates, date_of_signature,
            message_id, modification_id):
        pool = Pool()
        BillingInformation = pool.get('contract.billing_information')
        Endorsement = pool.get('endorsement')

        # 1) build a dictionary 'to_endorse' with
        # - original_mandate as key
        # - (contract_to_endorse, related_bil_info, new_mandate) list as value

        # search contracts candidates
        billing_informations = BillingInformation.search([
                ('sepa_mandate', 'in', prev_mandates)])
        contracts = list(set([x.contract for x in billing_informations]))
        bil_info_set = set(billing_informations)
        # ignore outdated billing informations and contracts
        to_endorse = defaultdict(list)
        for contract in contracts:
            if contract.end_date and contract.end_date < date_of_signature:
                continue
            ordered_bil_infos = list(contract.billing_informations)
            ordered_bil_infos.sort(
                key=lambda x: x.date if x.date else date.min)
            for i in xrange(len(ordered_bil_infos) - 1, -1, -1):
                if (ordered_bil_infos[i].date is None or
                        ordered_bil_infos[i].date <= date_of_signature):
                    ordered_bil_infos = ordered_bil_infos[i:]
                    break
            bil_info_to_endorse = [x for x in ordered_bil_infos if x in
                bil_info_set]
            if not bil_info_to_endorse:
                continue
            cur_mandate = bil_info_to_endorse[0].sepa_mandate
            to_endorse[cur_mandate].append((contract, bil_info_to_endorse[0],
                    new_mandates[cur_mandate.identification]))

        # 2) endorse contracts
        endorsement_definition = cls.get_endorsement_definition()
        endorsements = []
        for key, value in to_endorse.iteritems():
            endorsement, = Endorsement.create([{
                    'effective_date' : date_of_signature,
                    'definition' : endorsement_definition.id,
                    }])
            endorsement.contract_endorsements = [
                cls.get_contract_endorsement(
                    x[0], x[1], date_of_signature,x[2]) for x in value]
            endorsement.number = '_'.join([endorsement.number, message_id,
                    modification_id])

            endorsements.append(endorsement)
        Endorsement.save(endorsements)
        Endorsement.apply(endorsements)

    @classmethod
    def get_contract_endorsement(cls, contract, bil_info, date_of_signature,
            new_mandate):
        pool = Pool()
        EndorsementContract = pool.get('endorsement.contract')
        BillingInformation = pool.get('contract.billing_information')
        bil_info_effective_date = bil_info.date if bil_info.date \
            else contract.start_date
        effective_date = max(date_of_signature, bil_info_effective_date)
        billing_informations = [x for x in contract.billing_informations
            if (x.date is None or x.date <= effective_date)]
        if (bil_info_effective_date != effective_date):
            # create new billing_information
            new_billing_information = BillingInformation()
            new_billing_information.date = effective_date
            for fname in ('payment_term', 'billing_mode', 'payer',
                    'direct_debit_day'):
                setattr(new_billing_information, fname, getattr(
                        bil_info, fname))
            new_billing_information.sepa_mandate = new_mandate
            new_billing_information.direct_debit_account = \
                new_mandate.account_number.account
            billing_informations.append(new_billing_information)
        else:
            # update billing information
            billing_informations[-1].sepa_mandate = new_mandate
            billing_informations[-1].direct_debit_account = \
                new_mandate.account_number.account
        contract.billing_informations = billing_informations
        endorsement_contract = EndorsementContract(contract=contract)
        EndorsementWizardStepMixin._update_endorsement(endorsement_contract,
            contract._save_values)
        return endorsement_contract

    @classmethod
    def find_bank_account(cls, iban, bic):
        pool = Pool()
        Bank = pool.get('bank')
        BankAccountNumber = pool.get('bank.account.number')
        BankAccount = pool.get('bank.account')
        bank = Bank.search([('bic', '=', bic)])
        if not bank:
            cls.raise_user_error('bic_not_found', {'bic': bic})
        else:
            bank = bank[0]
        bank_account_number = BankAccountNumber.search([
                ('number', '=', iban),
                ('type', '=', 'iban')])
        if not bank_account_number:
            return None
        else:
            bank_account_number = bank_account_number[0]
        bank_account = BankAccount.search([
                ('bank', '=', bank.id),
                ('numbers', '=', bank_account_number.id)])
        if not bank_account:
            return None
        else:
            return bank_account[0]

    @classmethod
    def create_or_update_bank_account(cls, iban, bic, date_of_signature, owners):
        pool = Pool()
        Bank = pool.get('bank')
        BankAccountNumber = pool.get('bank.account.number')
        BankAccount = pool.get('bank.account')
        bank_account = cls.find_bank_account(iban, bic)
        if not bank_account:
            # Bank Account Creation
            bank = Bank.search([('bic', '=', bic)])
            if not bank:
                cls.raise_user_error('bic_not_found', {'bic': bic})
            else:
                bank = bank[0]
            bank_account = BankAccount(
                bank=bank,
                numbers=[BankAccountNumber(
                    number=iban,
                    type='iban')],
                start_date=date_of_signature,
                owners=owners)
            bank_account.save()
        else:
            need_update = False
            if (bank_account.start_date and
                    bank_account.start_date > date_of_signature):
                bank_account.start_date = date_of_signature
                need_update = True
            owners = [x for x in owners if x not in bank_account.owners]
            if owners:
                bank_account.owners.extend(owners)
                need_update = True
            if need_update:
                bank_account.save()
        return bank_account

    @classmethod
    def find_sepa_mandates(cls, mandate_identification, orgl_bank_account):
        # mandate_identification is not mandatory: all mandates
        # related to original bank account are searched if not provided
        pool = Pool()
        SepaMandate = pool.get('account.payment.sepa.mandate')
        mandate_clause = []
        if mandate_identification:
            mandate_clause.append(('identification', 'in',
                    mandate_identification))
        else:
            mandate_clause.append(('account_number', 'in',
                    orgl_bank_account.numbers))
        sepa_mandates = SepaMandate.search(mandate_clause)

        # remove all amended sepa mandates
        def remove_amended(mandates):
            amendments = SepaMandate.search([('amendment_of', 'in',
                        [x.id for x in mandates])])
            amended = [m.amendment_of for m in amendments]
            return [x for x in mandates if x not in amended]
        valid_sepa_mandates = remove_amended(sepa_mandates)
        return valid_sepa_mandates

    @classmethod
    def amend_mandate(cls, prev_mandate, new_bank_account, amendment_date):
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')
        new_mandate = Mandate()
        field_names = ('party', 'company', 'type', 'scheme',
                'signature_date', 'identification')
        for fname in field_names:
            setattr(new_mandate, fname, getattr(prev_mandate, fname))
        new_mandate.account_number = new_bank_account.numbers[0]
        new_mandate.start_date = amendment_date
        new_mandate.amendment_of = prev_mandate
        new_mandate.state = 'validated'
        new_mandate.save()
        return new_mandate
