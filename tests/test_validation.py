"""Data validation & the advertised-max-vs-actual-award rule.

Advertised maximum lives on Program (catalog). Actual award lives on
Application (submission) and may only be set on an approval status.
"""
import pytest
from pydantic import ValidationError

from app.enums import Status, UNVERIFIED, ValueDisclosure
from app.models import Application, CreditAward, Program


def test_verified_program_holds_advertised_maximum_not_award():
    prog = Program(
        provider="Acme", name="Acme Startups",
        value_disclosure=ValueDisclosure.VERIFIED,
        advertised_maximum=100000.0,
    )
    assert prog.advertised_maximum == 100000.0
    # Program has no concept of actual_award at all.
    assert not hasattr(prog, "actual_award")


def test_unverified_number_is_rejected():
    # A numeric advertised maximum without a VERIFIED classification is refused
    # (prevents storing an invented/unverified figure).
    with pytest.raises(ValidationError):
        Program(provider="Acme", name="P", advertised_maximum=50000.0)


def test_verified_noncash_benefit_allows_no_number():
    # A VERIFIED non-cash benefit (e.g. Auth0/Okta) legitimately has no dollar
    # figure — a number is allowed but never required.
    prog = Program(provider="Auth0 / Okta", name="Auth0 for Startups",
                   value_disclosure=ValueDisclosure.VERIFIED,
                   advertised_maximum=None,
                   advertised_maximum_text="One year of B2B Professional, up to 100,000 MAUs")
    assert prog.advertised_maximum is None
    assert prog.value_disclosure is ValueDisclosure.VERIFIED


def test_conditional_number_allowed():
    # Conditional ceilings carry a verified numeric maximum (not a guarantee).
    prog = Program(provider="NVIDIA", name="NVIDIA Inception",
                   value_disclosure=ValueDisclosure.CONDITIONAL,
                   advertised_maximum=100000.0)
    assert prog.advertised_maximum == 100000.0


def test_variable_disclosure_keeps_number_none():
    prog = Program(provider="Acme", name="P",
                   value_disclosure=ValueDisclosure.VARIABLE)
    assert prog.advertised_maximum is None
    assert prog.value_disclosure is ValueDisclosure.VARIABLE


def test_application_award_without_approval_fails():
    with pytest.raises(ValidationError):
        Application(
            program_id="program-0001", provider="Acme", program="Acme Startups",
            status=Status.SUBMITTED, actual_award=100000.0,  # illegal: not approved
        )


def test_application_award_allowed_when_approved():
    app = Application(
        program_id="program-0001", provider="Acme", program="Acme Startups",
        status=Status.APPROVED, actual_award=25000.0,
    )
    assert app.actual_award == 25000.0


def test_application_award_allowed_when_partially_approved():
    app = Application(
        program_id="p", provider="Acme", program="P",
        status=Status.PARTIALLY_APPROVED, actual_award=5000.0,
    )
    assert app.actual_award == 5000.0


def test_application_requires_program_reference():
    with pytest.raises(ValidationError):
        Application(program_id="  ", provider="Acme", program="P")


def test_unverified_sentinel_preserved_on_program():
    prog = Program(
        provider="Twilio", name="Searchlight",
        advertised_maximum=None, advertised_maximum_text=UNVERIFIED,
    )
    assert prog.advertised_maximum is None
    assert prog.advertised_maximum_text == UNVERIFIED


def test_blank_provider_fails_on_program():
    with pytest.raises(ValidationError):
        Program(provider="   ", name="P")


def test_negative_award_fails():
    with pytest.raises(ValidationError):
        Application(program_id="p", provider="A", program="P",
                    status=Status.APPROVED, actual_award=-1.0)


def test_secret_like_notes_rejected():
    with pytest.raises(ValidationError):
        Program(provider="A", name="P", notes="password=hunter2 do not do this")


def test_credit_used_cannot_exceed_award():
    with pytest.raises(ValidationError):
        CreditAward(provider_program="A", actual_award=100.0, amount_used=200.0)
