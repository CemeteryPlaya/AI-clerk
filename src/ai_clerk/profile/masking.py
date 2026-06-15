def mask_iin(iin: str | None) -> str:
    """Mask an IIN, revealing only the last 4 digits."""
    if not iin:
        return "—"
    value = iin.strip()
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * (len(value) - 4) + value[-4:]


def mask_document(number: str | None) -> str:
    """Mask a document number, revealing only the last 3 characters."""
    if not number:
        return "—"
    value = number.strip()
    if len(value) <= 3:
        return "•" * len(value)
    return "•" * (len(value) - 3) + value[-3:]
