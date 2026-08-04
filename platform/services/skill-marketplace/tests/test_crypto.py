from skill_marketplace.crypto import decrypt_token, encrypt_token


def test_encrypt_decrypt_round_trips():
    plaintext = "xoxp-super-secret-slack-token"
    ciphertext = encrypt_token(plaintext)

    assert ciphertext != plaintext
    assert decrypt_token(ciphertext) == plaintext


def test_ciphertext_is_not_plaintext_substring():
    plaintext = "ya29.a0-google-access-token"
    ciphertext = encrypt_token(plaintext)
    assert plaintext not in ciphertext
