#!/usr/bin/env python

from __future__ import print_function
from __future__ import absolute_import

import json
import re
import sys

from sparser_exceptions import SparserValueError, SparserSyntaxError, SparserUnexpectedError

if sys.version_info[0] > 2:
    # python 3
    # this is needed because custom-type callbacks can use old-style types and we need to ensure that our types
    # are compatible
    from builtins import zip
    from builtins import str
    from builtins import object


MATCHING_GROUP_RE = re.compile("\(([^\?][^:].*?)\)")
QUOTE_HUGGED_STRING = re.compile("^('.*?'|\".*?\")$")


def _floatify(raw):
    """
    :param str raw:
    :rtype: float
    """
    try:
        return float(re.sub('[^\w.-]', '', raw))
    except ValueError:
        raise SparserValueError('Could not perform sparser float on "%s"' % raw)


def _intify(raw):
    """
    :param str raw:
    :rtype: int
    """
    try:
        return int(re.sub('[^\w.-]', '', raw))
    except ValueError:
        raise SparserValueError('Could not perform sparser int on "%s"' % raw)


BUILT_IN_TYPE_MAP = {
    "int": ("-? ?[0-9,]+", _intify),
    "float": ("-? ?[0-9,.]+", _floatify),
    "currency": ("-? ?[$-]*[0-9,.]+", _floatify),
    "str": ("\S+", str.strip),
    "spstr": (".*", str.strip),
    "alpha": ("[a-zA-Z]+", str.strip),
    "spalpha": ("[a-zA-Z ]+", str.strip),
    "alphanum": ("[a-zA-Z0-9_]+", str.strip),
    "spalphanum": ("[a-zA-Z0-9_ ]+", str.strip),
}


class TOKEN(object):
    def __init__(self, content):
        self.content = content

    def group(self, idx):
        return re.match(self.patt, self.content).group(idx)


class OPENLOOP(TOKEN):
    patt = "{\* *loop +(\w+) *\*}"

    def __repr__(self):
        return "<OPENLOOP %r>" % self.content


class CLOSELOOP(TOKEN):
    patt = "{\* *endloop *\*}"

    def __repr__(self):
        return "<CLOSELOOP %r>" % self.content


class OPENSWITCH(TOKEN):
    patt = "{\* *switch +(\w+) *\*}"

    def __repr__(self):
        return "<OPENSWITCH %r>" % self.content


class CLOSESWITCH(TOKEN):
    patt = "{\* *endswitch *\*}"

    def __repr__(self):
        return "<CLOSESWITCH %r>" % self.content


class OPENCASE(TOKEN):
    patt = "{\* *case( +\w+)? *\*}"

    def __repr__(self):
        return "<OPENCASE %r>" % self.content


class CLOSECASE(TOKEN):
    patt = "{\* *endcase *\*}"

    def __repr__(self):
        return "<CLOSECASE %r>" % self.content


class INCLUDE(TOKEN):
    patt = "{\* *include +(\w+) *\*}"

    def __repr__(self):
        return "<INCLUDE %r>" % self.content


class VAR(TOKEN):
    patt = "{{ *(\w+|'.+?'|\".+?\")(?: +(\w+))? *}}"

    def __repr__(self):
        return "<VAR %s>" % self.content


class TEXT(TOKEN):
    def __repr__(self):
        return "<TEXT %r>" % self.content


OP_TOKENS = (OPENLOOP, CLOSELOOP, VAR, OPENCASE, CLOSECASE, OPENSWITCH, CLOSESWITCH, INCLUDE)


def _switch_tokens(raw_token):
    """
    :param str
    :rtype: TOKEN
    """
    for TokenCls in OP_TOKENS:
        if re.match(TokenCls.patt, raw_token):
            return TokenCls(raw_token)
    hint = ''
    if raw_token == "{*loop*}":
        hint = " (loop name required)"
    if raw_token == "{*switch*}":
        hint = " (switch name required)"
    raise SparserSyntaxError("could not parse token %r%s" % (raw_token, hint))


