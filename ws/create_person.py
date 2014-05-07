import xmlrpclib
import os.path
import ast
import ConfigParser
import os

if __name__ == '__main__':
    parser = ConfigParser.ConfigParser()
    with open('ws.conf') as fp:
        parser.readfp(fp)
    conf = dict(parser.items('connection'))
    # Get user_id and session
    s = xmlrpclib.ServerProxy('http://%s:%s@%s:%s/%s' % (
            conf['user'], conf['password'], conf['server_address'],
            conf['port'], conf['db_name']),
        allow_none=1, use_datetime=1, verbose=1)

    # Find all files in directory person
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fichiers = []
    for root, dirs, files in os.walk(os.path.join(current_dir, 'person')):
        for i in files:
            fichiers.append(os.path.join(root, i))
    # Get the user context
    context = s.model.res.user.get_preferences(True, {})
    for cur_fichier in fichiers:
        with open(cur_fichier, 'r') as fichier:
            person_dict_string = fichier.read()
            person_dict = ast.literal_eval(person_dict_string)
            res = s.model.party.party.ws_create_person(person_dict, context)
            print xmlrpclib.dumps((res, ), methodresponse=True)
