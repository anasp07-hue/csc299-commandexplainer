"""Tests for splitting a typed command into command, flags, and arguments (SPEC.md §3.2)."""

from __future__ import annotations

import pytest

from commandexplain.parser import (
    Chain,
    ChainCommand,
    ParseError,
    Redirect,
    SplitArgs,
    chain_to_text,
    parse_chain,
    retype,
    split_flags,
    split_operators,
    tokenize,
)

LS_FLAGS = {"-l", "-a", "-h", "-R"}
FIND_FLAGS = {"-name", "-type", "-delete"}


# --- tokenize and single commands -----------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_blank_input_gives_none(text: str) -> None:
    """Blank input means there's nothing to explain."""
    assert parse_chain(text) is None


def test_command_and_args_are_separated() -> None:
    """The first word is the command, and the rest are its arguments."""
    assert parse_chain("ls -la docs") == Chain((ChainCommand(("ls", "-la", "docs")),))


def test_surrounding_whitespace_is_ignored() -> None:
    """Spaces and tabs around and between words don't matter."""
    assert parse_chain("   rm\t -rf   old  ") == Chain((ChainCommand(("rm", "-rf", "old")),))


def test_parser_keeps_command_case() -> None:
    """The parser keeps what was typed; lookup is what ignores case."""
    chain = parse_chain("LS -la")
    assert chain is not None and chain.commands[0].tokens[0] == "LS"


def test_quoted_text_stays_together() -> None:
    """Quotes keep a phrase as one argument, and the quotes themselves are removed."""
    assert tokenize('grep "hello world" notes.txt') == ["grep", "hello world", "notes.txt"]


def test_unclosed_quote_raises_parse_error() -> None:
    """An unclosed quote is reported as a ParseError with the UNCLOSED_QUOTE reason."""
    with pytest.raises(ParseError) as excinfo:
        parse_chain('echo "hi')
    assert excinfo.value.reason == ParseError.UNCLOSED_QUOTE


def test_trailing_backslash_has_its_own_reason() -> None:
    """A backslash at the very end is a different problem from a missing quote."""
    with pytest.raises(ParseError) as excinfo:
        parse_chain("echo hi\\")
    assert excinfo.value.reason == ParseError.TRAILING_BACKSLASH


def test_non_ascii_text_is_fine() -> None:
    """Non-English text passes through as an argument."""
    chain = parse_chain("echo héllo 日本")
    assert chain is not None and chain.commands[0].tokens[1:] == ("héllo", "日本")


# --- split_flags ----------------------------------------------------------


def test_grouped_short_flags_are_split() -> None:
    """-rf is two flags, in the order typed."""
    assert split_flags(["-rf"], {"-r", "-f"}).flags == ("-r", "-f")


def test_separate_flags_and_arguments() -> None:
    """Flags and plain arguments are sorted apart, keeping their order."""
    result = split_flags(["-l", "docs", "-a", "notes.txt"], LS_FLAGS)
    assert result.flags == ("-l", "-a")
    assert result.arguments == ("docs", "notes.txt")


def test_known_word_flag_is_kept_whole() -> None:
    """find's -name is one flag, not -n -a -m -e (ADR 0007)."""
    result = split_flags([".", "-name", "*.txt", "-delete"], FIND_FLAGS)
    assert result.flags == ("-name", "-delete")
    assert result.arguments == (".", "*.txt")


def test_unknown_group_is_split_even_if_flags_unknown() -> None:
    """An unknown group is still split, so each letter can be reported on its own."""
    assert split_flags(["-xyz"], LS_FLAGS).flags == ("-x", "-y", "-z")


def test_long_flag_is_one_flag() -> None:
    """--all is a single long flag."""
    assert split_flags(["--all"], LS_FLAGS).flags == ("--all",)


def test_long_flag_value_is_dropped() -> None:
    """--color=auto counts as the flag --color (ADR 0009)."""
    assert split_flags(["--color=auto"], LS_FLAGS).flags == ("--color",)


@pytest.mark.parametrize("token", ["-9", "-15", "-100"])
def test_numeric_flag_stays_whole(token: str) -> None:
    """-15 is one flag, not -1 and -5 (ADR 0009)."""
    assert split_flags([token, "123"], set()).flags == (token,)


def test_lone_dash_is_an_argument() -> None:
    """cd - means 'previous folder', so - is an argument, not a flag."""
    result = split_flags(["-"], set())
    assert result.flags == ()
    assert result.arguments == ("-",)


