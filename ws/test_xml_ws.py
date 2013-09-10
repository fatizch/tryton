import xmlrpclib
import pprint
import json


def get_product_def(server_proxy, code, context, output_kind='python'):
    ids = server_proxy.model.offered.product.search([('code', '=', code)],
        context)
    res = server_proxy.model.offered.product.extract_object(ids[0],
        context)
    if output_kind == 'python':
        pprint.pprint(res)
    elif output_kind == 'xml':
        # print xmlrpclib.dumps(('domain', [('code', '=', code)]),
        #         'model.offered.product.search')
        print xmlrpclib.dumps((res, ), methodresponse=True)
    else:
        print json.dumps(res)


def export_contract(server_proxy, code, context, output_kind='python'):
    ids = server_proxy.model.contract.contract.search(
        [('offered.code', '=', code), ('id', '=', 5)], context)
    for id in ids:
        res = server_proxy.model.contract.contract.extract_object(id, context)
        if output_kind == 'python':
            pprint.pprint(res)
        elif output_kind == 'xml':
            print xmlrpclib.dumps(('contract_dict', res),
                'model.contract.contract.ws_subscribe_contract')
        else:
            print json.dumps(res)
        break

if __name__ == '__main__':
    user = 'admin'
    password = 'admin'
    db_name = 'mali'
    port = 8069
    server_address = 'localhost'
    output_kind = 'python'

    # Get user_id and session
    s = xmlrpclib.ServerProxy('http://%s:%s@%s:%s/%s' %
        (user, password, server_address, port, db_name),
        allow_none=1, use_datetime=1)

    # Get the user context
    context = s.model.res.user.get_preferences(True, {})

    get_product_def(s, 'kayes', context, output_kind=output_kind)
    export_contract(s, 'kayes', context, output_kind=output_kind)
