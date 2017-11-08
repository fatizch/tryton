# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree
from dateutil.parser import parse

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
                d['message_id'] = unicode(message_id, 'utf-8')
                d['modification_id'] = unicode(element.findtext('{*}Id') or '',
                    'utf-8')
                d['date_of_signature'] = unicode(element.findtext(
                        '{*}AcctSwtchngRef/{*}DtOfSgntr') or '', "utf-8")
                d['original_iban'] = unicode(element.findtext(
                        '{*}OrgnlPtyAndAcctId/{*}Acct/{*}IBAN') or '', "utf-8")
                d['original_bic'] = unicode(element.findtext(
                        '{*}OrgnlPtyAndAcctId/{*}Agt/{*}FinInstnId/{*}BICFI') \
                    or '', "utf-8")
                d['updated_iban'] = unicode(element.findtext(
                        '{*}UpdtdPtyAndAcctId/{*}Acct/{*}IBAN') or '', "utf-8")
                d['updated_bic'] = unicode(element.findtext(
                        '{*}UpdtdPtyAndAcctId/{*}Agt/{*}FinInstnId/{*}BICFI') \
                    or '', "utf-8")
                d['mandate_identification'] = [unicode(x.text, 'utf-8') for x in 
                        element.findall('{*}TxRprt/{*}TxDtls/{*}Refs/{*}MndtId')
                        ]
                result.append([d,])
        return result
