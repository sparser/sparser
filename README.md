Sparser is string parsing and regular expressions for humans
====================================
Parsing strings can be a surprisingly difficult task. This difficulty
multiplies when dealing with multiline strings. Traditionally, regular
expressions were used for this. As anyone who has worked with regular
expressions knows, however, they are difficult to read, difficult to
maintain, full of gotchas, and don't scale well over multiple lines.
Sparser was developed to handle this problem.

    >>> import sparser as sp
    >>> pattern = "Hello {{str}}!"
    >>> string = "Hello World!"
    >>> r = sp.match(pattern, string)
    >>> print r
    True

    >>> pattern = "Hello {{str planet}}!"
    >>> string = "Hello World!"
    >>> r = sp.match(pattern, string)
    >>> print r
    True

    >>> pattern = "Hello {{str planet}}!"
    >>> string = "Hello World!"
    >>> r = sp.parse(pattern, string)
    >>> print r
    {'planet': 'World'}

Syntax-wise, Sparser is a mashup of [regular expressions](https://docs.python.org/2/library/re.html)
and [Handlebars](https://github.com/wycats/handlebars.js/)-style templating. A more precise tag-line
might be, *Sparser is a reverse-templating language for matching and parsing strings*

    >>> pattern = "The {{spstr rocket}} {{str}} off at {{int hour}}:{{int minute}}" \
                  "and costs {{currency price}}."
    >>> compiled = sp.compile(pattern)
    >>> print compiled.parse("The Falcon 9 blasts off at 5:30 and costs $62,000,000.")
    {'rocket': 'Falcon 9',
     'hour': 5,
     'minute': 30,
     'price': 62000000
    }


Table of Contents
=================
1. [Examples](#examples)
2. [Installation](#installation)
3. [Documentation](#documentation)
    1. [Method reference](#method-reference)
    2. [Pattern behaviour](#pattern-behavior)
    3. [Tags](#tags)
    4. [Built-in types](#built-in-types)
    5. [Custom types](#custom-types)
4. [TODO](#todo)
5. [Similar projects](#similar-projects)
6. [Bugs](#bugs)


Examples
========

Sparser has a basic set of built-in types like `str`, `float`, and `currency`.
If this isn't enough, you can also pass `custom types` into the compile method

    >>> patt = "The {{str}} {{animal who}} was {{str action}} {{spstr food}}" \
               "on the {{int date}}rd of {{str month}}"
    >>> custom_types = {"animal": ("cat|dog|pig", None)}
    >>> compiled = sp.compile(patt, custom_types)
    >>> print compiled.parse("The handsome cat was slurping pho on the 23rd of July")
    {'who': 'cat',
     'action': 'slurping',
     'food': 'pho',
     'date': 23,
     'month': 'July'}

The first argument in the `custom types` tuple is the regex to match. The second
is a callback method. Use it if you want to clean the output.

    >>> custom_types = {"animal": ("cat|dog|pig", str.upper)}
    >>> compiled = sp.compile(patt, custom_types)
    >>> print compiled.parse("The handsome cat was slurping pho on the 23rd of July")
    {'who': 'CAT',
     'action': 'slurping',
     'food': 'pho',
     'date': 23,
     'month': 'July'}

For simple one-offs, use inline `lambda types`

    >>> patt = "The {{str}} {{"cat|dog|pig" who}} was {{str action}} {{spstr food}}" \
               "on the {{int date}}{{"st|nd|rd|th"}} of {{str month}}"
    >>> compiled = sp.compile(patt)
    >>> print compiled.parse("The handsome cat was slurping pho on the 23rd of July")
    {'who': 'cat,
     'action': 'slurping',
     'food': 'pho',
     'date': 23,
     'month': 'July'}

Loops are one of the most power features of Sparser. They are great
for lighly formatted tables

    >>> patt = """\
        {*loop imdb_list*}
            {*case*}{{int rank}}. {{spstr title}} ({{int year}}) +{{float rating}}{*endcase*}
        {*endloop*}"""
    >>> compiled = sp.compile(patt)
    >>> imdb_top_250 = """
    1. The Shawshank Redemption (1994)  9.2
    2. The Godfather (1972) 9.2
    3. The Godfather: Part II (1974)    9.0
    4. The Dark Knight (2008)   8.9"""
    >>> print compiled.parse(imbd_top_250)
    {"imdb_list": [
      {"rating": 9.2, "year": 1994, "rank": 1, "title": "The Shawshank Redemption"},
      {"rating": 9.2, "year": 1972, "rank": 2, "title": "The Godfather"},
      {"rating": 9.0, "year": 1974, "rank": 3, "title": "The Godfather: Part II"},
      {"rating": 8.9, "year": 2008, "rank": 4, "title": "The Dark Knight"}
    ]}

Loops can have multiple cases which can either be named or unnamed

    >>> patt = """\
        {*loop line_items*}
            {*case header*}{{spalpha name}}{*endcase*}
            {*case line_item*} {{spalpha name}} {{currency price}}{*endcase*}
            {*case total*} Total {{spalpha name}}: {{currency price}}{*endcase*}
            {*case break*}{*endcase*}
        {*endloop*}
        Net income {{currency net_income}}"""
    >>> compiled = sp.compile(patt)
    >>> income_statement = """\
        Revenues
         Merchandise sales     $30
         Other revenues        $8
         Total Revenues:            $38

        Expenses
         Cost of goods sold    $15
         Depreciation          $3
         Wages                 $30
         Total Expenses:            $28

        Net income                - $10"""
    >>> print compiled.parse(income_statement)
    {"line_items": [
      {"case": "header", "name": "Revenues"},
      {"case": "line_item", "price": 30.0, "name": "Merchandise sales"},
      {"case": "line_item", "price": 8.0, "name": "Other revenues"},
      {"case": "total", "price": 38.0, "name": "Revenues"},
      {"case": "break"},
      {"case": "header", "name": "Expenses"},
      {"case": "line_item", "price": 15.0, "name": "Cost of goods sold"},
      {"case": "line_item", "price": 3.0, "name": "Depreciation"},
      {"case": "line_item", "price": 30.0, "name": "Wages"},
      {"case": "total", "price": 28.0, "name": "Expenses"},
      {"case": "break"}],
     "net_income": -10.0}


Similar to loops are switch statements. These can be used for simple
multi-option matches

    >>> patt = """\
        The Patriots are {*switch statement*}
            {*case fact*}an NFL team{*endcase*}
            {*case opinion*}overrated{*endcase*}
            {*case telling_it_like_it_is*}ball deflaters and serial cheaters{*endcase*}
        {*endswitch*}."""
    >>> compiled = sp.compile(patt)
    >>> string = "The Patriots are ball deflaters and serial cheaters."
    >>> print compiled.parse(string)
    {"statement": {"case": "telling_it_like_it_is"}}

You can use the {\*include <what>\*} statement to embed patterns in patterns.
This works on a preprocessor level (like #define from C) so it is
equivalent to copying and pasting. This is useful for reusing common
patterns or just breaking up and organizing longer ones.

    >>> patt = """
        {*loop logs*}
            {*case*}{*include iso8601*}: {{spstr error}}{*endcase*}
            {*case*}{{spstr error}}: {*include iso8601*}{*endcase*}
        {*endloop*}
        """
    >>> iso8601 = """{{int year}}-{{int month}}-{{int day}}T{{int hour}}:{{int minute}}:{{float second}}"""
    >>> logs = """
        AssertionError: 2017-03-04T21:40:43.408923
        ZeroDivisionError: 2017-03-04T21:49:20.932833
        2017-03-04T21:52:03.987341: TypeError
        """
    >>> compiled = sp.compile(patt, includes={"iso8601": iso8601})
    >>> print compiled.parse(logs)
    {'logs': [
      {'error': 'AssertionError',
       'day': 4,
       'hour': 21,
       'minute': 40,
       'month': 3,
       'second': 43.408923,
       'year': 2017},
      {'error': 'ZeroDivisionError',
       'day': 4,
       'hour': 21,
       'minute': 49,
       'month': 3,
       'second': 20.932833,
       'year': 2017},
      {'error': 'TypeError',
       'day': 4,
       'hour': 21,
       'minute': 52,
       'month': 3,
       'second': 3.987341,
       'year': 2017}
    ]}

Unfortunately, Sparser does not support nesting switches and loops in v0.1. This might
be updated in future versions


Installation
============

    $ pip install sparser

Sparser has no dependencies and is supported in both Python 2 & 3. I have no
idea how Windows users install Python packages but Google can help you.


Documentation
=============

Method reference
----------------
**sparser.parse**(pattern, string[, custom_types[, includes]])

<p>Given a pattern and a string, parse the string and return a dictionary.
If the string does not match the pattern, a SparserValueError exception
is raised. Optionally, use custom_types ({type_name: (type_pattern, callback)} format)
and/or includes ({include_name: pattern})</p>

**sparser.match**(pattern, string[, custom_types[, includes]])

<p>The same as parse except instead of returning a dictionary, return True if the
pattern successfully matched the string. Internally, this works the same as
sparser.parse but is useful when you just need to know whether something matched
and don't want to deal with error handling or falsy, empty dictionaries.</p>

**sparser.compile**((pattern[, custom_types[, includes]])

<p>Pre-compile a pattern and return a SparserObject which you can later call parse/match
on. This is useful if speed is essential or simply as a way to keep your code clean.</p>

**SparserObject.parse**(string[, custom_types[, includes]])

<p>Same as sparser.parse but pre-compiled using the sparser.compile method</p>

**SparserObject.match**(string[, custom_types[, includes]])

<p>Same as sparser.match but pre-compiled using the sparser.compile method</p>


Pattern behavior
----------------
#### Matching to the end of input
Sparser expects a perfect match and doesn't do partial matching. What this
means is that this works

    >>> print sp.parse("Hello {{alpha planet}}, nice to meet you", "Hello world, nice to meet you")
    {'planet': 'world'}

But these will raise SparserValueErrors

    >>> print sp.parse("Hello {{alpha planet}}", "Hello world, nice to meet you")
    SparserValueError
    >>> print sp.parse("Hello {{alpha planet}}, nice to meet you", "Hello world")
    SparserValueError
    >>> print sp.parse("{{alpha planet}}", "Hello world")
    SparserValueError

To get around this, you can use a `{{spstr}}` tag before or after your pattern
like this

    >>> print sp.parse("Hello {{alpha planet}}{{spstr}}", "Hello world, nice to meet you")
    {'planet': 'world'}
    >>> print sp.parse("Hello {{alpha planet}}{{spstr}}", "Hello world")
    {'planet': 'world'}
    >>> print sp.parse("{{spstr}} Hello {{alpha planet}}", "blah blah Hello world")
    {'planet': 'world'}

`spstr` is a built-in type that stands for "spaced string". This is equivalent
to the regex `.+` meaning "any character 1+ times".


#### Un-matched cases
When Sparser is in a switch/loop, and there are multiple cases,
it will return the first case to match the input. If no cases match within the
switch/loop, it will raise a SparserValueError


#### Corraling loops and switches
Loops and switches greedily match everything until the pattern immediately after
the block or the end of the string. So, if you have a table like this

    Winners
    1. Peach
    2. Yoshi
    3. Luigi
    Play again?

The pattern below will raise a SparserValueError because it is going to try to
match `Play again?` in the loop.

    Winners
    {*loop ranked_players*}
        {*case*}{{int rank}}. {{str name}}{*endcase*}
    {*endloop*}

Instead, be sure to include the last line after the endloop

    Winners
    {*loop ranked_players*}
        {*case*}{{int rank}}. {{str name}}{*endcase*}
    {*endloop*}
    Play again?

Or, a `{{spstr}}` works in a pinch

    Winners
    {*loop ranked_players*}
        {*case*}{{int rank}}\. {{str name}}{*endcase*}
    {*endloop*}
    {{spstr}}


#### Loops and newlines
Loops are designed to handle table-like strings so newlines are implied in
loop-matching. Multiline-loops are supported but inline loops are not.
Sparser should support inline loops in version 0.2. In the
meantime, you can use the regex bar (`|`) operator in custom or lambda
types.


#### The number of spaces and newlines doesn't matter
Sparser is designed to make no distinction between single spaces and
multiple spaces (just like HTML). This means

    >>> sp.match("The moon", "The     moon")
    True

And

    >>> sp.match("The     sun", "The sun")
    True

But

    >>> sp.match("The     sun", "Thesun")
    False

The same is true for `\n` newlines. This is not without precedent. HTML
rendering works in the same way. This was done because of the unique
challenges in parsing multi-line regular expressions.


Tags
----
For the moment, there are only eight tags in Sparser

| Tag                            | Notes
| ------------------------------ | -----------------------------------------------------------------------
| {{<var_type> <var_name>}}      | var_name is optional
| {\*switch <switch_name>\*}     | can only contain {\*case\*} tags as direct decendents
| {\*endswitch\*}                |
| {\*loop <loop_name>\*}         | can only contain {\*case\*} tags as direct decendents
| {\*endloop\*}                  |
| {\*case <case_name>\*}         | case_name is optional
| {\*endcase\*}                  |
| {\*include <include_name>\*}   | this just inserts one pattern into another. Think of it like C's `#define` macro


Built-in types
---------------

These types can be used in any variable tag

| Type           | Description                                       | Python Regex Pattern
| -------------- | ------------------------------------------------- | --------
| str            | a string with no spaces                           | "\S+"
| spstr          | a string with spaces allowed                      | ".+"
| int            | an integer. Won't accept decimals                 | "-? ?[0-9,]+"
| float          | a float                                           | "-? ?[0-9,.]+"
| alpha          | a string without digits, special chars, or spaces | "[a-zA-Z]+"
| spalpha        | a string without digits or special chars          | "[a-zA-Z ]+"
| alphanumeric   | a string without special chars or spaces          | "[a-zA-Z0-9_]+"
| spalphanumeric | a string without special chars                    | "[a-zA-Z0-9_ ]+"
| currency       | a float which might be prefixed with '$' and/or - | "-? ?[$-]*[0-9,.]+"


Custom types
------------
Custom types are optional parameters. They take the form of

    {type_name: (regex_pattern, callback), ...}

Callback is a function to modify the extracted string before inclusion in the
dictionary. For example, to uppercase the match, do

    lambda float_str: float_str.upper()
    # str.upper also works

If you wanted to add a custom date type, you could do something like

    date_cb = lambda dt_str: date.strptime(st_str, "%m/%d/%Y")
    custom_types = {"date": ("\d{2}/\d{2}/\d{4}", date_cb)}

If you just want to return the un-modified string, pass in `None`

    custom_types = {"berry": ("(?:blue|black|rasp)berry" , None)}


TODO
======
- Nested loops (will need to rewrite major parts as a finite state machine)
- Inline loops (If a loop is not adjacent to \n on both sides, we should not automatically newline it)
- Cleanup the building of the AST
- Add unicode-compatible currency (euros, yen, etc.)
- Tests should use assertRaisesRegexp and match to exactly which exception was raised
- built-in date types
- .search for un-strict matching


Similar projects
================
- [parse](https://pypi.python.org/pypi/parse)
- [pyParsing](http://pyparsing.wikispaces.com/)


Bugs
===========
This is version 0.1 and there is liable to be a bug or two that we missed. Please
let us know or submit a patch.


