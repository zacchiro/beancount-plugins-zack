# Copyright (C) 2018 Stefano Zacchiroli <zack@upsilon.cc>
# License: GNU General Public License (GPL), version 2 or above

"""This Beancount plugin validates that documents referenced from Beancount
files correspond to existing files on disks. It will return a
DocumentNotFoundError for each document that cannot be found on disk.

Given a list of Beancount entries, the following documents will be checked by
the plugin:

* Filenames of ``document`` directives.

* Metadata associated to any directive, as long as the metadata key is in the
  (configurable) set of keys that the plugin will consider.

  By default, the plugin will look only for the `document` metadata. The
  default can be overridden passing the plugin a configuration string, which
  should be a comma-separated list of metadata keys, e.g.::

      plugin "no_missing_documents" "receipt,statement,invoice"

"""

import collections
import os

from beancount.core import data


__plugins__ = ('validate_documents',)


DocumentNotFoundError = collections.namedtuple(
    'DocumentNotFoundError',
    'source message entry')


# default list of metada keys that are expected to point to existing documents
DEFAULT_KEYS = ['document']

CHECK_DOCUMENT_ENTRIES = False  # disabled as Beancount core does this already


def parse_keys(config_str):
    return config_str.split(',')


def check_missing(entry, document):
    errors = []

    if not os.path.isfile(document):
        errors.append(DocumentNotFoundError(
            entry.meta,
            'Document not found: {}'.format(document),
            entry))

    return errors


def validate_documents(entries, options_map, config_str=None):
    """Ensure that "document" metadata keys correspond to existing files

    Args:
      entries: a list of directives
      options_map: an options map (unused)
    Returns:
      a pair formed by the input entries (unchanged) and a list of
      DocumentNotFoundError errors (if any)

    """
    errors = []

    document_keys = DEFAULT_KEYS
    if config_str is not None:
        document_keys = parse_keys(config_str)

    for entry in entries:
        # check the filename property of document directives
        if isinstance(entry, data.Document) and CHECK_DOCUMENT_ENTRIES:
            errors.extend(check_missing(entry, entry.filename))

        # check requested metadata of all directives (including documents)
        for key in document_keys:
            if key in entry.meta:
                errors.extend(check_missing(entry, entry.meta[key]))
                
    return entries, errors
