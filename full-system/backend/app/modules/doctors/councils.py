"""Medical councils a doctor can be registered with (NMC + State Medical Councils).

`match` = words that should appear on that council's registration certificate (used by the document check).
"""

NMC_REGISTER_URL = "https://www.nmc.org.in/?p=191"  # NMC Indian Medical Register search (manual check by the admin)

COUNCILS = {
    "NMC": ("National Medical Commission (Indian Medical Register)", ["national medical commission", "medical council of india", "indian medical register"]),
    "AP": ("Andhra Pradesh Medical Council", ["andhra pradesh"]),
    "AR": ("Arunachal Pradesh Medical Council", ["arunachal"]),
    "AS": ("Assam Medical Council", ["assam"]),
    "BR": ("Bihar Medical Council", ["bihar"]),
    "CG": ("Chhattisgarh Medical Council", ["chhattisgarh"]),
    "DL": ("Delhi Medical Council", ["delhi"]),
    "GA": ("Goa Medical Council", ["goa"]),
    "GJ": ("Gujarat Medical Council", ["gujarat"]),
    "HR": ("Haryana Medical Council", ["haryana"]),
    "HP": ("Himachal Pradesh Medical Council", ["himachal"]),
    "JK": ("Jammu & Kashmir Medical Council", ["jammu", "kashmir"]),
    "JH": ("Jharkhand Medical Council", ["jharkhand"]),
    "KA": ("Karnataka Medical Council", ["karnataka"]),
    "KL": ("Travancore-Cochin Medical Council (Kerala)", ["travancore", "kerala"]),
    "MP": ("Madhya Pradesh Medical Council", ["madhya pradesh"]),
    "MH": ("Maharashtra Medical Council", ["maharashtra"]),
    "MN": ("Manipur Medical Council", ["manipur"]),
    "ML": ("Meghalaya Medical Council", ["meghalaya"]),
    "MZ": ("Mizoram Medical Council", ["mizoram"]),
    "NL": ("Nagaland Medical Council", ["nagaland"]),
    "OD": ("Odisha Council of Medical Registration", ["odisha", "orissa"]),
    "PB": ("Punjab Medical Council", ["punjab"]),
    "RJ": ("Rajasthan Medical Council", ["rajasthan"]),
    "SK": ("Sikkim Medical Council", ["sikkim"]),
    "TN": ("Tamil Nadu Medical Council", ["tamil nadu"]),
    "TS": ("Telangana State Medical Council", ["telangana"]),
    "TR": ("Tripura State Medical Council", ["tripura"]),
    "UP": ("Uttar Pradesh Medical Council", ["uttar pradesh"]),
    "UK": ("Uttarakhand Medical Council", ["uttarakhand", "uttaranchal"]),
    "WB": ("West Bengal Medical Council", ["west bengal"]),
}


def options() -> list[dict]:
    return [{"value": k, "label": v[0]} for k, v in COUNCILS.items()]


def name(code: str) -> str:
    return COUNCILS.get(code, (code, []))[0]
