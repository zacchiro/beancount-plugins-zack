# Copyright (C) 2016 Stefano Zacchiroli <zack@upsilon.cc>
# License: GNU General Public License (GPL), version 3 or above

"""This Beancount plugin validates that each Beancount file that contains 2 or
more directives is strictly chronologically ordered. I.e., no directive that
occurs later in a given file (according to file order) has a date that occurs
earlier (in calendar order) than a previous directive in the same file.

While Beancount by default doesn't care about file ordering of directives,
ensuring strict file ordering is a useful check to avoid certain kinds of
booking errors, e.g., copy-pasting an old transaction to much later in a file,
forgetting to bump its date.

"""

# TODO this plugin can be easily made configurable to, e.g.:
# - enforce reverse date ordering
# - enforce ordering on arbitrary metadata, not only date

import collections

from beancount.core.data import filter_txns

__plugins__ = ('validate_file_ordering',)


FileOrderingError = collections.namedtuple(
    'FileOrderingError',
    'source message entry')


def txns_by_file(entries):
    """Group a list of transaction by origin file and sort them by line number.

    Args:
      entries: a list of directives. All non-transaction directives are ignored
    Returns:
      a dictionary mapping filenames to entries belonging to that file, sorted
      by line number

    """
    file_entries = {}  # return dict

    for entry in filter_txns(entries):  # group by file
        if 'filename' not in entry.meta:
            continue
        filename = entry.meta['filename']

        if filename not in file_entries:
            file_entries[filename] = []
        file_entries[filename].append(entry)

    for filename in file_entries:  # sort by line number
        file_entries[filename].sort(key=lambda e: e.meta['lineno'])

    return file_entries


def validate_date_ordering(entries):
    """Ensure that a given list of entries is chronologically ordered, from oldest
    to most recent date

    Args:
      entries: a list of directives
    Returns:
      a list of new errors, if any

    """
    errors = []
    prev_date = None

    for entry in entries:
        if prev_date and entry.date < prev_date:
            errors.append(FileOrderingError(
                entry.meta,
                'Date {} appears after {}, violating in-file date ordering'
                .format(entry.date, prev_date),
                entry))

        prev_date = entry.date

    return errors


def validate_file_ordering(entries, options_map):
    """Traverse all directives and ensure that, within the same file, their line
    numbers are strictly increasing. This implies that directives are sorted by
    date in all processed beancount files.

    Args:
      entries: A list of directives.
      unused_options_map: An options map.
    Returns:
      A list of new errors, if any were found.

    """
    errors = []

    for file_entries in txns_by_file(entries).values():
        errors.extend(validate_date_ordering(file_entries))

    return entries, errors
