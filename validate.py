# Copyright (C) 2018 Stefano Zacchiroli <zack@upsilon.cc>
# License: GNU General Public License (GPL), version 2 or above

"""Beancount plugin that allows to enforce data validation rules on ledgers.

Rules are specified via an external YAML file and interpreted according to
`Cerberus <http://docs.python-cerberus.org/>`_ semantics. The rules file must
be passed to the plugin as a configuration string, e.g.::

    plugin "mybeancount.public.validate" "validate.yaml"

"""

import collections
import re
import yaml

from beancount.core import data
from cerberus import Validator
from functools import reduce


__plugins__ = ('validate',)


ValidationError = collections.namedtuple(
    'ValidationError',
    'source message entry')


DEFAULT_TARGET = data.Transaction


def dict_lookup(d, path):
    """recursive lookup in nested dictionaries"""
    try:
        return reduce(dict.__getitem__, path, d)
    except KeyError:
        return None


def parse_target(target_str):
    """parse a Beancount directive type from its name in string form"""
    map = {
        # 'close': data.Close,
        # 'commodity': data.Commodity,
        # 'custom': data.Custom,
        # 'document': data.Document,
        # 'event': data.Event,
        # 'note': data.Note,
        # 'open': data.Open,
        # 'pad': data.Pad,
        # 'price': data.Price,
        # 'query': data.Query,
        'transaction': data.Transaction,
    }
    return map[target_str.lower()]


def entry_to_dict(entry):
    """lift a Beancount entry to a (nested) dict structure, so that rules can be
    checked by uniformly traversing nested dictionaries

    """

    def lift_posting(posting):
        posting = posting._asdict()
        posting['units'] = posting['units']._asdict()
        # TODO handle cost and price

        return posting

    d = entry._asdict()
    if isinstance(entry, data.Transaction):
        d['postings'] = map(lift_posting, d['postings'])
    # TODO handle other types of entries

    return d


def txn_has_account(txn_dict, account_RE):
    """return True iff transaction txn_dict (as a dict) has at least one posting
    whose account matches the account_RE regex

    """
    return any(map(lambda p: account_RE.search(p['account']),
                   txn_dict['postings']))


def rule_applies(rule, entry):
    """return True iff a rule should be applied to a Beancount entry"""
    (match, _check) = rule

    if match is None:  # catch all match
        return True

    target = DEFAULT_TARGET
    if 'target' in match:
        target = parse_target(match['target'])
    if not isinstance(entry, target):
        return False

    entry_d = entry_to_dict(entry)
    if isinstance(entry, data.Transaction) and 'has_account' in match:
        if not txn_has_account(entry_d,
                               re.compile(match['has_account'].strip('/'))):
            return False

    # TODO check dict "path"

    return True


def rule_validates(rule, entry):
    """return True iff a rule validates a Beancount entry

    precondition: it has already been established (e.g., using rule_applies)
    that the rule should be applied to this entry

    """
    (_match, check) = rule

    validator = Validator(check)
    validator.allow_unknown = True
    entry_d = entry_to_dict(entry)

    return validator.validate(entry_d)


def validate_entry(entry, rules):
    """Validate a single Beancount entry against a set of rules

    Returns:
      a list of errors, if any
    """
    errors = []

    for rule in rules:
        if rule_applies(rule, entry):
            if not rule_validates(rule, entry):
                errors.append(ValidationError(
                    entry.meta,
                    'Fails validation rule {}'.format(rule),
                    entry))

    return errors


def validate(entries, options_map, rules_file):
    """Enfore data-validation rules

    Args:
      entries: a list of directives
      options_map: an options map (unused)
      rules_file: the name of a YAML file containing validation rules
    Returns:
      a pair formed by the input entries (unchanged) and a list of
      ValidationError errors (if any)

    """
    # parse rules as a list of <match, check> pairs
    rules = [(rule['match'], {k: rule[k] for k in rule if k != 'match'})
             for rule in yaml.load(open(rules_file))]

    errors = []
    for entry in entries:
        errors.extend(validate_entry(entry, rules))

    return entries, errors