def _preprocess(tokens, includes_dict):
    """
    Replaces {*include*} tokens with what they are supposed to include

    :param [TOKEN, ...] tokens:
    :param {include_name: include_pattern, ...} includes_dict:
    :rtype: [TOKEN, ...]
    """
    while True:
        for i, token in enumerate(tokens):
            if isinstance(token, INCLUDE):
                template_name = token.group(1)
                if template_name not in includes_dict:
                    raise SparserValueError("Includes template %r not provided" % template_name)
                include_patt = includes_dict[template_name]
                del includes_dict[template_name]
                tokens = tokens[:i] + _tokenize(include_patt, includes_dict) + tokens[i+1:]
                break
        else:
            break
    return tokens


def _tokenize(raw, includes_dict):
    """
    :param str raw:
    :param {include_name: include_pattern, ...} includes_dict:
    :rtype: [TOKEN, ...]
    """
    includes_dict = includes_dict or {}

    remaining = raw
    tokens = []
    while True:
        match = re.match("^(.*?)({{.*?}}|{\*.*?\*})(.*?)\Z", remaining,
                         re.DOTALL | re.MULTILINE)
        if not match:
            break
        tokens.append(TEXT(match.group(1)))
        tokens.append(_switch_tokens(match.group(2)))
        remaining = match.group(3)
    tokens.append(TEXT(remaining))
    tokens = _preprocess(tokens, includes_dict)
    return tokens


def _root_tokenize(raw, includes_dict=None):
    """
    Tokenize but also merge together adjacent TEXT tokens. These are remnants of the {\*include\*} process
    :param str raw:
    :param {include_name: include_pattern, ...} includes_dict:
    :rtype: [TOKEN, ...]
    """
    tokens = _tokenize(raw, includes_dict)

    ret_tokens = []
    for token in tokens:
        if ret_tokens and isinstance(token, TEXT) and isinstance(ret_tokens[-1], TEXT):
            ret_tokens[-1].content += token.content
        else:
            ret_tokens.append(token)
    return ret_tokens


class DictEntry(object):
    def __init__(self, name, cb):
        self.name = name
        self.cb = cb


class SIS(object):
    # SparserIntermediateSymbol
    def __init__(self, tokens, ctx):
        """
        :param [TOKEN, ...] tokens:
        :param SparserCompilationContext ctx:
        """
        raise NotImplementedError


class Dict(SIS):
    # Text, Var, Loop are allowed
    def __init__(self, tokens, ctx):
        """
        :param [TOKEN, ...] tokens:
        :param SparserCompilationContext ctx:
        """
        all_members = []
        while tokens:
            token = tokens.pop(0)
            if isinstance(token, OPENLOOP):
                nested = 1
                loop_tokens = [token]
                while True:
                    token = tokens.pop(0)
                    loop_tokens.append(token)
                    if isinstance(token, OPENLOOP):
                        nested += 1
                    elif isinstance(token, CLOSELOOP):
                        nested -= 1
                        if nested == 0:
                            break
                    if not tokens:
                        raise SparserSyntaxError("{*loop*} not closed with a matching {*endloop*}")
                all_members.append(Loop(loop_tokens, ctx))
            elif isinstance(token, OPENSWITCH):
                nested = 1
                switch_tokens = [token]
                while True:
                    token = tokens.pop(0)
                    switch_tokens.append(token)
                    if isinstance(token, OPENSWITCH):
                        nested += 1
                    if isinstance(token, CLOSESWITCH):
                        nested -= 1
                        if nested == 0:
                            break
                    if not tokens:
                        raise SparserSyntaxError("{*switch*} not closed with a matching {*endswitch*}")
                all_members.append(Switch(switch_tokens, ctx))
            elif isinstance(token, VAR):
                all_members.append(Var([token], ctx))
            elif isinstance(token, TEXT):
                all_members.append(Text([token], ctx))
            else:
                raise SparserSyntaxError("Token %r cannot be here" % token)

        self._translate_members(all_members)

    def _translate_members(self, members):
        """
        :param [SIS, ...] members:
        :rtype: str, [DictEntry, ...]
        """
        self.translated = ''
        self.d_entries = []
        for member in members:
            patt, name, cb = member.translate()
            self.translated += patt
            if name is not None:
                self.d_entries.append(DictEntry(name, cb))
        self.translated += "$"

    def parse(self, string, do_error=True):
        """
        :param str string: the string captured within the dict
        :rtype: {var_name: var_val}
        """
        match = re.match(self.translated, string, re.DOTALL)
        if not match:
            if not do_error:
                return None
            # separate by loops so that we can point closer to the place that doesn't work
            for section in self.translated.split('(?P<.*?>.*?)'):
                if not re.search(section, string, re.DOTALL):
                    raise SparserValueError("%r is unmatched for string %r" % (section, string))
            raise SparserUnexpectedError("Unexpected error finding where the string doesn't match")

        ret = {}
        for sub_match, d_entry in zip(match.groups(), self.d_entries):
            try:
                ret[d_entry.name] = d_entry.cb(sub_match)
            except TypeError:
                ret[d_entry.name] = d_entry.cb(unicode(sub_match))

        return ret