def test_double_dash_ends_flags() -> None:
    """Everything after -- is an argument, even if it starts with a dash."""
    result = split_flags(["-r", "--", "-weird-name", "-f"], {"-r", "-f"})
    assert result.flags == ("-r",)
    assert result.arguments == ("-weird-name", "-f")


def test_repeated_flags_listed_once() -> None:
    """-ll and -l -l both show -l once."""
    assert split_flags(["-ll", "-l", "-a"], LS_FLAGS).flags == ("-l", "-a")


def test_flags_are_case_sensitive() -> None:
    """-R and -r are different flags."""
    assert split_flags(["-Rr"], LS_FLAGS).flags == ("-R", "-r")


def test_plus_sign_is_an_argument() -> None:
    """chmod +x: the +x is an argument, not a flag."""
    result = split_flags(["+x", "script.sh"], {"-R"})
    assert result.flags == ()
    assert result.arguments == ("+x", "script.sh")


def test_no_args() -> None:
    """No words means no flags and no arguments."""
    result = split_flags([], LS_FLAGS)
    assert result.flags == ()
    assert result.arguments == ()


def test_parse_error_is_not_a_value_error() -> None:
    """ParseError must not be caught by 'except ValueError' meant for blank input."""
    assert not issubclass(ParseError, ValueError)


def test_non_breaking_spaces_count_as_spaces() -> None:
    """Commands copied from web pages often contain non-breaking spaces."""
    chain = parse_chain("rm\u00a0-rf\u202fold")
    assert chain is not None and chain.commands[0].tokens == ("rm", "-rf", "old")


def test_empty_command_name_raises_parse_error() -> None:
    """A quoted empty command name ('' -l) can't be explained."""
    with pytest.raises(ParseError, match="empty") as excinfo:
        parse_chain("'' -l")
    assert excinfo.value.reason == ParseError.EMPTY_COMMAND


def test_double_dash_with_value_is_an_argument() -> None:
    """--=x isn't a real flag, so it's treated as an argument."""
    result = split_flags(["--=x"], LS_FLAGS)
    assert result.flags == ()
    assert result.arguments == ("--=x",)


# --- Commands that run other commands (ADR 0010) --------------------------

SUDO_FLAGS = {"-u", "-i", "-k", "-l"}


def split_sudo(*args: str) -> SplitArgs:
    """Split words the way they are split for sudo."""
    return split_flags(
        args, SUDO_FLAGS | {"--user"}, runs_command=True, flags_with_values={"-u", "--user"}
    )


def test_wrapper_stops_flags_at_inner_command() -> None:
    """sudo rm -i x: -i belongs to rm, not sudo."""
    result = split_sudo("rm", "-i", "x")
    assert result.flags == ()
    assert result.arguments == ()
    assert result.inner == ("rm", "-i", "x")


def test_wrapper_keeps_its_own_flags() -> None:
    """sudo -k ls -l: -k is sudo's, and ls -l is the inner command."""
    result = split_sudo("-k", "ls", "-l")
    assert result.flags == ("-k",)
    assert result.inner == ("ls", "-l")


def test_wrapper_flag_value_is_not_the_inner_command() -> None:
    """sudo -u bob ls -l: bob is -u's value, and ls is the inner command."""
    result = split_sudo("-u", "bob", "ls", "-l")
    assert result.flags == ("-u",)
    assert result.arguments == ("bob",)
    assert result.inner == ("ls", "-l")


def test_wrapper_double_dash_starts_inner_command() -> None:
    """sudo -- rm -rf x: everything after -- is the inner command."""
    result = split_sudo("--", "rm", "-rf", "x")
    assert result.inner == ("rm", "-rf", "x")


def test_wrapper_with_no_inner_command() -> None:
    """sudo -l on its own has no inner command."""
    result = split_sudo("-l")
    assert result.flags == ("-l",)
    assert result.inner == ()


def test_non_wrapper_never_has_inner() -> None:
    """Ordinary commands never get an inner command."""
    assert split_flags(["rm", "-i"], SUDO_FLAGS).inner == ()


def test_wrapper_grouped_flags_give_value_to_last_flag() -> None:
    """sudo -iu bob ls: -u is last in the group, so bob is its value (ADR 0010)."""
    result = split_sudo("-iu", "bob", "ls")
    assert result.flags == ("-i", "-u")
    assert result.arguments == ("bob",)
    assert result.inner == ("ls",)


def test_value_given_with_equals_is_not_taken_twice() -> None:
    """sudo --user=bob ls: the value is already in the token, so ls is the inner command."""
    result = split_sudo("--user=bob", "ls")
    assert result.flags == ("--user",)
    assert result.arguments == ()
    assert result.inner == ("ls",)


