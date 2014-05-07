import xmlrpclib
import pprint
import json
import ConfigParser
import os
import ast


def get_product_def(server_proxy, code, context, output_kind='python'):
    res = server_proxy.model.offered.product.get_product_def(code,
        context)
    if output_kind == 'python':
        pprint.pprint(res)
    elif output_kind == 'xml':
        print xmlrpclib.dumps((res, ), methodresponse=True)
    else:
        print json.dumps(res)


if __name__ == '__main__':
    parser = ConfigParser.ConfigParser()
    with open('ws.conf') as fp:
        parser.readfp(fp)
    conf = dict(parser.items('connection'))

    # Get user_id and session
    s = xmlrpclib.ServerProxy('http://%s:%s@%s:%s/%s' % (
            conf['user'], conf['password'], conf['server_address'],
            conf['port'], conf['db_name']),
        allow_none=1, use_datetime=1)

    # Get the user context
    context = s.model.res.user.get_preferences(True, {})

    current_dir = os.path.dirname(os.path.abspath(__file__))
    fichiers = []
    for root, dirs, files in os.walk(os.path.join(current_dir, 'contract')):
        for i in files:
            fichiers.append(os.path.join(root, i))

    for cur_fichier in fichiers:
        with open(cur_fichier, 'r') as fichier:
            contract_dict_string = fichier.read()
            contract_dict = ast.literal_eval(contract_dict_string)
            res = s.model.contract.ws_subscribe_contract(contract_dict, context)
            print xmlrpclib.dumps((res, ), methodresponse=True)
