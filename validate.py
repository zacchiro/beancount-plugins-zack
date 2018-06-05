# Copyright (C) 2018 Stefano Zacchiroli <zack@upsilon.cc>
# License: GNU General Public License (GPL), version 2 or above

"""Beancount plugin that allows to enforce data validation rules on ledgers.

Rules are specified via an external YAML file and interpreted according to
`Cerberus <http://docs.python-cerberus.org/>`_ semantics. The rules file must
be passed to the plugin as a configuration string, e.g.::

    plugin "mybeancount.public.validate" "validate.yaml"


Rules
=====

A rule is conceptually a pair <match, constraint>, where the match defines to
which Beancount elements the rule applies, and constraint(s) to be enforced on
matching elements. Additional, a rule description is required for ease of rule
reference. The rules file is hence a list of rules, expressed in YAML syntax,
like this::

      - description: rule 1's description
        match:
          # rule 1's match goes here
        constraint:
          # rule 1's constraint goes here

      - description: rule 1's description
        match:
          # rule 2's match
        constraint:
          # rule 2's constraint

      - description: rule 1's description
        match:
          # rule 3's match
        constraint:
          # rule 3's constraint

    - # etc.


Constraints
===========

TODO document constraints here, pointing to Cerberus


Matches
=======

By default rules are applied to Beancount transactions. You can override the
default using the "target" property of match sections; its value can be the
name of a top-level Beancount entry ("transaction", "open", "document", etc.),
"posting" (meaning individual transaction postings), or the special value "all"
(meaning all top-level entries). You can also use a list of those values to
match multiple Beancount elements at once. Examples::

    - match:
        target: transaction  # the default: apply rule to transactions
      ...

    - match:
        target: open  # apply rule to open entries instead
      ...

    - match:
        target:  # apply rule to transaction, open, and document entries
          - document
          - open
          - transaction
      ...

    - match:
        target: all  # apply rule to to all top-level entries
      ...

    - match:
        target: posting  # apply rule to individual transaction postings
      ...

TODO document "account" match property here

TODO document "schema" match property here


Validation data model
=====================

Constraints are enforced on Beancount elements which conforms with the
definitions found in the :mod:`beancount.core.data` module, after some
"massaging" to ease data validation. In particular, the following
transformations are applied before validation:

* conversion from nested namedtuples to nested dictionaries: the tuple
  structure of beancount.core.data is transformed to nested dictionaries, using
  the _asdict() method of namedtuples recursively. This allow to validate
  Beancount abstract syntax trees (ASTs) using Cerberus schemas (Cerberus
  doesn't allow to validate attributes). For instance, you can pretend 'meta'
  is a key of transaction directives, even if in beancount.core.data it is a
  namedtuple attribute.

* propagation of metadata from transactions down to postings. For instance,
  given the following input transaction::

      1970-01-01 * "grocery"
        author: "zack"
        Expenses:Grocery      10.00 EUR
          foo: "bar"
        Assets:Checking

  what validation rules will actually consider is::

      1970-01-01 * "grocery"
        author: "zack"
        Expenses:Grocery      10.00 EUR
          foo: "bar"
          author: "zack"
        Assets:Checking
          author: "zack"

Note that these transformations are in effect only during validation and are
discarded afterwards. The set of directives returned by this plugin are
unchanged w.r.t. its input.

"""

import collections
import copy
import re
import yaml

from beancount.core import data
from cerberus import Validator


__plugins__ = ('validate',)


RuleError = collections.namedtuple(
    'RuleError',
    'source message entry')
ValidationError = collections.namedtuple(
    'ValidationError',
    'source message entry')


ALL_TARGETS = data.ALL_DIRECTIVES
DEFAULT_TARGETS = [data.Transaction]


def parse_target(target_str):
    """parse a Beancount directive type from its name in string form"""
    map = {
        'all': ALL_TARGETS,
        'close': [data.Close],
        'commodity': [data.Commodity],
        'custom': [data.Custom],
        'document': [data.Document],
        'event': [data.Event],
        'note': [data.Note],
        'open': [data.Open],
        'pad': [data.Pad],
        'posting': [data.Posting],
        'price': [data.Price],
        'query': [data.Query],
        'transaction': [data.Transaction],
    }
    return map[target_str.lower()]  # TODO return RuleError if parsing fails