@pytest.mark.parametrize("token", ["-INT", "-SIGKILL", "-xyz"])
def test_keep_flags_whole_never_splits(token: str) -> None:
    """With keep_flags_whole, unknown groups stay as one flag (ADR 0014)."""
    assert split_flags([token, "5"], {"-9"}, keep_flags_whole=True).flags == (token,)


# --- Chains (SPEC.md §3.2 steps 1-2, ADR 0019) ---------------------------


def test_pipe_splits_into_two_commands() -> None:
    """ls -a | grep txt is two commands joined by a pipe."""
    assert parse_chain("ls -a | grep txt") == Chain(
        (ChainCommand(("ls", "-a")), ChainCommand(("grep", "txt"))), ("|",)
    )


@pytest.mark.parametrize("joiner", ["|", "&&", "||", ";"])
def test_every_joiner(joiner: str) -> None:
    """Each joiner separates two commands, with or without spaces around it."""
    for text in (f"ls {joiner} wc", f"ls{joiner}wc"):
        chain = parse_chain(text)
        assert chain is not None
        assert [c.tokens for c in chain.commands] == [("ls",), ("wc",)]
        assert chain.joiners == (joiner,)


@pytest.mark.parametrize("text", ['grep "a|b" f', "grep 'a|b' f", "grep a\\|b f", 'echo "|"'])
def test_quoted_or_escaped_operators_are_not_operators(text: str) -> None:
    """AC 9: quoted or escaped pipes are part of an argument, not a pipe."""
    chain = parse_chain(text)
    assert chain is not None and chain.is_single


def test_redirect_target_is_a_file_not_a_command() -> None:
    """echo hi > out.txt: out.txt is the file, and echo is the only command."""
    chain = parse_chain("echo hi > out.txt")
    assert chain == Chain((ChainCommand(("echo", "hi"), (Redirect(">", "out.txt"),)),))
    assert not chain.is_single


def test_words_after_redirect_file_belong_to_the_command() -> None:
    """As in a real shell, sort > out.txt -r gives sort the -r."""
    chain = parse_chain("sort > out.txt -r")
    assert chain is not None
    assert chain.commands[0].tokens == ("sort", "-r")
    assert chain.commands[0].redirects == (Redirect(">", "out.txt"),)


def test_redirects_and_joiners_together() -> None:
    """cat < in.txt | sort >> out.txt keeps each redirect with its own command."""
    chain = parse_chain("cat < in.txt | sort >> out.txt")
    assert chain == Chain(
        (
            ChainCommand(("cat",), (Redirect("<", "in.txt"),)),
            ChainCommand(("sort",), (Redirect(">>", "out.txt"),)),
        ),
        ("|",),
    )


def test_trailing_semicolon_is_allowed() -> None:
    """ls; is a single command in a real shell."""
    chain = parse_chain("ls;")
    assert chain is not None and chain.is_single


@pytest.mark.parametrize(
    ("text", "reason", "detail"),
    [
        ("| grep x", ParseError.MISSING_BEFORE, "|"),
        ("&& ls", ParseError.MISSING_BEFORE, "&&"),
        ("> out.txt", ParseError.MISSING_BEFORE, ">"),
        ("ls &&", ParseError.MISSING_AFTER, "&&"),
        ("ls |", ParseError.MISSING_AFTER, "|"),
        ("ls | | wc", ParseError.MISSING_AFTER, "|"),
        ("ls >", ParseError.MISSING_AFTER, ">"),
        ("ls > | wc", ParseError.MISSING_AFTER, ">"),
    ],
)
def test_operator_with_a_missing_side(text: str, reason: str, detail: str) -> None:
    """An operator with nothing on one side is reported with which side and which operator."""
    with pytest.raises(ParseError) as excinfo:
        parse_chain(text)
    assert excinfo.value.reason == reason
    assert excinfo.value.detail == detail


@pytest.mark.parametrize(
    ("text", "syntax"),
    [
        ("sleep 5 &", "&"),
        ("ls 2>/dev/null", "2>"),
        ("ls 2> err.txt", "2>"),
        ("ls > out 2>&1", "2>"),
        ("ls &> out", "&>"),
        ("echo $(date)", "$("),
        ('echo "$(date)"', "$("),
        ("echo `date`", "`"),
        ("(cd x)", "("),
        ("cat << EOF", "<<"),
        ("ls |& wc", "|&"),
        ("ls # comment", "#"),
        ("ls -a #| grep x", "#"),
        ("ls;#x", "#"),
    ],
)
def test_unsupported_syntax_is_named(text: str, syntax: str) -> None:
    """Shell syntax this version doesn't explain raises UNSUPPORTED naming it (ADR 0019)."""
    with pytest.raises(ParseError) as excinfo:
        parse_chain(text)
    assert excinfo.value.reason == ParseError.UNSUPPORTED
    assert excinfo.value.detail == syntax


