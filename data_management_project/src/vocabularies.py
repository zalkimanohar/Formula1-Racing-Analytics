"""Controlled vocabularies used by the cleaning pipeline (Component C) and documented in the metadata.

Every mapping is explicit and exhaustive: an unmapped source value stops the pipeline instead of
being silently passed through.
"""
from __future__ import annotations

import re

COUNTRY_NAME_FIXES = {
    "UK": "United Kingdom",
    "USA": "United States",
    "UAE": "United Arab Emirates",
    "Korea": "South Korea",
}

COUNTRY_ISO3 = {
    "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT", "Azerbaijan": "AZE", "Bahrain": "BHR",
    "Belgium": "BEL", "Brazil": "BRA", "Canada": "CAN", "China": "CHN", "France": "FRA",
    "Germany": "DEU", "Hungary": "HUN", "India": "IND", "Italy": "ITA", "Japan": "JPN",
    "Malaysia": "MYS", "Mexico": "MEX", "Monaco": "MCO", "Morocco": "MAR", "Netherlands": "NLD",
    "Portugal": "PRT", "Qatar": "QAT", "Russia": "RUS", "Saudi Arabia": "SAU", "Singapore": "SGP",
    "South Africa": "ZAF", "South Korea": "KOR", "Spain": "ESP", "Sweden": "SWE", "Switzerland": "CHE",
    "Turkey": "TUR", "United Arab Emirates": "ARE", "United Kingdom": "GBR", "United States": "USA",
}

# Demonyms -> ISO 3166-1 alpha-3; former states use their ISO 3166-3 four-letter code.
NATIONALITY_ISO = {
    "american": "USA", "argentine": "ARG", "australian": "AUS", "austrian": "AUT", "belgian": "BEL",
    "brazilian": "BRA", "british": "GBR", "canadian": "CAN", "chilean": "CHL", "chinese": "CHN",
    "colombian": "COL", "czech": "CZE", "danish": "DNK", "dutch": "NLD", "east german": "DDDE",
    "finnish": "FIN", "french": "FRA", "german": "DEU", "hong kong": "HKG", "hungarian": "HUN",
    "indian": "IND", "indonesian": "IDN", "irish": "IRL", "italian": "ITA", "japanese": "JPN",
    "liechtensteiner": "LIE", "malaysian": "MYS", "mexican": "MEX", "monegasque": "MCO",
    "new zealander": "NZL", "polish": "POL", "portuguese": "PRT", "rhodesian": "RHZW",
    "russian": "RUS", "south african": "ZAF", "spanish": "ESP", "swedish": "SWE", "swiss": "CHE",
    "thai": "THA", "uruguayan": "URY", "venezuelan": "VEN",
}

STATUS_FINISHED = "Finished"
STATUS_LAPPED = "Finished (lapped)"
STATUS_ACCIDENT = "Accident or collision"
STATUS_MECHANICAL = "Mechanical or technical failure"
STATUS_HEALTH = "Driver health or safety"
STATUS_DNS = "Did not start or withdrew"
STATUS_DSQ = "Disqualified or excluded"
STATUS_RETIRED = "Retired (unspecified) or not classified"

LAPPED_RE = re.compile(r"^\+\d+ Laps?$")

STATUS_GROUP = {
    "Finished": STATUS_FINISHED,
    "Lapped": STATUS_LAPPED,
    **{s: STATUS_ACCIDENT for s in (
        "Accident", "Collision", "Collision damage", "Damage", "Debris", "Fatal accident", "Spun off")},
    **{s: STATUS_MECHANICAL for s in (
        "Alternator", "Axle", "Battery", "Brake duct", "Brakes", "Broken wing", "CV joint", "Chassis",
        "Clutch", "Cooling system", "Crankshaft", "Differential", "Distributor", "Driver Seat", "Driveshaft",
        "Drivetrain", "ERS", "Electrical", "Electronics", "Engine", "Engine fire", "Engine misfire",
        "Exhaust", "Fire", "Front wing", "Fuel", "Fuel leak", "Fuel pipe", "Fuel pressure", "Fuel pump",
        "Fuel rig", "Fuel system", "Gearbox", "Halfshaft", "Handling", "Heat shield fire", "Hydraulics",
        "Ignition", "Injection", "Launch control", "Magneto", "Mechanical", "Oil leak", "Oil line",
        "Oil pipe", "Oil pressure", "Oil pump", "Out of fuel", "Overheating", "Pneumatics", "Power Unit",
        "Power loss", "Puncture", "Radiator", "Rear wing", "Refuelling", "Safety belt", "Seat",
        "Spark plugs", "Stalled", "Steering", "Supercharger", "Suspension", "Technical", "Throttle",
        "Track rod", "Transmission", "Turbo", "Tyre", "Tyre puncture", "Undertray", "Vibrations",
        "Water leak", "Water pipe", "Water pressure", "Water pump", "Wheel", "Wheel bearing", "Wheel nut",
        "Wheel rim")},
    **{s: STATUS_HEALTH for s in (
        "Driver unwell", "Eye injury", "Illness", "Injured", "Injury", "Physical", "Safety", "Safety concerns")},
    **{s: STATUS_DNS for s in ("Did not start", "Withdrew")},
    **{s: STATUS_DSQ for s in ("Disqualified", "Excluded", "Underweight")},
    **{s: STATUS_RETIRED for s in ("Not classified", "Not restarted", "Retired")},
}

FINISH_CATEGORY_BY_CODE = {"R": "Retired", "W": "Withdrawn", "D": "Disqualified"}

LOWERCASE_PARTICLES = {"de", "di", "da", "del", "della", "do", "dos", "das", "van", "von", "der", "den",
                       "la", "le", "du", "y", "e", "of", "the", "and"}


# Names the casing rule cannot restore; official spelling taken from the entity's Wikipedia article.
NAME_EXCEPTIONS = {
    "Avus": "AVUS",
    "Rouen-Les-Essarts": "Rouen-les-Essarts",
    "Jérôme D'Ambrosio": "Jérôme d'Ambrosio",
    "Fritz D'Orey": "Fritz d'Orey",
    "Robert la Caze": "Robert La Caze",
    "Mike Macdowel": "Mike MacDowel",
}


def status_group(status: str) -> str | None:
    if LAPPED_RE.match(status):
        return STATUS_LAPPED
    return STATUS_GROUP.get(status)


def _capitalise_word(word: str) -> str:
    pieces = re.split(r"([-'])", word)
    out = []
    for piece in pieces:
        if piece in ("-", "'") or not piece:
            out.append(piece)
            continue
        if piece[0].isalpha():
            piece = piece[0].upper() + piece[1:]
            if piece.startswith("Mc") and len(piece) > 2:
                piece = "Mc" + piece[2].upper() + piece[3:]
        out.append(piece)
    return "".join(out)


def smart_title(text):
    """Title-case a lowercased proper name; keep particles lowercase after the first word.

    'circuit of the americas' -> 'Circuit of the Americas', '70th anniversary grand prix' ->
    '70th Anniversary Grand Prix', "patricio o'ward" -> "Patricio O'Ward", 'bruce mclaren' -> 'Bruce McLaren'.
    """
    if text is None or text != text:
        return text
    words = str(text).split(" ")
    titled = " ".join(w if (i > 0 and w in LOWERCASE_PARTICLES) else _capitalise_word(w)
                      for i, w in enumerate(words))
    return NAME_EXCEPTIONS.get(titled, titled)
