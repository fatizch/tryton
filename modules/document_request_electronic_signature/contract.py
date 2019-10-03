# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = [
    'Contract',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    def init_subscription_document_request(self):
        DocumentRequestLine = Pool().get('document.request.line')
        super(Contract, self).init_subscription_document_request()
        DocumentRequestLine.update_electronic_signature_status(
            self.document_request_lines)

    def format_signature_url(self, url):
        return url.format(contract=self)

    @classmethod
    def get_calculated_required_documents(cls, contracts):
        res = super(Contract, cls).get_calculated_required_documents(contracts)
        DocumentDesc = Pool().get('document.description')
        desc_codes = set()
        for k, documents in res.items():
            for k, v in documents.items():
                desc_codes |= v.keys()
        desc_dict = dict((d.code, d) for d in DocumentDesc.search(
            ['code', 'in', desc_codes]))
        new_res = {}
        for contract, documents in res.items():
            new_res[contract] = {}
            for k, v in documents.items():
                cur_dict = {}
                new_res[contract][k] = cur_dict
                for desc_code, desc_settings in v.items():
                    desc = desc_dict[desc_code]
                    cur_dict[desc_code] = desc_settings
                    for sub_doc in [s.doc for s in desc.sub_documents]:
                        cur_dict[sub_doc.code] = desc_settings
        return new_res
