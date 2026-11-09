def test_unknown_layout_returns_text_without_invented_fields():
    from stokguard.ocr.parser import parse_receipt

    text = "SYNTHETIC OCR FIXTURE\nTOKO CONTOH\nRp 27.000\nTerima kasih"
    result = parse_receipt(text)
    assert result.raw_text == text
    assert result.receipt_number is None and result.receipt_date is None
    assert result.lines == []


def test_explicit_labels_and_lines_only():
    from stokguard.ocr.parser import parse_receipt

    result = parse_receipt(
        "Tanggal: 09-11-2026\nNo Nota: SYN-123\nRoti|2|12000\nGula 3 9000\nA|1,2|9000"
    )
    assert result.receipt_date == "2026-11-09"
    assert result.receipt_number == "SYN-123"
    assert len(result.lines) == 1
    assert result.lines[0].name == "Roti" and result.lines[0].quantity == "2"
    assert result.lines[0].price_rupiah == "12000"
    assert parse_receipt("Tanggal: 2026-02-30").receipt_date is None
    assert parse_receipt("Tanggal: 2026-11-09").receipt_date == "2026-11-09"
