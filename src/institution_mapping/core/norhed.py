"""The NORHED partner list (source: docs/reference/norhed_partners_ror_matching.xlsx).

Used in the mapping only for rule 5.5 (a NORHED partner as tie-breaker, applied through recorded decisions) and to
give partners that are not in ROR their LOCAL ID; the client path sets its `norhed` column from it (rule 11.5).
The M&E pipeline sets its own NORHED flag.
Row 67, University of Letters and Humanities, is a value of the Moodle NORHED dropdown that could not be identified:
it has a LOCAL ID and no country. Columns: name as in the partner file and the dropdown, partner's country, ROR ID or
LOCAL ID, ROR name.
"""

import pandas as pd

NORHED = [
    ("University of Ngaoundéré", "Cameroon", "03gq1d339", "University of Ngaoundéré"),
    ("University of Maroua", "Cameroon", "051sa4h84", "University of Maroua"),
    ("Addis Ababa University", "Ethiopia", "038b8e254", "Addis Ababa University"),
    ("Hawassa University", "Ethiopia", "04r15fz20", "Hawassa University"),
    ("Haramaya University", "Ethiopia", "059yk7s89", "Haramaya University"),
    ("Bahir Dar University", "Ethiopia", "01670bg46", "Bahir Dar University"),
    ("Jimma University", "Ethiopia", "05eer8g02", "Jimma University"),
    ("Mekelle University", "Ethiopia", "04bpyvy69", "Mekelle University"),
    ("Eastern Nile Technical Regional Office - Ethiopia", "Ethiopia", "LOCAL-0001", ""),
    ("University of Gondar", "Ethiopia", "0595gz585", "University of Gondar"),
    (
        "Addis Ababa Science and Technology University",
        "Ethiopia",
        "02psd9228",
        "Addis Ababa Science and Technology University",
    ),
    ("Debre Markos University", "Ethiopia", "04sbsx707", "Debre Markos University"),
    ("Wollega University", "Ethiopia", "00316zc91", "Wollega University"),
    ("Arba Minch University", "Ethiopia", "00ssp9h11", "Arba Minch University"),
    ("Dilla University", "Ethiopia", "04ahz4692", "Dilla University"),
    ("Université de Kinshasa", "D.R. Congo", "05rrz2q74", "University of Kinshasa"),
    ("University of Cape Coast", "Ghana", "0492nfe34", "University of Cape Coast"),
    ("University of Ghana", "Ghana", "01r22mr83", "University of Ghana"),
    ("University for Development Studies", "Ghana", "052nhnq73", "University for Development Studies"),
    (
        "Kwame Nkrumah University of Science and Technology",
        "Ghana",
        "00cb23x68",
        "Kwame Nkrumah University of Science and Technology",
    ),
    ("University of Nairobi", "Kenya", "02y9nww90", "University of Nairobi"),
    ("Maseno University", "Kenya", "023pskh72", "Maseno University"),
    ("Kenya Medical Research Institute", "Kenya", "04r1cxt79", "Kenya Medical Research Institute"),
    ("Technical University of Kenya (TUK)", "Kenya", "04eehsy38", "Technical University of Kenya"),
    (
        "African Population and Health Research Center (APHRC)",
        "Kenya",
        "032ztsj35",
        "African Population and Health Research Center",
    ),
    ("Egerton University", "Kenya", "01jk2zc89", "Egerton University"),
    ("Machakos University", "Kenya", "05eyrmk93", "Machakos University"),
    ("Kamuzu University of Health Sciences (KUHeS)", "Malawi", "00khnq787", "Kamuzu University of Health Sciences"),
    (
        "Malawi University of Science and Technology (MUST)",
        "Malawi",
        "027vmhf17",
        "Malawi University of Science and Technology",
    ),
    ("University of Malawi", "Malawi", "04vtx5s55", "University of Malawi"),
    ("Queen Elizabeth Central Hospital", "Malawi", "025sthg37", "Queen Elizabeth Central Hospital"),
    ("Kamuzu Central Hospital", "Malawi", "022j3nr24", "Kamuzu Central Hospital"),
    (
        "Lilongwe University of Agriculture and Natural Resources (LUANAR)",
        "Malawi",
        "0188qm081",
        "Lilongwe University of Agriculture and Natural Resources",
    ),
    ("University of Mzuzu", "Malawi", "008ej3804", "Mzuzu University"),
    ("University of Bamako", "Mali", "02s6w8y22", "University of Bamako"),
    ("Eduardo Mondlane University", "Mozambique", "05n8n9378", "Eduardo Mondlane University"),
    ("Lurio University/University of Lurio", "Mozambique", "03sbnrq14", "Lúrio University"),
    ("Université Abdou Moumouni de Niamey", "Niger", "05tj8pb04", "Université Abdou Moumouni"),
    ("University of Lagos", "Nigeria", "05rk03822", "University of Lagos"),
    ("University of Rwanda", "Rwanda", "00286hs46", "University of Rwanda"),
    ("University of Khartoum", "Sudan", "02jbayz55", "University of Khartoum"),
    ("University of the Witwatersrand", "South Africa", "03rp50x72", "University of the Witwatersrand"),
    ("University of KwaZulu-Natal", "South Africa", "04qzfn040", "University of KwaZulu-Natal"),
    ("University of Bahr El Ghazal", "South Sudan", "02zrvx577", "University of Bahr El-Ghazal"),
    ("University of Juba", "South Sudan", "02f1kft51", "University of Juba"),
    ("University of Dar Es Salaam", "Tanzania", "0479aed98", "University of Dar es Salaam"),
    ("Tanzania Institute of Education", "Tanzania", "00bwsj193", "Tanzania Institute of Education (TIE)"),
    ("Patandi Teachers College of Special Needs", "Tanzania", "LOCAL-0002", ""),
    (
        "Muhimbili University of Health and Allied Sciences",
        "Tanzania",
        "027pr6c67",
        "Muhimbili University of Health and Allied Sciences",
    ),
    ("University of Dodoma", "Tanzania", "009n8zh45", "The University of Dodoma"),
    ("Dar es Salaam Institute of Technology", "Tanzania", "038c55s31", "Dar es Salaam Institute of Technology"),
    ("Institute of Social Work -Tanzania", "Tanzania", "03zeb7y98", "Institute of Social Work"),
    ("State University of Zanzibar", "Tanzania", "0316x1478", "State University of Zanzibar"),
    ("Kilimanjaro Christian Medical University College", "Tanzania", "01e6x5f94", "KCMC University"),
    (
        "National Institute for Medical Research -Tanzania",
        "Tanzania",
        "05fjs7w98",
        "National Institute for Medical Research",
    ),
    (
        "Mbeya University of Science and Technology",
        "Tanzania",
        "055326464",
        "Mbeya University of Science and Technology",
    ),
    ("Institute of Fisheries Research - Zanzibar", "Tanzania", "LOCAL-0003", ""),
    ("Makerere University", "Uganda", "03dmz0111", "Makerere University"),
    ("Makerere University Business School", "Uganda", "LOCAL-0004", ""),
    ("Kyambogo University", "Uganda", "01wb6tr49", "Kyambogo University"),
    ("The Uganda National Institute of Teacher Education (UNITE)", "Uganda", "LOCAL-0005", ""),
    ("Uganda Christian University", "Uganda", "007pr2d48", "Uganda Christian University"),
    ("Gulu University", "Uganda", "042vepq05", "Gulu University"),
    ("Uganda Martyrs University", "Uganda", "04v4swe56", "Uganda Martyrs University"),
    ("University of Zambia", "Zambia", "03gh19d69", "University of Zambia"),
    ("University of Zimbabwe", "Zimbabwe", "04ze6rb18", "University of Zimbabwe"),
    (
        "University of Letters and Humanities",
        "",
        "LOCAL-0615",
        "",
    ),  # in the dropdown only; not identified (21 Oct 2026)
]


def table():
    """The list as a table: institution_name, country, ror_id, ror_name, institution_id."""
    d = pd.DataFrame(NORHED, columns=["institution_name", "country", "institution_id", "ror_name"])
    d["ror_id"] = d.institution_id.where(~d.institution_id.str.startswith("LOCAL-"), "")
    return d[["institution_name", "country", "ror_id", "ror_name", "institution_id"]]
