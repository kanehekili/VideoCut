# Module for working with JSON i8n file

import json
import locale

global lang
lang = None


# Determines current system locale
def get_lang():
    global lang
    if lang is None:
        lang_code = locale.getdefaultlocale()[0]
        i8n_file = open('data/i8n.json')
        i8n = json.load(i8n_file)

        for lang_name in i8n:
            if lang_name == lang_code:
                if i8n[lang_name]["alias"] is not None and i8n[i8n[lang_name]["alias"]] is not None:
                    lang = i8n[i8n[lang_name]["alias"]]
                break

        if lang is None:
            lang = i8n['en_EN']

        i8n_file.close()
    return lang


# List of current supported locales
def get_lang_list():
    i8n_file = open('data/i8n.json')
    i8n = json.load(i8n_file)
    lang_list = []

    for lang in i8n:
        lang_list.append([lang, i8n[lang]['name']])

    i8n_file.close()
    return lang_list


# Private recursive function for resolving localized string in lang dict
def __get_lang_str_inner(path, obj):
    global lang
    if lang is None:
        lang = get_lang()

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

    raise ValueError("Значение не существует либо не является результирующим %s" % way)
    return None


# Public function for resolving localized string in JSON xPath like way
def get_lang_str(path):
    return __get_lang_str_inner(path, None)