class Case(SIS):
    def __init__(self, tokens, ctx):
        """
        :param [TOKEN, ...] token:
        :param SparserCompilationContext ctx:
        """
        match = re.search(tokens[0].patt, tokens[0].content)
        if match and match.group(1) is not None:
            self.var_name = match.group(1).strip()
        else:
            self.var_name = None
        self.dict = Dict(tokens[1:-1], ctx)

    def parse(self, entry):
        """
        :param str entry:
        :rtype: {var_name: var_val, ...}
        """
        ret = self.dict.parse(entry, do_error=False)
        if ret is not None and self.var_name is not None:
            ret["case"] = self.var_name
        return ret


class Loop(SIS):
    def __init__(self, tokens, ctx):
        """
        :param [TOKEN, ...] token:
        :param SparserCompilationContext ctx:
        """
        assert isinstance(tokens[0], OPENLOOP)
        assert isinstance(tokens[-1], CLOSELOOP)
        self.loop_name = tokens[0].content[2:-2].split(' ')[1]
        tokens = tokens[1:-1]  # pop off LOOPSTART LOOPEND
        self.cases = []
        while tokens:
            token = tokens.pop(0)
            if isinstance(token, OPENCASE):
                nested = 1
                case_tokens = [token]
                while True:
                    token = tokens.pop(0)
                    case_tokens.append(token)
                    if isinstance(token, OPENCASE):
                        nested += 1
                    if isinstance(token, CLOSECASE):
                        nested -= 1
                        if nested == 0:
                            break
                    if not tokens:
                        raise SparserSyntaxError("{*case*} not closed with a matching {*endcase*}")
                self.cases.append(Case(case_tokens, ctx))
            elif isinstance(token, TEXT):
                if token.content.strip():
                    raise SparserSyntaxError("{*loop*} tags can only contain {*case*}s")
            else:
                raise SparserSyntaxError("{*loop*} tags can only contain {*case*}s")
        if not self.cases:
            raise SparserSyntaxError("{*loop*} tags must contain at least one {*case*}")

    def translate(self):
        """
        :rtype: (str regex, str loop_name, func cb)
        """
        return "(?P<%s>.*)" % self.loop_name, self.loop_name, self.cb

    def cb(self, string_input):
        """
        :param str string_input: the string captured within the loop
        :rtype: [{var_name: var_val, ...}, ...]
        """
        string_lines = re.split("\n|\r\n|\r", string_input)
        if not [l for l in string_lines if l]:
            return []

        ret = []
        for line in string_lines:
            for case_obj in self.cases:
                parsed_case = case_obj.parse(line)
                if parsed_case is not None:
                    ret.append(parsed_case)
                    break
            else:
                err_msg = '%r unmatched for loop %r: [' % (line, self.loop_name)
                err_msg += ', '.join("%r" % case_obj.dict.translated for case_obj in self.cases)
                err_msg += ']'
                raise SparserValueError(err_msg)
        return ret


