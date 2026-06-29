def parse_mu_number(number: str) -> tuple[int, int]:
    if not number or not number.startswith("MU-"):
        return (0, 0)

    try:
        body = number[3:]
        sequence_part, year_part = body.split("/", 1)
        return (int(year_part), int(sequence_part))
    except (ValueError, AttributeError):
        return (0, 0)


def mu_number_sort_key(number: str) -> tuple[int, int]:
    return parse_mu_number(number)
