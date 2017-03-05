#!/usr/bin/env python

from __future__ import print_function
from builtins import zip
from builtins import str

import json
import re
import unittest
import sys
import difflib

if sys.version_info[0] > 2:
    from io import StringIO
else:
    from StringIO import StringIO

if __name__ == "__main__":
    sys.path.append('..')
    import sparser as sp
    from sparser_exceptions import SparserValueError, SparserSyntaxError, SparserError


exception_map = {
    "SparserValueError": SparserValueError,
    "SparserSyntaxError": SparserSyntaxError
}


class TestSparser(unittest.TestCase):
    def test_sparser(self):
        with open('tests.txt') as f:
            raw_tests = f.read()
        raw_tests = '\n'.join([l for l in raw_tests.splitlines() if not l.strip().startswith('#')])
        raw_tests = raw_tests.strip()
        raw_tests = raw_tests.split('\n\n\n\n')
        assert raw_tests  # assert that we actually loaded the file
        for raw_test in raw_tests:
            self._test_raw_test(raw_test)

    def _test_raw_test(self, raw_test):
        title = raw_test.split('\n')[0][2:]
        pattern = re.search("PATTERN\n(.*?)\n?STRING", raw_test, re.DOTALL).group(1)
        string = re.search("STRING\n(.*?)\n?(OUTPUT|RAISES)", raw_test, re.DOTALL).group(1)
        if "OUTPUT" in raw_test:
            try:
                output = json.loads(re.search("OUTPUT\n(.*?)$", raw_test, re.DOTALL).group(1))
            except ValueError:
                raise Exception("Problem loading json for test %r" % title)
            try:
                real_output = sp.parse(pattern, string)
            except SparserError as e:
                print("Failure in %r" % title)
                raise e
            if output != real_output:
                raise Exception(title + ": " +
                                '\n'.join(l for l in difflib.unified_diff(
                                    json.dumps(output, sort_keys=True, indent=4).splitlines(),
                                    json.dumps(real_output, sort_keys=True, indent=4).splitlines())))
        elif "RAISES" in raw_test:
            what_to_raise = re.search("RAISES\n(.*?)$", raw_test, re.DOTALL).group(1)
            try:
                with self.assertRaises(exception_map[what_to_raise]):
                    print(sp.parse(pattern, string))
            except Exception as e:
                raise Exception("In %r, problem with assertRaises: %s" % (title, str(e)))
        else:
            raise Exception("Needs an OUTPUT or a RAISES")

    def test_output_tester(self):
        # just to make sure tests actually work
        test = "PATTERN"\
               "{{int num}}"\
               "STRING"\
               "This is not a number"\
               "OUTPUT"\
               "{\"num\": 5}"
        with self.assertRaises(Exception):
            self._test_raw_test(test)

    def test_raises_tester(self):
        test = "PATTERN"\
               "(.*?)"\
               "STRING"\
               "Invalid"\
               "RAISES"\
               "SparserSyntaxError"
        with self.assertRaises(Exception):
            self._test_raw_test(test)

    def test_valid_tester(self):
        test = "PATTERN"\
               "{{str the_str}}"\
               "STRING"\
               "Invalid"
        with self.assertRaises(Exception):
            self._test_raw_test(test)

    def test_tokenizer(self):
        # tests the workings of the tokenizer and also that the repr on the tokens works
        inp = "txt{{int v1}}{*loop a*}{*case*}txt{{str v2}}txt{*endcase*}" \
              "{*case b*}{*switch la*}{*case*}{*include abc*}{*endcase*}{*endswitch*}{*endcase*}{*endloop*}"
        tokens = sp._root_tokenize(inp, includes_dict={'abc': 'blah'})
        exp_order = [sp.TEXT, sp.VAR, sp.TEXT, sp.OPENLOOP, sp.TEXT, sp.OPENCASE, sp.TEXT, sp.VAR, sp.TEXT,
                     sp.CLOSECASE, sp.TEXT, sp.OPENCASE, sp.TEXT, sp.OPENSWITCH, sp.TEXT, sp.OPENCASE, sp.TEXT,
                     sp.CLOSECASE, sp.TEXT, sp.CLOSESWITCH, sp.TEXT, sp.CLOSECASE, sp.TEXT, sp.CLOSELOOP]
        for exp_cls, act_tok in zip(exp_order, tokens):
            if not isinstance(act_tok, exp_cls):
                raise AssertionError("Expecting %r. Received %r" % (exp_cls, act_tok))
            assert repr(act_tok)

    def test_cli(self):
        string_io = StringIO()
        sp._main(['--pattern-string', '"{{str what}} world"', '--input-string', '"hello world"'], string_io)
        ret = json.loads(string_io.getvalue())
        self.assertEqual(ret, {"what": "hello"})

        # TODO fake files
        # sp._main(['--pattern-string', '"{{str what}} world"', '--input-file', "<<<", '"hello world"'], string_io)
        # ret = json.loads(string_io.getvalue())
        # self.assertEqual(ret, {"what": "hello"})

        # sp._main(['--input-string', '"hello world"', '--pattern-file', '<<<', '"{{str what}} world"'], string_io)
        # ret = json.loads(string_io.getvalue())
        # self.assertEqual(ret, {"what": "hello"})

    def test_includes(self):
        patt = "{{str a1}} {*include sub_patt*} {{str a2}}"
        sub_patt = "b{{'[c]{5}' cs}}b"
        string = "a bcccccb a"
        self.assertEqual(
            sp.parse(patt, string, includes={"sub_patt": sub_patt}),
            {"a1": "a", "a2": "a", "cs": "ccccc"})
        with self.assertRaises(SparserValueError):
            sp.parse(patt, string)

    def test_match(self):
        patt = "Hello {{alpha where}}"
        good_string = "Hello world"
        bad_string = "Hello world. How are you?"
        self.assertTrue(sp.match(patt, good_string))
        self.assertFalse(sp.match(patt, bad_string))

    def test_custom_types(self):
        patt = "the {{animal who}} says {{str sound}}"
        custom_types = {"animal": ("(?:cat|dog|horse)", str.upper)}
        string = "the dog says bwak"
        self.assertEqual(
            sp.parse(patt, string, custom_types=custom_types),
            {"who": "DOG", "sound": "bwak"})

        # no matching groups allowed in custom types
        custom_types = {"animal": ("(cat|dog|horse)", str.upper)}
        with self.assertRaises(SparserSyntaxError):
            sp.parse(patt, string, custom_types=custom_types)


if __name__ == "__main__":
    unittest.main()
