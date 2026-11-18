# Copyright (C) 2020 Software in the Public Interest, Inc.
# Author: Martin Michlmayr <tbm@cyrius.com>
# License: GNU General Public License (GPL), version 2 or above
"""Tests for the validate plugin"""

import unittest

from beancount import loader
from beancount.core.data import filter_txns

from validate import r
from validate import has_account
from validate import has_metadata
from validate import has_narration
from validate import has_tag
from validate import has_payee
from validate import metadata_value_eq
from validate import metadata_value_in


class TestHasAccount(unittest.TestCase):
    """Test has_account()"""

    @loader.load_doc()
    def test_has_account(self, entries, _, __):
        """
        2020-02-14 open Assets:Foo
        2020-02-14 open Assets:Bar
        2020-02-14 * ""
            Assets:Foo             10.00 EUR
            Assets:Bar
        """
        entries = list(filter_txns(entries))
        self.assertEqual(has_account(r('Assets:Foo'), entries[0]), True)
        self.assertEqual(has_account(r('Assets:F.*'), entries[0]), True)
        self.assertEqual(has_account(r('Assets:Fo$'), entries[0]), False)
        self.assertEqual(has_account(r('Assets:Bar'), entries[0]), True)
        self.assertEqual(has_account(r('Assets:Ba.$'), entries[0]), True)
        self.assertEqual(has_account(r('Expenses:Test'), entries[0]), False)


class TestHasMetaData(unittest.TestCase):
    """Test has_metadata()"""

    @loader.load_doc()
    def test_has_metadata(self, entries, _, __):
        """
        2020-02-14 open Assets:Foo
        2020-02-14 open Assets:Bar
        2020-02-14 * "Has metadata"
            test: "bar"
            Assets:Foo             10.00 EUR
            Assets:Bar
        2020-02-14 * "No metadata"
            Assets:Foo             10.00 EUR
            Assets:Bar
        2020-02-14 * "Has metadata on posting"
            Assets:Foo             10.00 EUR
              test: "bar"
            Assets:Bar
        """
        entries = list(filter_txns(entries))
        self.assertEqual(has_metadata('test', entries[0]), True)
        self.assertEqual(has_metadata('test', entries[1]), False)
        self.assertEqual(has_metadata('test', entries[2]), True)


class TestHasNarration(unittest.TestCase):
    """Test has_narration()"""

    @loader.load_doc()
    def test_has_narration(self, entries, _, __):
        """
        2020-02-14 open Assets:Foo
        2020-02-14 open Assets:Bar
        2020-02-14 * "Test"
            Assets:Foo             10.00 EUR
            Assets:Bar
        2020-02-14 * "Payee" ""
            Assets:Foo             10.00 EUR
            Assets:Bar
        2020-02-14 * ""
            Assets:Foo             10.00 EUR
            Assets:Bar
        """
        entries = list(filter_txns(entries))
        self.assertEqual(has_narration(r('^Test$'), entries[0]), True)
        self.assertEqual(has_narration(r('Foo'), entries[0]), False)
        self.assertEqual(has_narration(r('^$'), entries[1]), True)
        self.assertEqual(has_narration(r('Foo'), entries[1]), False)
        self.assertEqual(has_narration(r('^$'), entries[2]), True)
        self.assertEqual(has_narration(r('Foo'), entries[2]), False)


class TestHasPayee(unittest.TestCase):
    """Test has_payee()"""

    @loader.load_doc()
    def test_has_payee(self, entries, _, __):
        """
        2020-02-14 open Assets:Foo
        2020-02-14 open Assets:Bar
        2020-02-14 * "No payee"
            Assets:Foo             10.00 EUR
            Assets:Bar
        2020-02-14 * "Has payee" "Test"
            Assets:Foo             10.00 EUR
            Assets:Bar
        """
        entries = list(filter_txns(entries))
        self.assertEqual(has_payee(entries[0]), False)
        self.assertEqual(has_payee(entries[1]), True)


class TestHasTag(unittest.TestCase):
    """Test has_tag()"""

    @loader.load_doc()
    def test_has_tag(self, entries, _, __):
        """
        2020-02-14 open Assets:Foo
        2020-02-14 open Assets:Bar
        2020-02-14 * "Has tag"
            #test
            Assets:Foo             10.00 EUR
            Assets:Bar
        2020-02-14 * "Missing tag"
            Assets:Foo             10.00 EUR
            Assets:Bar
        2020-02-14 * "Test fake tags"
            Assets:Foo             10.00 EUR
              tags: "a,b,c"
            Assets:Bar
        """
        entries = list(filter_txns(entries))
        self.assertEqual(has_tag('test', entries[0]), True)
        self.assertEqual(has_tag('notest', entries[0]), False)
        self.assertEqual(has_tag('test', entries[1]), False)
        self.assertEqual(has_tag('b', entries[2]), True)
        self.assertEqual(has_tag('x', entries[2]), False)


class TestMetadataValueEq(unittest.TestCase):
    """Test metadata_value_eq()"""

    @loader.load_doc()
    def test_metadata_value_eq(self, entries, _, __):
        """
        2020-02-14 open Assets:Foo
        2020-02-14 open Assets:Bar
        2020-02-14 * "Metadata"
            foo: "bar"
            Assets:Foo             10.00 EUR
            Assets:Bar
        """
        entries = list(filter_txns(entries))
        self.assertEqual(metadata_value_eq('foo', 'bar', entries[0]), True)
        self.assertEqual(metadata_value_eq('foo', 'baz', entries[0]), False)
        self.assertEqual(metadata_value_eq('bar', 'baz', entries[0]), False)


class TestMetadataValueIn(unittest.TestCase):
    """Test metadata_value_in()"""

    @loader.load_doc()
    def test_metadata_value_in(self, entries, _, __):
        """
        2020-02-14 open Assets:Foo
        2020-02-14 open Assets:Bar
        2020-02-14 * "Metadata"
            foo: "bar"
            Assets:Foo             10.00 EUR
            Assets:Bar
        """
        entries = list(filter_txns(entries))
        self.assertEqual(metadata_value_in('foo', ['bar'], entries[0]), True)
        self.assertEqual(metadata_value_in('foo', ('bar'), entries[0]), True)
        self.assertEqual(metadata_value_in('foo', ['bar'], entries[0]), True)
        self.assertEqual(metadata_value_in('foo', ('bar'), entries[0]), True)
        self.assertEqual(metadata_value_in('foo', ['baz'], entries[0]), False)
        self.assertEqual(metadata_value_in('bar', ['baz'], entries[0]), False)


if __name__ == '__main__':
    unittest.main()
