import re
from datetime import datetime

from stokguard.core.numbers import parse_quantity, parse_rupiah
from stokguard.ocr.schemas import ParsedLine, ParsedReceipt


def parse_receipt(text: str) -> ParsedReceipt:
    result = ParsedReceipt(raw_text=text)
    for line in text.splitlines():
        date = re.fullmatch(
            r"\s*Tanggal\s*:\s*(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})\s*", line, re.I
        )
        if date and result.receipt_date is None:
            value = date[1]
            try:
                result.receipt_date = (
                    datetime.strptime(
                        value, "%Y-%m-%d" if len(value.split("-")[0]) == 4 else "%d-%m-%Y"
                    )
                    .date()
                    .isoformat()
                )
            except ValueError:
                pass
        number = re.fullmatch(
            r"\s*(?:No\.?\s*Nota|Nomor\s*Nota)\s*:\s*([\w/-]{1,100})\s*", line, re.I
        )
        if number and result.receipt_number is None:
            result.receipt_number = number[1]
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3 or not parts[0] or len(parts[0]) > 200:
            continue
        try:
            if parse_quantity(parts[1], 1) <= 0:
                continue
            parse_rupiah(parts[2])
        except ValueError:
            continue
        result.lines.append(ParsedLine(name=parts[0], quantity=parts[1], price_rupiah=parts[2]))
    return result
