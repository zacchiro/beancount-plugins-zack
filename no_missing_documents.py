# Copyright (C) 2018 Stefano Zacchiroli <zack@upsilon.cc>
# License: GNU General Public License (GPL), version 2 or above

"""This Beancount plugin validates that each Beancount transaction that
contains a document metadata key has as value a path corresponding to an
existing file on disk.

The list of metadata keys considered to be documents default to the single key
"document". The default can be overridden passing a configuration string, which
should be a comma-separated list of metadata keys, e.g.::

    plugin "no_missing_documents" "receipt,statement,invoice"

"""

import collections
import os

from beancount.core.data import filter_txns

__plugins__ = ('validate_documents',)


DocumentNotFoundError = collections.namedtuple(
    'DocumentNotFoundError',
    'source message entry')


# default list of metada keys that are expected to point to existing documents
DEFAULT_KEYS = ['document']


def parse_keys(config_str):
    return config_str.split(',')


def validate_documents(entries, options_map, config_str=''):
    """Ensure that "document" metadata keys correspond to existing files

    Args:
      entries: a list of directives
      options_map: an options map (unused)
    Returns:
      a pair formed by the input entries (unchanged) and a list of
      DocumentNotFoundError errors (if any)

    """
    errors = []

    document_keys = parse_keys(config_str)

    for entry in entries:
        for key in document_keys:
            try:
                document = entry.meta[key]
                if not os.path.isfile(document):
                    errors.append(DocumentNotFoundError(
                        entry.meta,
                        'Document not found: {}'.format(document),
                        entry))
            except KeyError:
                pass
                
    return entries, errors
