# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
__all__ = ['assert_eq', 'assert_not_eq']


def assert_eq(value_1, value_2):
    '''
        Checks values equality, and print a nice message if they are not
    '''
    if value_1 != value_2:
        raise AssertionError('Assertion error, got %s, expected %s' % (
            str(value_1), str(value_2)))


def assert_not_eq(value_1, value_2):
    if value_1 == value_2:
        raise AssertionError(
            'Assertion error, expected inequality, got %s' % str(value_1))