def element_to_dict(entry):
    """lift a Beancount entry to a (nested) dict structure, so that rules can be
    checked by uniformly traversing nested dictionaries

    """
    def lift_posting(posting):
        posting = posting._asdict()
        posting['_type'] = data.Posting
        units = posting['units']._asdict()
        units['_type'] = data.Amount
        posting['units'] = units
        # TODO handle cost and price

        return posting

    entry_type = type(entry)
    d = entry._asdict()
    d['_type'] = entry_type

    if entry_type == data.Transaction:
        d['postings'] = list(map(lift_posting, d['postings']))
    # TODO handle other types of entries

    return d


def txn_has_account(txn_dict, account_RE):
    """return True iff transaction txn_dict (as a dict) has at least one posting
    whose account matches the account_RE regex

    """
    return any(map(lambda p: account_RE.search(p['account']),
                   txn_dict['postings']))


def propagate_meta(from_elt, to_elt):
    """update metadata of to_elt Beancount element using from_elt's ones

    both Beancount elements are expected to be in dict format

    WARNING: to_elt is both returned and modified in place

    """
    # XXX we should probably blacklist 'filename' and 'lineno' here
    to_elt['meta'].update(from_elt['meta'])

    return to_elt


def load_rule(rule):

    def new_validator(schema):
        v = Validator(schema)
        v.allow_unknown = True
        return v

    try:
        target = rule['match']['target']
        rule['match']['target'] = DEFAULT_TARGETS
        if target is not None:
            if isinstance(target, str):
                target = [target]
            rule['match']['target'] = [t for ts in map(parse_target, target)
                                       for t in ts]
    except KeyError:
        pass

    try:  # Cerberus validators used for matching
        rule['match']['schema'] = new_validator(rule['match']['schema'])
    except KeyError:
        pass

    try:  # Cerberus validators used for enforcement
        rule['constraint'] = new_validator(rule['constraint'])
    except KeyError:
        pass

    try:  # account regexs
        account = rule['match']['account']
        if account.startswith('/') and account.endswith('/'):
            rule['match']['account'] = re.compile(account.strip('/'))
        else:  # not a regex, enforce strict string matching
            rule['match']['account'] = re.compile('^{}$'.format(account))
    except KeyError:
        pass

    return rule


def rule_applies(rule, element_d):
    """return True iff a rule should be applied to a Beancount element (as a dict)

    """
    match = rule['match']
    if match is None:  # catch-all match
        return True

    if element_d['_type'] not in rule['match']['target']:
        return False  # current entry is not an instance of any target

    if 'account' in match:
        account_RE = match['account']
        if element_d['_type'] == data.Transaction \
           and not txn_has_account(element_d, account_RE):
            return False
        if element_d['_type'] == data.Posting \
           and not account_RE.search(element_d['account']):
            return False

    if 'schema' in match and not match['schema'].validate(element_d):
        return False

    return True


def rule_validates(rule, element_d):
    """return True iff a rule validates a Beancount element (as a dict)

    precondition: it has already been established (e.g., using rule_applies)
    that the rule should be applied to this element

    """
    return rule['constraint'].validate(element_d)


def validate_entry(entry, rules):
    """Validate a single Beancount entry against a set of rules

    Returns:
      a list of errors, if any
    """

    def apply_rule(rule, element, context):
        if rule_applies(rule, element) and not rule_validates(rule, element):
            return [ValidationError(
                context.meta,
                'Constraint violation: {description}'.format(**rule),
                context)]
        return []

    entry_dict = element_to_dict(entry)
    errors = []

    for rule in rules:  # validate top-level entries
        errors.extend(apply_rule(rule, element=entry_dict, context=entry))

        if entry_dict['_type'] == data.Transaction:  # validate txn postings
            for posting in entry_dict['postings']:
                posting = propagate_meta(entry_dict, copy.deepcopy(posting))
                errors.extend(apply_rule(rule, element=posting, context=entry))

    return errors


# from profilehooks import profile
# @profile
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
    rules = list(map(load_rule, yaml.load(open(rules_file))))

    errors = []
    for entry in entries:
        errors.extend(validate_entry(entry, rules))

    return entries, errors
