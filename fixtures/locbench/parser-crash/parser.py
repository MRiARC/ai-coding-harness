"""Tokenizes config strings into key/value pairs."""


def parse_tokens(raw):
    # BUG: crashes on strings without an equals sign.
    key, value = raw.split("=")
    return {key.strip(): value.strip()}
