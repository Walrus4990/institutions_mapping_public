"""Build coding/registries/international_networks.csv: the ROR records of one international organisation (NGO
network, UN body, CGIAR centre, company group) and the record that stands for the whole organisation (rulebook
6.4, client 22 Oct 2026).
Members = active ROR records of the same organisation in other countries (name pattern only; parent links are not used,
because they also lead to universities and hospitals of the same network).

Usage: python tools/make_networks.py ROR_DIR coding/registries/international_networks.csv
"""

import sys

import pandas as pd

# network, international ROR record, name pattern of member records (matched on display_name), why this record
NET = [
    ("Médecins Sans Frontières", "032mwd808", r"^Médecins Sans Frontières$", "MSF International, Geneva (msf.org)"),
    (
        "Save the Children",
        "02y2gng66",
        r"^Save the Children( Japan)?$",
        "headquarters (Save the Children International, London) has no ROR record: main member's record "
        "(Save the Children UK), until ROR adds the headquarters",
    ),
    ("AIDS Healthcare Foundation", "05n8mee18", r"^AIDS Healthcare Foundation$", "headquarters, Los Angeles"),
    (
        "Elizabeth Glaser Pediatric AIDS Foundation",
        "00vzqmg54",
        r"^Elizabeth Glaser Pediatric AIDS Foundation$",
        "headquarters, Washington DC",
    ),
    ("Innovations for Poverty Action", "0235ad950", r"^Innovations for Poverty Action$", "headquarters, New Haven"),
    ("International Rescue Committee", "03v6ftq03", r"^International Rescue Committee$", "headquarters, New York"),
    (
        "Plan International",
        "02ytj9t26",
        r"^Plan International(?: Japan| Tanzania| Regional Office of the Americas)?$",
        "record with the global website plan-international.org (headquarters: Global Hub, Woking; "
        "ROR lists the record in Bolivia)",
    ),
    ("Amref Health Africa", "00qpv3w06", r"^Amref Health Africa$", "headquarters, Nairobi"),
    ("Aga Khan Development Network", "028mpsh75", r"^Aga Khan Development Network$", "headquarters, Geneva"),
    ("Aga Khan Foundation", "03t8x2c04", r"^Aga Khan Foundation$", "headquarters, Geneva"),
    ("Malaria Consortium", "02hn7j889", r"^Malaria Consortium$", "headquarters, London"),
    (
        "Population Services International",
        "03x1cjm87",
        r"^Population Services International$",
        "headquarters, Washington DC",
    ),
    ("Population Council", "03zjj0p70", r"^Population Council$", "headquarters, New York"),
    ("GIZ", "00q08t645", r"^Deutsche Gesellschaft für Internationale Zusammenarbeit$", "headquarters, Bonn/Eschborn"),
    ("PATH", "02ycvrx49", r"^Program for Appropriate Technology in Health$", "headquarters, Seattle"),
    (
        "CARE International",
        "029ma5383",
        r"^(CARE International( Japan| in Vietnam)?|Care International( Sri Lanka)?|CARE USA|CARE Canada|Care India)$",
        "CARE International secretariat, Geneva",
    ),
    ("Concern Worldwide", "004qxjv96", r"^Concern Worldwide( UK| US)?$", "headquarters, Dublin"),
    (
        "Helen Keller Intl",
        "04qxbzf60",
        r"^(Helen Keller International( Nepal)?|HELEN KELLER INTL Cambodia)$",
        "headquarters, New York",
    ),
    (
        "WaterAid",
        "02at6q094",
        r"^WaterAid( America)?$",
        "headquarters (WaterAid International) has no ROR record: main member's record (WaterAid UK), "
        "until ROR adds the headquarters",
    ),
    ("World Vision", "00jemq805", r"^World Vision( International)?$", "World Vision International"),
    (
        "Oxfam",
        "022283x63",
        r"^Oxfam( America| Intermón| México| Solidarité)?$",
        "headquarters (Oxfam International secretariat, Nairobi) has no ROR record: main member's record "
        "(Oxfam GB), until ROR adds the headquarters",
    ),
    ("British Council", "00t3pr326", r"^British Council$", "headquarters, London"),
    ("Busara", "032f13a22", r"^Busara Center for Behavioral Economics$", "headquarters, Nairobi"),
    (
        "World Health Organization",
        "01f80g185",
        r"^World Health Organization( - .*| Regional Office .*)?$",
        "headquarters, Geneva",
    ),
    (
        "International Organization for Migration",
        "01j7ed328",
        r"^International Organization for Migration$",
        "headquarters, Geneva",
    ),
    ("FAIRMED", "05k7y1t77", r"^(FAIRMED|Fairmed)$", "foundation headquarters, Bern"),
    ("IITA", "00va88c89", r"^International Institute of Tropical Agriculture$", "CGIAR centre, headquarters Ibadan"),
    (
        "CIMMYT",
        "03gvhpa76",
        r"^(International Maize and Wheat Improvement Center|Centro Internacional de Mejoramiento de Maíz Y Trigo)$",
        "CGIAR centre, headquarters El Batán, Mexico",
    ),
    (
        "ICRISAT",
        "0541a3n79",
        r"^International Crops Research Institute for the Semi-Arid Tropics$",
        "CGIAR centre, headquarters Patancheru, India",
    ),
    ("IQVIA", "01mk44223", r"^IQVIA ", "company headquarters, United States"),
    ("Tetra Tech", "03fk8t087", r"^Tetra Tech ", "company headquarters, United States"),
    ("GSK", "01xsqw823", r"^GlaxoSmithKline", "company headquarters, United Kingdom"),
    ("UNICEF", "02dg0pv02", r"^United Nations Children's Fund$", "headquarters, New York"),
]


def members(orgs, pattern):
    """The active ROR records whose display name matches a pattern of NET (its groups made non-capturing)."""
    names = orgs.display_name.str.replace("\u200e", "").str.strip()
    return set(orgs.index[names.str.contains(pattern.replace("(", "(?:").replace("(?:?:", "(?:"), regex=True)])


def networks(orgs):
    """One row per member record of each network in NET, with the record that stands for the whole network."""
    rows = []
    for net, hq, pattern, why in NET:
        assert hq in orgs.index, (net, hq)
        for i in sorted(members(orgs, pattern) - {hq}):
            rows.append(
                dict(
                    network=net,
                    international_ror_id=hq,
                    international_name=orgs.at[hq, "display_name"],
                    member_ror_id=i,
                    member_name=orgs.at[i, "display_name"],
                    member_country=orgs.at[i, "country_code"],
                    why=why,
                )
            )
    return pd.DataFrame(rows)


def main(argv):
    """Write the registry and print the number of members per network."""
    ror_dir, out = argv[:2]
    orgs = pd.read_csv(f"{ror_dir}/ror_orgs.csv", dtype=str, keep_default_na=False)
    d = networks(orgs[orgs.status == "active"].set_index("ror_id"))
    d.to_csv(out, index=False)
    print(d.groupby("network").size().to_string())


if __name__ == "__main__":
    main(sys.argv[1:])