@pytest.mark.parametrize(
    "text", ["echo '$(date)'", "echo '&'", "echo 2 > f", "head -2>x", "echo a#b", "echo '#'"]
)
def test_lookalikes_of_unsupported_syntax_are_fine(text: str) -> None:
    """Single-quoted text, a separate number, or a number inside a flag isn't unsupported."""
    assert parse_chain(text) is not None


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ('ls | grep "x', ParseError.UNCLOSED_QUOTE),
        ("ls | echo x\\", ParseError.TRAILING_BACKSLASH),
        ("ls | '' x", ParseError.EMPTY_COMMAND),
    ],
)
def test_chain_keeps_earlier_parse_errors(text: str, reason: str) -> None:
    """The Phase 3 errors still work inside chains."""
    with pytest.raises(ParseError) as excinfo:
        parse_chain(text)
    assert excinfo.value.reason == reason


@pytest.mark.parametrize("text", ["", "   ", " "])
def test_blank_chain_is_none(text: str) -> None:
    """Blank input means there's nothing to explain."""
    assert parse_chain(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "ls -a | grep txt",
        'grep "a|b" f',
        "cat < 'my file.txt' | sort > out.txt",
        "mkdir d && cd d || echo failed ; ls",
        "echo '&&' \"$HOME\"",
    ],
)
def test_chain_to_text_round_trips(text: str) -> None:
    """Rebuilding the text and parsing it again gives the same chain."""
    chain = parse_chain(text)
    assert chain is not None
    assert parse_chain(chain_to_text(chain)) == chain


def test_split_operators_keeps_quotes_in_pieces() -> None:
    """split_operators returns raw pieces; quotes are removed later by tokenize()."""
    assert split_operators('echo "a|b" | wc') == ['echo "a|b" ', "|", " wc"]


@pytest.mark.parametrize("text", ["ls;2>x", "ls|2>x", "ls&&2>x"])
def test_numbered_redirect_right_after_an_operator(text: str) -> None:
    """2> straight after an operator is still a numbered redirect (unsupported)."""
    with pytest.raises(ParseError) as excinfo:
        parse_chain(text)
    assert (excinfo.value.reason, excinfo.value.detail) == (ParseError.UNSUPPORTED, "2>")


def test_lone_semicolon_is_missing_before() -> None:
    """A lone ';' says something is missing before it."""
    with pytest.raises(ParseError) as excinfo:
        parse_chain(";")
    assert (excinfo.value.reason, excinfo.value.detail) == (ParseError.MISSING_BEFORE, ";")


def test_clobber_redirect_is_unsupported() -> None:
    """>| (force overwrite) is named as unsupported."""
    with pytest.raises(ParseError) as excinfo:
        parse_chain("ls >| out")
    assert excinfo.value.detail == ">|"


def test_chain_command_keeps_typed_text() -> None:
    """Each command remembers its own text, quoting included."""
    chain = parse_chain('echo "a b" $HOME | sort > out.txt -r')
    assert chain is not None
    assert [c.text for c in chain.commands] == ['echo "a b" $HOME', "sort > out.txt -r"]


@pytest.mark.parametrize(
    ("typed", "tokens", "expected"),
    [
        ('sl -la "$HOME"', ["ls", "-la", "$HOME"], 'ls -la "$HOME"'),
        ("sudo sl 'a b'", ["sudo", "ls", "a b"], "sudo ls 'a b'"),
        ("srot > out.txt -r", ["sort", "-r"], "sort > out.txt -r"),
        ("LS", ["ls"], "ls"),
    ],
)
def test_retype_changes_only_the_fixed_words(typed: str, tokens: list[str], expected: str) -> None:
    """retype swaps changed words and keeps the user's quoting everywhere else."""
    chain = parse_chain(typed)
    assert chain is not None
    fixed = retype(chain.commands[0], tokens)
    assert fixed.text == expected
    assert fixed.tokens == tuple(tokens)


def test_retype_without_text_falls_back_to_rebuilding() -> None:
    """A command built in code (no typed text) is rebuilt from its words."""
    fixed = retype(ChainCommand(("sl", "a b")), ["ls", "a b"])
    assert fixed.display() == "ls 'a b'"
