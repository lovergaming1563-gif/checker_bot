import re

def validate_mobile_number(number: str) -> bool:
    """
    Validates mobile number format.
    Requires exactly 10 digits.
    """
    # Regex for exactly 10 digits
    pattern = r"^\d{10}$"
    return bool(re.match(pattern, number))
