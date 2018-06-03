# Copyright (C) 2018 Stefano Zacchiroli <zack@upsilon.cc>
# License: GNU General Public License (GPL), version 2 or above

"""Beancount plugin that allows to enforce data validation rules on ledgers.

Rules are specified via an external YAML file and interpreted according to
`Cerberus <http://docs.python-cerberus.org/>`_ semantics. The rules file must
be passed to the plugin as a configuration string, e.g.::

    plugin "mybeancount.public.validate" "validate.yaml"


Rules
-----

A rule is a pair <match, schema>, where the match defines to which Beancount
elements the rule applies, and schema the constraint to be enforced on matching
elements. The rules file is hence a list of rules, expressed in YAML syntax,
like this::

      - match:
          # rule 1's match goes here
        schema:
          # rule 1's constraint goes here

      - match:
          # rule 2's match
        schema:
          # rule 2's constraint

      - match:
          # rule 3's match
        schema:
          # rule 3's constraint

    - # etc.


Matches
-------

By default rules are applied to Beancount transactions. You can override the
default using the "target" property of matches, which can be the name of a
top-level Beancount entries ("transaction", "open", "document", etc.),
"posting" (meaning individual transaction postings), or the special value "all"
(meaning all top-level entries). Examples::

    - match:
        target: transaction  # this is default, apply rule to transactions
      ...

    - match:
        target: open  # apply rule to open entries instead
      ...

    - match:
        target:  # apply rule to transactions, open, and document entries
          - document
          - open
          - transaction
      ...

    - match:
        target: all  # apply rule to to all top-level entries
      ...

    - match:
        target: posting  # apply rule to individual postings
      ...


Schemas
-------

TODO document schemas here


Validated elements
------------------

Schema validation is enforced on Beancount elements which conforms with the
definitions found in the beancount.core.data module, after some "massaging"
meant to ease data validation. In particular, the following transformations
are applied before validation:

* lifting from namedtuples to nested dictionaries: the tuple structure of
  beancount.core.data is transformed to nested dictionaries, using the
  _asdict() method of namedtuples recursively. This allow to uniformly traverse
  the AST using Cerberus schemas (Cerberus doesn't allow to validate
  attributes). For instance, you can pretend 'meta' is a key of transaction
  directives, even if in beancount.core.data it is a namedtuple attribute.

* propagation of metadata from transactions to postings. For instance, given
  the following input transaction::

      1970-01-01 * "grocery"
        author: "zack"
        Expenses:Grocery      10.00 EUR
          foo: "bar"
        Assets:Checking

  what validators will actually validate is::

      1970-01-01 * "grocery"
        author: "zack"
        Expenses:Grocery      10.00 EUR
          foo: "bar"
          author: "zack"
        Assets:Checking
          author: "zack"

Note that these transformations are in effect only for validation and are
discarded afterwards. The set of directives returned by this plugin are
unchanged w.r.t. its input.

"""

import collections
import copy
import logging
import re
import yaml

from beancount.core import data
from cerberus import Validator
from functools import partial, reduce


__plugins__ = ('validate',)


ValidationError = collections.namedtuple(
    'ValidationError',
    'source message entry')


ALL_TARGETS = data.ALL_DIRECTIVES
DEFAULT_TARGETS = [data.Transaction]


def dict_lookup(d, path):
    """recursive lookup in nested dictionaries"""
    try:
        return reduce(dict.__getitem__, path, d)
    except KeyError:
        return None


def parse_target(target_str):
    """parse a Beancount directive type from its name in string form"""
    map = {
        'close': data.Close,
        'commodity': data.Commodity,
        'custom': data.Custom,
        'document': data.Document,
        'event': data.Event,
        'note': data.Note,
        'open': data.Open,
        'pad': data.Pad,
        'posting': data.Posting,
        'price': data.Price,
        'query': data.Query,
        'transaction': data.Transaction,
    }
    return map[target_str.lower()]


def load_cerberus_rule(check):
    # TODO implement heuristics here to reduce schema verbosity
    return check


def element_to_dict(entry):
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


def propagate_meta(from_elt, to_elt):
    """update metadata of to_elt Beacount element using from_elt's ones

    WARNING: to_elt is both returned and modified in place

    """
    if from_elt.meta:
        if not to_elt.meta:
            to_elt.meta = {}
        # XXX we should probably blacklist 'filename' and 'lineno' here
        to_elt.meta.update(from_elt.meta)

    return to_elt


def rule_applies(rule, element):
    """return True iff a rule should be applied to a Beancount element"""
    (match, _check) = rule

    if match is None:  # catch all match
        return True

    targets = DEFAULT_TARGETS
    if 'target' in match:
        target = match['target']
        if isinstance(target, str):
            # TODO this forbids merging 'all' with 'posting'; make it possible
            if target == 'all':
                targets = ALL_TARGETS
            else:
                targets = [parse_target(target)]
        elif isinstance(target, list):
            targets = map(parse_target, target)
        else:
            logging.warn('invalid target for rule {}, using default'
                         .format(rule))

    if not any(filter(partial(isinstance, element), targets)):
        return False  # current entry is not an instance of any target

    element_d = element_to_dict(element)
    if 'account' in match:
        account_RE = re.compile(match['account'].strip('/'))
        if isinstance(element, data.Transaction) \
           and not txn_has_account(element_d, account_RE):
            return False
        if isinstance(element, data.Posting) \
           and not account_RE.search(element.account):
            return False

    # TODO check dict "path"

    return True


def rule_validates(rule, element):
    """return True iff a rule validates a Beancount element

    precondition: it has already been established (e.g., using rule_applies)
    that the rule should be applied to this element

    """
    (_match, check) = rule

    validator = Validator(check)
    validator.allow_unknown = True
    element_d = element_to_dict(element)

    return validator.validate(element_d)


def validate_entry(entry, rules):
    """Validate a single Beancount entry against a set of rules

    Returns:
      a list of errors, if any
    """

    def apply_rule(rule, element, entry):
        if rule_applies(rule, element):
            if not rule_validates(rule, element):
                return [ValidationError(
                    entry.meta,
                    '{} offends rule {}'.format(element, rule),
                    entry)]
        return []

    errors = []

    for rule in rules:  # validate top-level entries
        errors.extend(apply_rule(rule, entry, entry))

    if isinstance(entry, data.Transaction):  # validate txn postings
        for posting in entry.postings:
            posting = propagate_meta(entry, copy.deepcopy(posting))
            errors.extend(apply_rule(rule, posting, entry))

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
    rules = [(rule['match'], load_cerberus_rule(rule['schema']))
             for rule in yaml.load(open(rules_file))]

    errors = []
    for entry in entries:
        errors.extend(validate_entry(entry, rules))

    return entries, errors
