COUNTRY_CODES = {
    "Angola": "ao", "Botswana": "bw", "Comoros": "km",
    "Democratic Republic of the Congo": "cd", "Eswatini": "sz",
    "Lesotho": "ls", "Madagascar": "mg", "Malawi": "mw",
    "Mauritius": "mu", "Mozambique": "mz", "Namibia": "na",
    "Seychelles": "sc", "South Africa": "za", "Tanzania": "tz",
    "Zambia": "zm", "Zimbabwe": "zw",
    "Nigeria": "ng", "Kenya": "ke", "Ghana": "gh", "Egypt": "eg",
    "Morocco": "ma", "Ethiopia": "et", "Uganda": "ug", "Rwanda": "rw",
    "Senegal": "sn", "Tunisia": "tn", "Algeria": "dz",
    "Ivory Coast": "ci", "Cameroon": "cm",
    "United States": "us", "Canada": "ca", "Mexico": "mx",
    "Brazil": "br", "Argentina": "ar", "Chile": "cl", "Colombia": "co",
    "Peru": "pe", "Venezuela": "ve", "Ecuador": "ec", "Bolivia": "bo",
    "Uruguay": "uy", "Paraguay": "py", "Cuba": "cu", "Jamaica": "jm",
    "Panama": "pa", "Costa Rica": "cr",
}

def user_country_flag(request):
    country_code = ""
    if request.user.is_authenticated:
        profile = getattr(request.user, "userprofile", None)
        if profile and profile.country:
            country_code = COUNTRY_CODES.get(profile.country, "")
    return {"country_code": country_code}