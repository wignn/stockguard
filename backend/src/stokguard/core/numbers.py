import re
from decimal import ROUND_HALF_UP, Decimal, localcontext

MAX_INT = 2**63 - 1
MIN_INT = -(2**63)
QUANTITY = re.compile(r"[0-9]+(?:\.[0-9]{1,3})?\Z")
RUPIAH = re.compile(r"[0-9]+\Z")


def checked_integer(value: int) -> int:
    if type(value) is not int or not MIN_INT <= value <= MAX_INT:
        raise ValueError("Nilai di luar batas yang didukung.")
    return value


def parse_quantity(value: str, step_milli: int) -> int:
    if type(step_milli) is not int or not 1 <= step_milli <= MAX_INT:
        raise ValueError("Langkah kuantitas tidak valid.")
    if not isinstance(value, str) or len(value) > 24 or not QUANTITY.fullmatch(value):
        raise ValueError("Jumlah harus berupa desimal nonnegatif, maksimal tiga angka pecahan.")
    whole, _, fraction = value.partition(".")
    milli = checked_integer(int(whole) * 1000 + int(fraction.ljust(3, "0") or "0"))
    if milli % step_milli:
        raise ValueError("Jumlah tidak sesuai satuan produk.")
    return milli


def format_quantity(milli: int) -> str:
    checked_integer(milli)
    sign = "-" if milli < 0 else ""
    whole, remainder = divmod(abs(milli), 1000)
    fraction = f".{remainder:03d}".rstrip("0") if remainder else ""
    return f"{sign}{whole}{fraction}"


def parse_rupiah(value: str) -> int:
    if not isinstance(value, str) or len(value) > 19 or not RUPIAH.fullmatch(value):
        raise ValueError("Harga harus berupa bilangan rupiah nonnegatif.")
    return checked_integer(int(value))


def value_delta(milli: int, cost_rupiah: int) -> int:
    checked_integer(milli)
    checked_integer(cost_rupiah)
    if cost_rupiah < 0:
        raise ValueError("Harga pokok tidak boleh negatif.")
    with localcontext() as ctx:
        ctx.prec = 50
        result = Decimal(milli) * Decimal(cost_rupiah) / Decimal(1000)
        return checked_integer(int(result.quantize(Decimal(1), rounding=ROUND_HALF_UP)))
