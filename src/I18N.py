# Module for working with JSON i18n file

import json
import locale

from os import listdir
from os.path import isfile, join

global lang
lang = None


# Determines current system locale
def set_lang(code):
    #TODO: Use seperate files
    global lang

    lang_code = code or locale.getdefaultlocale()[0]
    i18n_file = open('data/i18n.json')
    i18n = json.load(i18n_file)
    i18n_file.close()

    if code is not None:
        for lang_name in i18n:
            if lang_name == lang_code:
                if "alias" in i18n[lang_name]:
                    lang_code = i18n[lang_name]['alias']
                lang = i18n[lang_code]
                break
    else:
        if lang is None:
            set_lang('en_EN')

    return lang_code

def __scan_files():
    onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
    return;

# List of current supported locales
def get_lang_list():
    i18n_file = open('data/i18n.json')
    i18n = json.load(i18n_file)
    i18n_file.close()
    lang_list = []

    for lang in i18n:
        code = lang
        native = i18n[lang]['name']

        if 'alias' in i18n[code]:
            code = i18n[code]['alias']

        if 'native' in i18n[code]:
            native = i18n[code]['native']

        lang_list.append([lang, i18n[lang]['name'], native])

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