class Switch(SIS):
    def __init__(self, tokens, ctx):
        """
        :param [TOKEN, ...] token:
        :param SparserCompilationContext ctx:
        """
        assert isinstance(tokens[0], OPENSWITCH)
        assert isinstance(tokens[-1], CLOSESWITCH)
        self.switch_name = tokens[0].content[2:-2].split(' ')[1]
        tokens = tokens[1:-1]  # pop off LOOPSTART LOOPEND
        self.cases = []
        while tokens:
            token = tokens.pop(0)
            if isinstance(token, OPENCASE):
                nested = 1
                case_tokens = [token]
                while True:
                    token = tokens.pop(0)
                    case_tokens.append(token)
                    if isinstance(token, OPENCASE):
                        nested += 1
                    if isinstance(token, CLOSECASE):
                        nested -= 1
                        if not nested:
                            break
                    if not tokens:
                        raise SparserSyntaxError("{*case*} not closed with a matching {*endcase*}")
                self.cases.append(Case(case_tokens, ctx))
            elif isinstance(token, TEXT):
                if token.content.strip():
                    raise SparserSyntaxError("{*switch*} tags can only contain {*case*}s")
            else:
                raise SparserSyntaxError("{*switch*} tags can only contain {*case*}s")
        if not self.cases:
            raise SparserSyntaxError("{*switch*} tags must contain at least one {*case*}")

    def translate(self):
        """
        :rtype: (str regex, str switch_name, func cb)
        """
        return "(?P<%s>.*?)" % self.switch_name, self.switch_name, self.cb

    def cb(self, string_input):
        """
        :param str string_input: the string passed into the loop
        :rtype: [{var_name: var_val, ...}, ...]
        """
        for case_obj in self.cases:
            parsed_case = case_obj.parse(string_input)
            if parsed_case is not None:
                return parsed_case

        err_msg = '%r unmatched for switch %r: [' % (string_input, self.switch_name)
        err_msg += ', '.join("%r" % case_obj.dict.translated for case_obj in self.cases)
        err_msg += ']'
        raise SparserValueError(err_msg)


class Text(SIS):
    def __init__(self, tokens, ctx):
        """
        "    " -> " +"
        "\n\n\n" -> "\n+"
        :param [TOKEN, ...] tokens:
        :param SparserCompilationContext ctx:
        """
        assert len(tokens) == 1
        self.patt = tokens[0].content
        self.patt = re.sub(' +', ' ', self.patt)
        self.patt = re.sub('\n+', '\n', self.patt)
        self.patt = re.sub('\n $', '\n', self.patt)
        self.patt = re.sub('^ \n', '\n', self.patt)
        self.patt = re.escape(self.patt)
        self.patt = re.sub('\\\n\\\ ', '\n *', self.patt)
        self.patt = re.sub('[^\n] ', ' +', self.patt)
        self.patt = re.sub('^\\\\\n', '\n*', self.patt)
        self.patt = re.sub('\\\\\n$', '\n*', self.patt)
        self.patt = re.sub('(.)\\\\\n(.)', lambda x: x.group(1) + '\n+' + x.group(2), self.patt)
        print(self.patt)


    def translate(self):
        """
        :rtype: (str regex, str var_name=None, func cb=None)
        """
        return self.patt, None, None


class Var(SIS):
    def __init__(self, tokens, ctx):
        """
        :param [TOKEN, ...] tokens:
        :param SparserCompilationContext ctx:
        """
        assert len(tokens) == 1
        elements = tokens[0].content[2:-2].split(' ')
        if len(elements) == 2:
            var_type, self.var_name = elements
        elif len(elements) == 1:
            var_type = elements[0]
            self.var_name = None
        else:
            raise SparserUnexpectedError("Unexpected error: Variables should be one or two elements.")

        if var_type in ctx.type_map:
            re_patt, self.cb = ctx.type_map[var_type]
        elif QUOTE_HUGGED_STRING.match(var_type):
            re_patt = var_type[1:-1]
            _assert_no_group_syntax(re_patt)
            re_patt = "(?:" + re_patt + ")"
            self.cb = None
        else:
            supported = json.dumps(list(ctx.type_map.keys()))
            raise SparserSyntaxError("%s not a known type (%r supported)" % (var_type, supported))

        if self.cb is None:
            self.cb = lambda x: x

        if self.var_name is not None:
            self.patt = "(?P<%s>%s)" % (self.var_name, re_patt)
        else:
            self.patt = re_patt

    def translate(self):
        """
        :rtype: (str regex, str var_name, func cb)
        """
        return self.patt, self.var_name, self.cb


