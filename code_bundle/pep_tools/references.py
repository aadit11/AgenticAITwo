"""Build public PEP links from a PEP number."""


def pep_url(number: int) -> str:
    """Return the canonical zero-padded PEP URL."""
    if number < 0:
        raise ValueError("PEP number must be zero or greater")
    return f"https://peps.python.org/pep-{number:04d}/"


def format_pep_reference(number: int, title: str) -> str:
    """Return a citation string the summary agent can keep next to a passage."""
    cleaned = " ".join(title.split())
    return f"PEP {number}: {cleaned} ({pep_url(number)})"
