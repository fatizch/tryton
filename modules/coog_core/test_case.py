# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

MODULE_NAME = 'coog_core'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(TestCaseModel, cls).__setup__()
        cls._error_messages.update({
                'no_language': 'No language is selected, users won\'t have '
                'a language',
                })

    @classmethod
    def get_user_group_dict(cls):
        user_group_dict = defaultdict(list)
        user_group_dict['product'].append('coog_core.group_global_config')
        return user_group_dict

    @classmethod
    def create_or_update_users_groups(cls):
        pool = Pool()
        user_group_dict = cls.get_user_group_dict()
        dict_authorization_users = user_group_dict.keys()
        dict_authorization_groups = list(set(
            [x for y in user_group_dict.values() for x in y]))
        Group = pool.get('res.group')
        User = pool.get('res.user')
        UserGroup = pool.get('res.user-res.group')
        authorization_groups = Group.search(
            [
                ('xml_id', 'in', dict_authorization_groups)
            ])
        assert len(authorization_groups) == len(dict_authorization_groups), \
            dict_authorization_groups
        lang = Transaction().context.get('language')
        Lang = pool.get('ir.lang')
        lang, = Lang.search([('code', '=', lang)], limit=1)
        if not lang:
            cls.raise_user_warning('no_language', 'no_language')
        authorization_users = User.search(
            [
                ('login', 'in', [x + '_user'
                    for x in dict_authorization_users]),
            ])
        for authorization_user in dict_authorization_users:
            user_login = authorization_user + '_user'
            if user_login not in [x.login for x in authorization_users]:
                user = User()
                user.name = authorization_user + ' user'
                user.login = user_login
                user.password = 'coog'
                if lang:
                    user.language = lang
                user.save()
            else:
                user = [x for x in authorization_users
                    if x.login == user_login][0]
            user_existing_groups = UserGroup.search(
                [
                    ('user', '=', user)
                ])
            for group in user_group_dict[authorization_user]:
                if group not in [x.group.xml_id for x in user_existing_groups]:
                    user_group = UserGroup()
                    user_group.user = user
                    user_group.group = [g for g in authorization_groups
                        if g.xml_id == group][0]
                    user_group.save()

    @classmethod
    def authorizations_test_case(cls):
        cls.create_or_update_users_groups()

    @classmethod
    def authorizations_test_case_test_method(cls):
        return True
