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
                d['message_id'] = str(message_id, 'utf-8')
                d['modification_id'] = str(element.findtext('{*}Id') or '',
                    'utf-8')
                d['date_of_signature'] = str(element.findtext(
                        '{*}AcctSwtchngRef/{*}DtOfSgntr') or '', "utf-8")
                d['original_iban'] = str(element.findtext(
                        '{*}OrgnlPtyAndAcctId/{*}Acct/{*}IBAN') or '', "utf-8")
                d['original_bic'] = str(element.findtext(
                        '{*}OrgnlPtyAndAcctId/{*}Agt/{*}FinInstnId/{*}BICFI')
                    or '', "utf-8")
                d['updated_iban'] = str(element.findtext(
                        '{*}UpdtdPtyAndAcctId/{*}Acct/{*}IBAN') or '', "utf-8")
                d['updated_bic'] = str(element.findtext(
                        '{*}UpdtdPtyAndAcctId/{*}Agt/{*}FinInstnId/{*}BICFI')
                    or '', "utf-8")
                d['mandate_identification'] = [str(x.text, 'utf-8') for x in
                        element.findall('{*}TxRprt/{*}TxDtls/{*}Refs/{*}MndtId')
                        ]
                result.append([d])
        return result
