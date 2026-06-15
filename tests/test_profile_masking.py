from ai_clerk.profile.masking import mask_document, mask_iin


def test_mask_iin_keeps_last_four():
    assert mask_iin("900101300123") == "••••••••0123"


def test_mask_iin_handles_short_and_empty():
    assert mask_iin("12") == "••"
    assert mask_iin(None) == "—"
    assert mask_iin("") == "—"


def test_mask_document_keeps_last_three():
    assert mask_document("N12345678") == "••••••678"


def test_mask_document_handles_short_and_empty():
    assert mask_document("AB") == "••"
    assert mask_document(None) == "—"
