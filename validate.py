# Copyright (C) 2018-2019 Stefano Zacchiroli <zack@upsilon.cc>
# License: GNU General Public License (GPL), version 2 or above

"""Beancount plugin that allows to enforce data validation rules on ledgers.

Rules are specified in a simple DSL implemented as Python functions.

Rules must be passed to the plugin via a configuration string that must be a
syntactically valid Python list consisting of validation rules (the string will
be eval()-ed by the plugin, you've been warned), e.g.::

  plugin "mybeancount.public.validate" "[
    ('bank operations must have a bank label',
     (has_account, r('^Assets:.*:Checking')), (has_metadata, 'bank-label')),
    ('receivables must have a debtor',
     (has_account, r('^Assets:(Receivables|Reimbursable)')),
     (has_metadata, 'debtor')),
    ('cheque payments must declare check number',
     (has_account, r(':Cheque$')), (has_metadata, 'cheque')),
    ('incomes must have payee',
     (has_account, r('^Income:')), (has_payee,)),
    ('payables must have a creditor',
     (has_account, r('^Liabilities:Payables')), (has_metadata, 'creditor')),
    ('metadata project must be either debian or spi',
     (has_metadata, 'project'), (metadata_value_in, 'project', ('debian', 'spi'))),
  ]"

Each rule is a triple <description, check, constraint>. Description is a human
readable string that will be shown in case of validation errors. Check is a
predicate on transactions. Constraint will be enforced on transactions iff the
Check predicate matches.

The following functions can be used to assemble checks and constraints:

- has_account
- has_metadata
- has_narration
- has_payee
- has_tag
- metadata_value_eq
- metadata_value_in

See the docstrings of the corresponding functions in this module for more
details about their semantics.

The following functions can be used as helpers:

- r: shortand for re.compile(), case-insensitive by default
- fake_tags: parse posting-specific tags out of a "tags" metadata

Again, see docstring for details.

"""

import collections
import re

from functools import partial

from beancount.core.data import filter_txns
from beancount.core.data import Transaction

__plugins__ = ('validate',)


MiscCheckError = collections.namedtuple(
    'MiscCheckError',
    'source message entry')

Rule = collections.namedtuple('Rule', ['description', 'match', 'constraint'])


def fake_tags(element):
    """parse "fake tags", i.e., metadata with key "tags" and values "tag1, tag2,
    ...", as if they were actual tags and return them as a list

    return the empty list if no "tags" metadata is defined

    expect as input a Beancount element (e.g., entries, but also postings) that
    equipped with a "meta" attribute

    XXX this function is required due to the fact that Beancount currently
    supports posting-level metadata but not tags; see:
    https://bitbucket.org/blais/beancount/issues/144/allow-tagging-of-individual-postings

    """
    return (tag.strip()
            for tag in element.meta.get('tags', '').split(','))


def r(string_regex, flags=re.IGNORECASE):
    """compile a regex

    """
    return re.compile(string_regex, flags=flags)


def has_account(account_RE, entry):
    """return True iff entry is a Transaction and has at least one posting whose
    account matches the account_RE regex

    """
    return (isinstance(entry, Transaction) and
            any(re.search(account_RE, posting.account)
                for posting in entry.postings))


def has_narration(narration_RE, entry):
    """return True iff entry is a Transaction whose narration matches given regex

    """
    return (isinstance(entry, Transaction) and
            re.search(narration_RE, entry.narration))


def has_metadata(key, entry):
    """return True iff entry is a Transaction and has a metadata value with key
    key.

    To satisfy the condition the metadata can be either on the transaction as a
    whole or on one of its postings.

    """
    return (isinstance(entry, Transaction) and
            (key in entry.meta or
             any(key in posting.meta for posting in entry.postings)))


def has_tag(tag, entry):
    """return True iff entry is a Transaction and has a tag called tag.

    To satisfy the condition the tag can be either on the transaction as a
    whole or on one of its postings.

    """
    return (isinstance(entry, Transaction) and
            (tag in entry.tags or
             any(tag in fake_tags(posting) for posting in entry.postings)))


def has_payee(entry):
    """return True iff entry is a Transaction with a payee (!= None)

    """
    return (isinstance(entry, Transaction) and entry.payee)


def metadata_value_eq(key, value, entry):
    """return True iff entry is a Transaction with a metadata key: value

    only checks for metadata on the transaction itself, ignoring postings

    """
    return (isinstance(entry, Transaction) and
            key in entry.meta and entry.meta[key] == value)


def metadata_value_in(key, values, entry):
    """return True iff entry is a Transaction with a metadata key whose value is
    one of values

    only checks for metadata on the transaction itself, ignoring postings

    """
    return (isinstance(entry, Transaction) and
            key in entry.meta and entry.meta[key] in values)


def compile_rules(raw_rules):
    """compile validation rules

    in particular, turn matches and constraints into boolean predicates over
    entries (i.e., functions: Entry -> bool)

    """
    return [Rule(description=dsc,
                 match=partial(match[0], *match[1:]),
                 constraint=partial(constr[0], *constr[1:]))
            for (dsc, match, constr) in raw_rules]


def validate_txn(entry, rules):
    """validate a single transaction and return all spotted errors

    """
    for rule in rules:
        if rule.match(entry) and not rule.constraint(entry):
            yield MiscCheckError(
                entry.meta,
                'Constraint validation: {}'.format(rule.description),
                entry)


def validate(entries, options_map, raw_rules):
    """Traverse all entries and ensure each of them satisfies RULES checks.

    Args:
      entries: a list of directives
      options_map: an options map (unused)
    Returns:
      a list of new errors, if any

    """
    errors = []
    rules = compile_rules(eval(raw_rules))

    for entry in filter_txns(entries):
        errors.extend(validate_txn(entry, rules))

    return entries, errors
