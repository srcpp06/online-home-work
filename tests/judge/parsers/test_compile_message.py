"""What a student sees of a compile error (SPEC §3.8): their own code's errors in full,
the tests' errors as the message alone, never a test path or a line of test code."""

from pathlib import Path

from judge.core.messages import MAX_PUBLIC_MESSAGE
from judge.parsers import make_parser
from judge.parsers.compile_message import UNREADABLE, student_compile_message

FIXTURES = Path(__file__).parent / "fixtures" / "dart_json"

HIDDEN = (
    'Failed to load "test/_ohw_all_test.dart":\n'
    "test/hidden/02_discount_test.dart:9:12: Error: "
    "The method 'applyCoupon' isn't defined for the type 'Cart'.\n"
    " - 'Cart' is from 'package:cart/cart.dart' ('lib/cart.dart').\n"
    "Try correcting the name to the name of an existing method, "
    "or defining a method named 'applyCoupon'.\n"
    "    cart.applyCoupon('SECRET-2026');\n"
    "         ^^^^^^^^^^^\n"
)

OWN_CODE = """\
Failed to load "test/_ohw_all_test.dart":
lib/cart.dart:4:3: Error: Expected ';' after this.
  int total = 0
  ^^^
"""


def test_a_tests_error_keeps_the_message_and_drops_the_test_code() -> None:
    message = student_compile_message(HIDDEN)

    assert message == (
        "Kodingiz topshiriqdagi interfeysga mos emas: "
        "The method 'applyCoupon' isn't defined for the type 'Cart'."
    )


def test_an_error_in_the_students_code_is_shown_with_its_line() -> None:
    message = student_compile_message(OWN_CODE)

    assert message == ("lib/cart.dart:4:3: Error: Expected ';' after this.\n  int total = 0\n  ^^^")


def test_a_real_compiler_output_leaks_no_test_path_or_test_line() -> None:
    parser = make_parser("dart_json")
    for line in (FIXTURES / "compile_error.jsonl").read_text().splitlines():
        parser.feed(line)
    assert parser.compile_error is not None

    message = student_compile_message(parser.compile_error)

    assert "test/" not in message
    assert "expect(" not in message
    assert message.startswith(
        "Kodingiz topshiriqdagi interfeysga mos emas: "
        "The getter 'total' isn't defined for the type 'Cart'.\n"
    )
    # The student's own file keeps its location and line, once per error.
    assert message.count("lib/cart.dart:10:41: Error:") == 1
    assert "int totalWithDiscount(int percent) => total - total * percent ~/ 100;" in message


def test_the_same_test_error_is_listed_once() -> None:
    twice = HIDDEN + HIDDEN.replace("9:12", "15:7")

    assert student_compile_message(twice).count("applyCoupon") == 1


def test_a_note_about_a_test_file_inside_the_students_error_is_dropped() -> None:
    text = (
        "lib/cart.dart:3:7: Error: 'Coupon' is imported from both 'lib/a.dart' and x.\n"
        " - 'Coupon' is from 'test/hidden/helpers.dart'.\n"
        "class Coupon {}\n"
    )

    assert "test/hidden" not in student_compile_message(text)


def test_output_it_cannot_read_gives_a_plain_hint_not_the_raw_text() -> None:
    raw = "Unhandled exception:\n#0 test/hidden/secret_test.dart main\n"

    assert student_compile_message(raw) == UNREADABLE


def test_a_long_message_is_cut() -> None:
    errors = "".join(
        f"lib/cart.dart:{n}:1: Error: Undefined name 'value{n}'.\n  value{n};\n  ^\n"
        for n in range(200)
    )

    message = student_compile_message(errors)

    assert len(message) <= MAX_PUBLIC_MESSAGE
    assert message.endswith("...")
