"""Bound untrusted primary keys before Python conversion or ORM lookups."""


def parse_positive_id(value):
    text = str(value) if value is not None else ''
    if not (1 <= len(text) <= 19 and text.isascii() and text.isdecimal()):
        return None
    number = int(text)
    return number if 1 <= number <= 9223372036854775807 else None
