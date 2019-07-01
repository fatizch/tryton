# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree

__all__ = [
    'BankMobilityHandler',
    'FLOW5'
    ]


class BankMobilityHandler(object):

    def handle_file(self, file):
        raise NotImplementedError


class FLOW5(BankMobilityHandler):
    def handle_file(self, file):
        result = []
        message_id = ''
        for event, element in etree.iterparse(file):
            tag = etree.QName(element)
            if tag.localname == 'MsgId':
                message_id = element.text
            if tag.localname == 'Mod':
                d = {}
                d['message_id'] = message_id
                d['modification_id'] = element.findtext('{*}Id') or ''
                d['date_of_signature'] = element.findtext(
                    '{*}AcctSwtchngRef/{*}DtOfSgntr') or ''
                d['original_iban'] = element.findtext(
                    '{*}OrgnlPtyAndAcctId/{*}Acct/{*}IBAN') or ''
                d['original_bic'] = element.findtext(
                        '{*}OrgnlPtyAndAcctId/{*}Agt/{*}FinInstnId/{*}BICFI') \
                    or ''
                d['updated_iban'] = element.findtext(
                        '{*}UpdtdPtyAndAcctId/{*}Acct/{*}IBAN') or ''
                d['updated_bic'] = element.findtext(
                        '{*}UpdtdPtyAndAcctId/{*}Agt/{*}FinInstnId/{*}BICFI') \
                    or ''
                d['mandate_identification'] = [x.text for x in
                        element.findall('{*}TxRprt/{*}TxDtls/{*}Refs/{*}MndtId')
                        ]
                result.append([(d,)])
        return result
