"""Validazioni leggere. Verificam FORMA, nao existencia real da empresa."""
import re


def piva_check_digit(first10: str) -> int:
    total = 0
    for i, ch in enumerate(first10):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10


def is_valid_piva_format(value: str) -> bool:
    """11 digitos + digito verificador. Passar aqui NAO prova que a empresa existe."""
    v = (value or "").strip().replace(" ", "")
    if not re.fullmatch(r"\d{11}", v):
        return False
    return piva_check_digit(v[:10]) == int(v[10])


def normalize_ateco(code: str) -> str:
    """'4941' / '49.41' / '49.41.00' -> '49.41' (apenas formatacao)."""
    digits = re.sub(r"\D", "", code or "")
    if len(digits) < 2:
        raise ValueError(f"ATECO invalido: {code!r}")
    return f"{digits[:2]}.{digits[2:4]}" if len(digits) >= 4 else digits[:2]
