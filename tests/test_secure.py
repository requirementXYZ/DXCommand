import pytest

from app.secure import (SecretError, is_protected, merge_secret, protect,
                        reveal, PREFIX)


def test_protect_reveal_roundtrip():
    stored = protect("hunter2")
    assert stored != "hunter2"
    assert stored.startswith(PREFIX)
    assert "hunter2" not in stored
    assert reveal(stored) == "hunter2"


def test_protect_is_idempotent():
    once = protect("secret")
    assert protect(once) == once


def test_empty_passthrough():
    assert protect("") == ""
    assert reveal("") == ""
    assert not is_protected("")


def test_reveal_plaintext_passthrough():
    # pre-migration values (plaintext) must still be usable
    assert reveal("legacyplain") == "legacyplain"


def test_corrupted_blob_raises_clean_error():
    with pytest.raises(SecretError, match="re-enter"):
        reveal(PREFIX + "bm90LXJlYWwtZHBhcGk=")


def test_merge_secret_blank_keeps_stored():
    stored = protect("keepme")
    assert merge_secret(stored, "") == stored
    assert merge_secret(stored, None) == stored


def test_merge_secret_new_value_replaces_encrypted():
    stored = protect("old")
    new = merge_secret(stored, "newpass")
    assert new != stored
    assert is_protected(new)
    assert reveal(new) == "newpass"


def test_unicode_password():
    assert reveal(protect("pässwörd£☃")) == "pässwörd£☃"
