# Module for working with JSON i18n file

import json
import locale

from os import listdir
from os.path import isfile, join

global lang

__DEFAULT_LOCALES_FILE_PATH = 'data/lang/'
__DEFAULT_LANG_CODE = 'en_EN'


# Determines current system locale
def set_lang(code):

    global lang

    lang_code = code or locale.getdefaultlocale()[0]
    lang = __get_lang(lang_code)

    return lang_code

def __get_lang(lang_code):
    available_locale_files = __get_available_lang_lang_list(None)
    lang_file = None

    for local in available_locale_files:
        if local == lang_code + '.json':
            lang_file = __read_lang_file(lang_code + '.json')

    if lang_file is None:
        lang_file = __read_lang_file(__DEFAULT_LANG_CODE + '.json')

    if 'alias' in lang_file:
        lang_file = __get_lang(lang_file['alias'])

    return lang_file


def __read_lang_file(file_name):
    i18n_file = open(__DEFAULT_LOCALES_FILE_PATH + file_name)
    i18n = json.load(i18n_file)
    i18n_file.close()
    return i18n


def __get_available_lang_lang_list(path):
    if path is None:
        path = __DEFAULT_LOCALES_FILE_PATH
    available_locale_files = [f for f in listdir(path) if isfile(join(path, f))]
    return available_locale_files


# List of current supported locales
def get_lang_list():
    lang_list = []

    for locale_file in __get_available_lang_lang_list(None):
        i18n_file = open(__DEFAULT_LOCALES_FILE_PATH + locale_file)
        i18n = json.load(i18n_file)
        i18n_file.close()

        code = locale_file.split('.')[0]
        native = i18n['name']

        if 'alias' in i18n:
            code = i18n['alias']

        if 'native' in i18n:
            native = i18n['native']

        lang_list.append([code, i18n['name'], native])

    return lang_list


# Private recursive function for resolving localized string in lang dict
def __get_lang_str_inner(path, obj):
    global lang

    if lang is None:
        set_lang(None)

    if obj is None:
        obj = lang

    way = path.split(".", 1)
    elem = obj[way[0]]

    if len(way) == 1 and elem is not None:
        if isinstance(elem, type('str')) or isinstance(elem, type('int')):
            return obj[way[0]]
        else:
            raise ValueError("Can't use value \"%s\" of type %s" % (way[0], type(elem)))

    if isinstance(elem, dict):
        return __get_lang_str_inner(way[1], elem)

    raise ValueError("Value does not exists, or not in supported format %s" % way)


# Public function for resolving localized string in JSON xPath like way
def get_lang_str(path):
    return __get_lang_str_inner(path, None)