class SparserCompilationContext(object):
    def __init__(self, custom_types):
        """
        :param {type_name: (regex, cb)} custom_types:
        """
        if custom_types is not None:
            for type_name, (pattern, cb) in custom_types.items():
                _assert_no_group_syntax(pattern)

            self.type_map = dict(list(BUILT_IN_TYPE_MAP.items()))
            self.type_map.update(custom_types)
        else:
            self.type_map = BUILT_IN_TYPE_MAP


class SparserCompiledObject(object):
    """
    This is just for the sake of a nicer interface object
    """
    def __init__(self, tokens, custom_types):
        """
        :param [TOKEN, ...] tokens:
        :param {type_name: (regex, cb)} custom_types:
        """
        ctx = SparserCompilationContext(custom_types)
        self.dict = Dict(tokens, ctx)

    def parse(self, string):
        """
        :param str string:
        :rtype: dict
        """
        return self.dict.parse(str(string))

    def match(self, string):
        """
        :param str string:
        :rtype: bool
        """
        try:
            self.parse(string)
            return True
        except SparserValueError:
            return False


def _assert_no_group_syntax(patt):
    """
    :param str patt:
    """
    if MATCHING_GROUP_RE.search(patt):
        raise SparserSyntaxError("Matching groups are not allowed in custom types. Use (?: ) style non-matching groups")


def compile(patt, custom_types=None, includes=None):
    """
    Compile a sparser pattern, returning a SparserCompiledObject

    :param str patt:
    :param {type_name: (regex, cb)} custom_types:
    :param {include_name: include_pattern, ...} includes:
    :rtype: SparserCompiledObject
    """
    tokens = _root_tokenize(patt, includes_dict=includes)
    return SparserCompiledObject(tokens, custom_types)


def parse(pattern, string, custom_types=None, includes=None):
    """
    Try to match the pattern to the string, returning
    a dictionary of values pulled from the string.
    This raises a SparserValueError on no match

    :param str patt:
    :param str string:
    :param {type_name: (regex, cb)} custom_types:
    :param {include_name: include_pattern, ...} includes:
    :rtype: dict
    """
    compiled = compile(pattern, custom_types, includes)
    ret = compiled.parse(string)
    return ret


def match(pattern, string, custom_types=None, includes=None):
    """
    Try to match the pattern to the start of the
    string, returning True or False

    :param str pattern:
    :param str string:
    :param {type_name: (regex, cb)} custom_types:
    :rtype: bool
    """
    compiled = compile(pattern, custom_types, includes)
    return compiled.match(string)


def _main(args, out=sys.stdout):
    from argparse import ArgumentParser

    arg_parser = ArgumentParser(description='Sparser is regexes and string parsing for humans')

    pattern_group = arg_parser.add_mutually_exclusive_group(required=True)
    pattern_group.add_argument(
        '--pattern-string', dest="pattern_string",
        help='The sparser pattern as a string')
    pattern_group.add_argument(
        '--pattern-file', dest="pattern_file",
        help='The sparser pattern as a text file')

    input_group = arg_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--input-string', dest="input_string",
        help='The string to be matched against')
    input_group.add_argument(
        '--input-file', dest="input_file",
        help='The string to be matched against as a text file')

    args = arg_parser.parse_args(args)

    if args.pattern_string is not None:
        patt = args.pattern_string
    elif args.pattern_file is not None:
        with open(args.pattern_file) as f:
            patt = f.read()

    if args.input_string is not None:
        string = args.input_string
    elif args.input_file is not None:
        with open(args.input_file) as f:
            string = f.read()

    out.write(json.dumps(parse(patt, string)) + "\n")


if __name__ == "__main__":
    _main(sys.argv[1:])
