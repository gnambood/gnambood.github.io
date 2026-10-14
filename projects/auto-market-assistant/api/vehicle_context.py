"""Conservative guard against an explicitly named vehicle differing from the form."""
import re


def _normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).lower())).strip()


def vehicle_context_conflict(question, make, model, year, known_pairs):
    """Return a user-facing mismatch message, or None.

    Only unambiguous make+model mentions present in the review corpus count.
    Questions that do not explicitly name a vehicle remain unchanged.
    """
    text = _normalize(question)
    selected_make = _normalize(make)
    selected_family = " ".join(_normalize(model).split()[:2])
    selected_year = int(year) if year is not None else None
    matches = []

    for candidate_make, candidate_family in known_pairs:
        candidate_make = _normalize(candidate_make)
        candidate_family = _normalize(candidate_family)
        if not candidate_make or not candidate_family:
            continue
        pattern = (
            r"(?<![a-z0-9])(?:(?P<year>(?:19|20)\d{2})\s+)?"
            + re.escape(candidate_make) + r"\s+"
            + re.escape(candidate_family) + r"(?![a-z0-9])"
        )
        for hit in re.finditer(pattern, text):
            matches.append((candidate_make, candidate_family, hit.group("year")))

    # No explicit vehicle, or multiple distinct vehicles being compared:
    # avoid guessing which vehicle the user intended.
    found = set(matches)
    if len(found) != 1:
        return None

    named_make, named_family, named_year = next(iter(found))
    if (
        named_make == selected_make
        and named_family == selected_family
        and (named_year is None or selected_year is None or int(named_year) == selected_year)
    ):
        return None

    selected = f"{selected_year} {make} {model}" if selected_year else f"{make} {model}"
    named = f"{named_year} {named_make} {named_family}" if named_year else f"{named_make} {named_family}"
    return (
        f"Your selected vehicle is {selected}, but your question asks about "
        f"{named}. Please change the vehicle selection or update your question."
    )
