"""The patient data collection spec as data: every field the intake chat fills silently for the doctor.

The patient only sees a conversation; this schema is what the backend fills, validates, saves and shows to the
doctor. Kinds: bool, enum (options), multi (options), tags (free list), int / num (min, max), date, time, text (max),
list (rows of item fields), vital (a home reading with the device used and a reliability score, see VITALS).
Values the patient doesn't know are left empty, never guessed. Computed values (age, BMI, days since onset,
pack-years) are worked out by the server. Field ids follow the API contract (silent_form_updates).
"""


def F(fid, label, kind, section, **kw):
    return {"id": fid, "label": label, "kind": kind, "section": section, **kw}


def opts(*pairs):
    return [{"value": v, "label": l} for v, l in pairs]


SECTIONS = [
    {"id": "step0", "title": "Warning signs"},
    {"id": "phase2", "title": "Symptoms and timeline"},
    {"id": "toggles", "title": "Other symptoms (yes / no)"},
    {"id": "vitals", "title": "Home readings (with the device used)"},
    {"id": "phase3", "title": "Exposure, family history, medicines and past history"},
    {"id": "phase1", "title": "About the patient and their surroundings"},
    {"id": "phase4", "title": "Reports"},
    {"id": "phase5", "title": "Consent and preferences"},
]

# Step 0. A Yes stops the routine questions and shows the urgent-care message.
RED_FLAG_FIELDS = ["chest_pain", "severe_breathlessness", "confusion_fainting", "uncontrolled_bleeding",
                   "fluid_intolerance_low_urine", "seizure_or_stiff_neck"]

# Home readings: unit, valid range, and how a reading is written.
VITALS = {
    "highest_temp": {"label": "Highest temperature", "units": ["°F", "°C"], "range": {"°F": (93, 110), "°C": (34, 43.5)}},
    "home_temp": {"label": "Temperature now", "units": ["°F", "°C"], "range": {"°F": (93, 110), "°C": (34, 43.5)}},
    "home_bp": {"label": "Blood pressure", "units": ["mmHg"], "pattern": r"^\d{2,3}/\d{2,3}$"},
    "home_spo2": {"label": "Oxygen level (SpO₂)", "units": ["%"], "range": {"%": (50, 100)}},
    "home_hr": {"label": "Heart rate", "units": ["/min"], "range": {"/min": (20, 250)}},
    "home_glucose": {"label": "Blood sugar", "units": ["mg/dL"], "range": {"mg/dL": (20, 700)}},
}

SYMPTOM_TOGGLES_SPEC = [  # the 21 from the spec
    ("muscle_aches", "Muscle aches"), ("joint_pain", "Joint pain"), ("headache", "Headache"), ("sore_throat", "Sore throat"),
    ("cough", "Cough"), ("runny_nose", "Runny nose"), ("shortness_of_breath", "Shortness of breath"),
    ("chest_discomfort", "Chest discomfort"), ("abdominal_pain", "Stomach (abdominal) pain"), ("heartburn", "Heartburn or sour taste"),
    ("nausea_vomiting", "Nausea or vomiting"), ("diarrhea", "Loose motions (diarrhoea)"), ("constipation", "Constipation"),
    ("itching", "Itching"), ("skin_rash", "Skin rash"), ("mouth_ulcers", "Mouth ulcers"), ("jaundice_eyes_skin", "Yellow eyes or skin"),
    ("dark_urine", "Dark urine"), ("dysuria", "Burning when passing urine"), ("bleeding_gums_bruising", "Bleeding gums or nose, or easy bruising"),
    ("blood_in_stool_urine", "Blood in stool or urine"),
]
SYMPTOM_TOGGLES_EXTRA = [  # asked when the AI's (hidden) picture of the problem makes them useful to tell apart
    ("fatigue", "Tiredness or low energy"), ("weight_gain", "Weight gain"), ("cold_intolerance", "Feeling cold more than others"),
    ("heat_intolerance", "Feeling hot more than others"), ("hair_skin_changes", "Hair fall, or dry or changed skin"),
    ("neck_swelling", "Swelling in the front of the neck"), ("excessive_thirst", "Unusual thirst"), ("palpitations", "Racing or pounding heartbeat"),
    ("night_sweats", "Night sweats"), ("leg_swelling", "Swelling of the feet or legs"), ("vision_changes", "Changes in vision"),
    ("numbness_tingling", "Numbness or tingling"), ("weakness", "Weakness"),
]

FAMILY_CONDITIONS = ["Thyroid problem", "Diabetes", "High blood pressure", "Heart disease", "Stroke", "Cancer",
                     "Liver disease", "Kidney disease", "Tuberculosis", "Thalassemia or sickle cell", "Other genetic condition"]

FIELDS: list[dict] = [
    # ---- Step 0 ----
    F("chest_pain", "Chest pain or pressure right now", "bool", "step0", red_flag=True),
    F("severe_breathlessness", "Severe breathlessness", "bool", "step0", red_flag=True),
    F("confusion_fainting", "Confusion, drowsiness or fainting", "bool", "step0", red_flag=True),
    F("uncontrolled_bleeding", "Bleeding that won't stop, or vomiting blood", "bool", "step0", red_flag=True),
    F("fluid_intolerance_low_urine", "Can't keep fluids down, or passing very little urine", "bool", "step0", red_flag=True),
    F("seizure_or_stiff_neck", "Seizure, or stiff neck with fever", "bool", "step0", red_flag=True),
    # Asked for safety (medicines, X-rays) but not an emergency by itself: it never stops the intake.
    F("pregnancy_possible", "Pregnant, or could be pregnant", "bool", "step0", only_female=True),

    # ---- Phase 2 ----
    F("main_symptoms_narrative", "Main problem, in the patient's words", "text", "phase2", max=1000),
    F("onset_date", "Date the symptoms started", "date", "phase2"),
    F("onset_note", "When it started, in the patient's words", "text", "phase2", max=200),
    F("duration_days", "Days since it started", "int", "phase2", computed=True),
    F("trend", "Since it started", "enum", "phase2",
      options=opts(("getting_better", "Getting better"), ("same", "About the same"), ("worse", "Getting worse"), ("fluctuating", "Comes and goes"))),
    F("pain_severity_0_10", "Pain or discomfort (0-10)", "int", "phase2", min=0, max=10),
    F("pain_location", "Where the pain is", "text", "phase2", max=120),
    F("fever_present", "Fever", "bool", "phase2"),
    F("fever_pattern", "Fever pattern", "enum", "phase2",
      options=opts(("continuous", "Stays high all the time"), ("step_ladder", "Rises a little more each day"),
                   ("every_other_day", "Spikes every other day"), ("every_third_day", "Spikes every third day"),
                   ("two_phase", "Went away, then came back with bleeding"), ("not_sure", "Not sure"))),
    F("chills", "Chills or shivering", "bool", "phase2"),
    F("sweating", "Sweating", "bool", "phase2"),
    F("lightheadedness", "Light-headed on standing, or fainting", "bool", "phase2"),
    F("appetite", "Appetite", "enum", "phase2", options=opts(("normal", "Normal"), ("reduced", "Reduced"), ("absent", "None"))),
    F("weight_loss_3m", "Lost weight without trying (3 months)", "bool", "phase2"),
    F("weight_loss_kg", "About how many kg", "num", "phase2", min=0, max=60, only_if={"weight_loss_3m": True}),
    F("stools_per_day", "Stools per day", "int", "phase2", min=0, max=40),
    F("bristol_scale", "Stool type (Bristol 1-7)", "int", "phase2", min=1, max=7),
    F("urination_freq", "Times passing urine per day", "int", "phase2", min=0, max=40),
    F("fever_pattern_narrative", "Fever pattern, in the patient's words", "text", "phase2", max=500),
    F("other_noticed_changes", "Other changes noticed", "text", "phase2", max=500),
    F("lesion_or_rash_description", "Rash or skin change: where, colour, size, itch or pain", "text", "phase2", max=500),
    F("other_symptoms", "Other symptoms mentioned", "tags", "phase2", max_items=15),

    # ---- Yes / no symptoms ----
    *[F(fid, label, "bool", "toggles", symptom=True) for fid, label in SYMPTOM_TOGGLES_SPEC],
    *[F(fid, label, "bool", "toggles", symptom=True, extra=True) for fid, label in SYMPTOM_TOGGLES_EXTRA],

    # ---- Home readings (value + device + reliability) ----
    *[F(fid, v["label"], "vital", "vitals") for fid, v in VITALS.items()],

    # ---- Phase 3 ----
    F("travel_3d", "Travelled in the last 3 days", "bool", "phase3"),
    F("travel_3d_destination", "Where (last 3 days)", "text", "phase3", max=120, only_if={"travel_3d": True}),
    F("travel_30d_3m", "Travelled in the last 3 months", "bool", "phase3"),
    F("travel_30d_3m_destination", "Where (last 3 months)", "text", "phase3", max=120, only_if={"travel_30d_3m": True}),
    F("outside_food_72h", "Ate outside home in the last 3 days", "bool", "phase3"),
    F("meal_type", "What kind of food", "enum", "phase3", only_if={"outside_food_72h": True},
      options=opts(("street_food", "Street food"), ("restaurant", "Restaurant"), ("function", "Wedding or function"),
                   ("packaged", "Packaged food"), ("other", "Other"))),
    F("untreated_water", "Drank untreated or unboiled water", "bool", "phase3"),
    F("sick_contact", "Close contact with someone ill", "bool", "phase3"),
    F("household_sick_count", "People at home with similar symptoms", "int", "phase3", min=0, max=30),
    F("insect_animal_contact", "Insect bites or animal contact (2 weeks)", "bool", "phase3"),
    F("vaccinations", "Vaccines had", "multi", "phase3",
      options=opts(("typhoid", "Typhoid"), ("hep_a_b", "Hepatitis A/B"), ("influenza", "Influenza"), ("covid19", "COVID-19"), ("others", "Others"))),
    F("parental_and_family_history", "Parents' and family's illnesses", "list", "phase3", baseline=True,
      condition_hints=FAMILY_CONDITIONS,
      item_fields=[{"id": "relation", "label": "Relative", "kind": "text", "max": 40},
                   {"id": "condition", "label": "Condition", "kind": "text", "max": 100},
                   {"id": "age_at_onset", "label": "At what age", "kind": "text", "max": 20}]),
    F("family_history_none_known", "No illness known in parents or family", "bool", "phase3", baseline=True),
    F("family_history_changed", "Any new illness in the family since the last visit", "enum", "phase3", existing_only=True,
      options=opts(("no", "No"), ("yes", "Yes"), ("unsure", "Not sure"))),
    F("carrier_status", "Known carrier (e.g. thalassemia or sickle cell trait)", "bool", "phase3", baseline=True),
    F("carrier_type", "Which", "text", "phase3", max=80, baseline=True, only_if={"carrier_status": True}),
    F("chronic_conditions", "Long-term conditions", "multi", "phase3", baseline=True,
      options=opts(("diabetes", "Diabetes"), ("hypertension", "High blood pressure"), ("asthma", "Asthma"), ("copd", "COPD"),
                   ("thyroid", "Thyroid"), ("kidney", "Kidney disease"), ("liver", "Liver disease"), ("heart", "Heart disease"),
                   ("epilepsy", "Epilepsy"), ("others", "Others"), ("none", "None"))),
    F("current_medicines", "Medicines taken now", "list", "phase3", baseline=True,
      item_fields=[{"id": "drug_name", "label": "Medicine", "kind": "text", "max": 100},
                   {"id": "dose", "label": "Dose", "kind": "text", "max": 40},
                   {"id": "frequency", "label": "How often", "kind": "text", "max": 60},
                   {"id": "reason", "label": "For", "kind": "text", "max": 100}]),
    F("high_risk_drugs", "Taken in the last 30 days", "multi", "phase3",
      options=opts(("aspirin", "Aspirin"), ("nsaids", "Painkillers like ibuprofen or diclofenac"), ("metformin", "Metformin"),
                   ("steroids", "Steroids"), ("anticoagulants", "Blood thinners"), ("antibiotics_30d", "Antibiotics"), ("none", "None of these"))),
    F("otc_herbal", "Herbal, home or over-the-counter remedies", "bool", "phase3"),
    F("otc_herbal_names", "Which remedies", "text", "phase3", max=300, only_if={"otc_herbal": True}),
    F("drug_allergies", "Allergies (medicines, food, other)", "tags", "phase3", baseline=True, max_items=15),
    F("no_known_allergies", "No known allergies", "bool", "phase3", baseline=True),
    F("prior_surgeries", "Past operations", "list", "phase3", baseline=True,
      item_fields=[{"id": "type", "label": "Operation", "kind": "text", "max": 100}, {"id": "year", "label": "Year", "kind": "text", "max": 4}]),
    F("prior_hospitalizations", "Past hospital stays", "list", "phase3", baseline=True,
      item_fields=[{"id": "reason", "label": "Reason", "kind": "text", "max": 100}, {"id": "year", "label": "Year", "kind": "text", "max": 4}]),
    F("records_conditions_changed", "Long-term conditions since the last visit", "enum", "phase3", existing_only=True,
      options=opts(("no_change", "No change"), ("changed", "Something changed"), ("unsure", "Not sure"))),
    F("records_medicines_still_taking", "Taking the recorded medicines as prescribed", "enum", "phase3", existing_only=True,
      options=opts(("yes", "Yes, all"), ("missed", "Missed some doses"), ("changed", "Some stopped or changed"), ("unsure", "Not sure"))),
    F("outside_food_water_narrative", "Outside food or water, in the patient's words", "text", "phase3", max=500),

    # ---- Phase 1 ----
    F("gender", "Sex", "enum", "phase1", baseline=True, options=opts(("male", "Male"), ("female", "Female"), ("other", "Other"))),
    F("dob", "Date of birth", "date", "phase1", baseline=True),
    F("age", "Age", "int", "phase1", computed=True),
    F("height_cm", "Height (cm)", "num", "phase1", min=40, max=250, baseline=True),
    F("weight_kg", "Weight (kg)", "num", "phase1", min=2, max=300, baseline=True),
    F("bmi", "BMI", "num", "phase1", computed=True),
    F("location", "City, district or village", "text", "phase1", max=120, baseline=True),
    F("residence_type", "Area", "enum", "phase1", baseline=True,
      options=opts(("urban", "City"), ("semi_urban", "Small town"), ("rural", "Village"))),
    F("water_source", "Drinking water", "enum", "phase1", baseline=True,
      options=opts(("tap", "Tap"), ("borewell", "Borewell"), ("river", "River or pond"), ("filtered", "Filtered (RO/UV)"), ("bottled", "Bottled"))),
    F("occupation_category", "Work", "enum", "phase1", baseline=True,
      options=opts(("mining", "Mining"), ("textile", "Textile"), ("construction", "Construction"), ("agriculture", "Farming"),
                   ("office", "Office"), ("healthcare", "Healthcare"), ("student", "Student"), ("homemaker", "Homemaker"),
                   ("unemployed", "Not working"), ("other", "Other"))),
    F("years_in_occupation", "Years in this work", "int", "phase1", min=0, max=70, baseline=True),
    F("ppe_used", "Uses protective equipment at work", "bool", "phase1", baseline=True),
    F("work_exposure_note", "Work tasks and exposures (dust, chemicals, heat, noise, fumes)", "text", "phase1", max=500, baseline=True),
    F("smoking", "Smoking", "enum", "phase1", baseline=True, options=opts(("never", "Never"), ("former", "Used to"), ("current", "Yes, now"))),
    F("cigarettes_per_day", "Cigarettes or bidis per day", "num", "phase1", min=0, max=100, baseline=True, only_if={"smoking": ["current", "former"]}),
    F("smoking_years", "Years smoked", "num", "phase1", min=0, max=80, baseline=True, only_if={"smoking": ["current", "former"]}),
    F("pack_years", "Pack-years", "num", "phase1", computed=True),
    F("alcohol", "Alcohol", "enum", "phase1", baseline=True,
      options=opts(("none", "None"), ("occasional", "Occasionally"), ("regular", "Regularly"), ("quit", "Quit"))),
    F("alcohol_year_quit", "Year quit", "int", "phase1", min=1930, max=2100, baseline=True, only_if={"alcohol": ["quit"]}),
    F("substances", "Other substances", "multi", "phase1", baseline=True, sensitive=True,
      options=opts(("tobacco_chewing", "Chewing tobacco / gutka"), ("cannabis", "Cannabis"), ("opioids", "Opioids"), ("other", "Other"), ("none", "None"))),
    F("activity_level", "Physical activity", "enum", "phase1", baseline=True,
      options=opts(("sedentary", "Mostly sitting"), ("light", "Light"), ("moderate", "Moderate"), ("active", "Very active"))),
    F("diet_type", "Diet", "enum", "phase1", baseline=True,
      options=opts(("vegetarian", "Vegetarian"), ("non_vegetarian", "Non-vegetarian"), ("mixed", "Mixed"))),
    F("meal_timing", "Meal timing (late meals?)", "text", "phase1", max=120, baseline=True),
    F("spicy_fried_freq", "Spicy, fried or fatty food", "enum", "phase1", baseline=True,
      options=opts(("never", "Rarely"), ("weekly", "Weekly"), ("daily", "Daily"))),
    F("avg_sleep_hours", "Sleep (hours a night)", "num", "phase1", min=0, max=24, baseline=True),
    F("diet_note", "Eating habits, in the patient's words", "text", "phase1", max=300),

    # ---- Phase 4 ----
    F("last_known_labs", "Last known lab values (from uploaded reports)", "list", "phase4", readonly=True,
      item_fields=[{"id": "test", "label": "Test", "kind": "text"}, {"id": "value", "label": "Value", "kind": "text"},
                   {"id": "date", "label": "Date", "kind": "text"}]),
    F("rapid_tests_done", "Rapid tests already done", "multi", "phase4",
      options=opts(("malaria", "Malaria"), ("dengue_ns1_igm", "Dengue NS1/IgM"), ("typhoid", "Typhoid"), ("covid", "COVID"), ("none", "None"))),
    F("reports_to_upload", "Has reports or scans to upload", "bool", "phase4"),

    # ---- Phase 5 ----
    F("consent_processing", "Agreed: answers saved for care, profile updated", "bool", "phase5", baseline=True),
    F("sensitive_flags", "Keep private to the treating doctor", "multi", "phase5", baseline=True,
      options=opts(("sexual_health", "Sexual health"), ("substance_use", "Substance use"), ("mental_health", "Mental health"), ("none", "None"))),
    F("preferred_language", "Preferred language", "enum", "phase5", baseline=True,
      options=opts(("en", "English"), ("hi", "Hindi"), ("mr", "Marathi"), ("ta", "Tamil"), ("te", "Telugu"), ("bn", "Bengali"),
                   ("gu", "Gujarati"), ("kn", "Kannada"), ("ml", "Malayalam"), ("other", "Other"))),
]
BY_ID = {f["id"]: f for f in FIELDS}
SYMPTOM_TOGGLES = [f["id"] for f in FIELDS if f.get("symptom")]
PROBE_TOGGLES = [fid for fid, _ in SYMPTOM_TOGGLES_EXTRA]

# When a symptom (or fever) is Yes, these fields become relevant, in this order.
CLUSTERS: dict[str, list[str]] = {
    "fever": ["fever_pattern", "highest_temp", "chills", "sweating", "bleeding_gums_bruising", "skin_rash",
              "muscle_aches", "joint_pain", "headache", "insect_animal_contact", "travel_30d_3m",
              "untreated_water", "sick_contact", "household_sick_count", "appetite", "urination_freq"],
    "gi": ["stools_per_day", "bristol_scale", "nausea_vomiting", "blood_in_stool_urine", "pain_location",
           "outside_food_72h", "untreated_water", "household_sick_count", "appetite", "jaundice_eyes_skin",
           "spicy_fried_freq", "alcohol", "high_risk_drugs"],
    "respiratory": ["fever_present", "shortness_of_breath", "home_spo2", "sore_throat", "runny_nose", "sick_contact",
                    "smoking", "occupation_category", "work_exposure_note", "ppe_used"],
    "urinary": ["fever_present", "urination_freq", "blood_in_stool_urine", "pain_location", "dark_urine"],
    "skin": ["lesion_or_rash_description", "itching", "fever_present", "insect_animal_contact", "otc_herbal",
             "drug_allergies", "high_risk_drugs"],
    "liver": ["dark_urine", "appetite", "nausea_vomiting", "alcohol", "weight_loss_3m", "untreated_water", "outside_food_72h"],
    "pain": ["pain_severity_0_10", "pain_location", "home_bp"],
    "chest": ["pain_severity_0_10", "shortness_of_breath", "sweating", "palpitations", "smoking", "home_bp", "home_hr",
              "parental_and_family_history"],
    "metabolic": ["weight_gain", "cold_intolerance", "hair_skin_changes", "neck_swelling", "excessive_thirst",
                  "urination_freq", "home_glucose", "parental_and_family_history", "activity_level", "avg_sleep_hours"],
}
CLUSTER_TRIGGERS = {
    "fever": ["fever_present"], "gi": ["abdominal_pain", "diarrhea", "nausea_vomiting", "constipation", "heartburn"],
    "respiratory": ["cough", "sore_throat", "runny_nose", "shortness_of_breath"], "urinary": ["dysuria"],
    "skin": ["skin_rash", "itching", "mouth_ulcers"], "liver": ["jaundice_eyes_skin"],
    "pain": ["headache", "joint_pain", "muscle_aches", "abdominal_pain"], "chest": ["chest_discomfort", "palpitations"],
    "metabolic": ["fatigue", "weight_gain", "excessive_thirst", "cold_intolerance", "hair_skin_changes", "weakness"],
}
# Warning signs worth asking about for each kind of problem (asked naturally, one at a time; not a checklist).
CLUSTER_RED_FLAGS = {
    "fever": ["seizure_or_stiff_neck", "fluid_intolerance_low_urine", "confusion_fainting"],
    "gi": ["fluid_intolerance_low_urine", "uncontrolled_bleeding"],
    "respiratory": ["severe_breathlessness", "chest_pain"],
    "chest": ["chest_pain", "severe_breathlessness", "confusion_fainting"],
    "pain": ["seizure_or_stiff_neck", "confusion_fainting"],
    "liver": ["uncontrolled_bleeding", "confusion_fainting"],
    "urinary": ["fluid_intolerance_low_urine"],
    "metabolic": ["confusion_fainting"],
}
# Clusters where hereditary / metabolic conditions overlap: family history is asked early.
HEREDITARY_CLUSTERS = {"metabolic", "chest", "pain", "liver"}
CORE = ["main_symptoms_narrative", "onset_date", "trend"]
BASELINE_PRIORITY = ["gender", "dob", "drug_allergies", "current_medicines", "chronic_conditions",
                     "parental_and_family_history", "smoking", "alcohol", "height_cm", "weight_kg", "location",
                     "occupation_category", "residence_type", "water_source"]
CONSENT = ["consent_processing", "preferred_language"]

# Standard codes for the yes/no symptoms, from a FIXED table (the AI never makes codes up). For the doctor only.
# SNOMED CT concept ids and ICD-10 (WHO) codes; blank where no single code fits. Check them against the official
# SNOMED CT / ICD-10 releases before any clinical or billing use.
CODES: dict[str, tuple[str, str, str]] = {  # field -> (display, SNOMED CT, ICD-10)
    "fever_present": ("Fever", "386661006", "R50.9"), "headache": ("Headache", "25064002", "R51"),
    "cough": ("Cough", "49727002", "R05"), "sore_throat": ("Sore throat", "162397003", "R07.0"),
    "runny_nose": ("Rhinorrhoea", "64531003", ""), "shortness_of_breath": ("Dyspnoea", "267036007", "R06.0"),
    "chest_discomfort": ("Chest pain", "29857009", "R07.4"), "chest_pain": ("Chest pain", "29857009", "R07.4"),
    "abdominal_pain": ("Abdominal pain", "21522001", "R10.4"), "nausea_vomiting": ("Nausea and vomiting", "16932000", "R11"),
    "diarrhea": ("Diarrhoea", "62315008", ""), "constipation": ("Constipation", "14760008", "K59.0"),
    "heartburn": ("Heartburn", "16331000", "R12"), "itching": ("Pruritus", "418290006", "L29.9"),
    "skin_rash": ("Rash", "271807003", "R21"), "mouth_ulcers": ("Mouth ulcer", "26284000", ""),
    "jaundice_eyes_skin": ("Jaundice", "18165001", "R17"), "dysuria": ("Dysuria", "49650001", "R30.0"),
    "joint_pain": ("Joint pain", "57676002", "M25.5"), "muscle_aches": ("Myalgia", "68962001", "M79.1"),
    "chills": ("Chills", "43724002", ""), "sweating": ("Sweating", "415690000", ""),
    "severe_breathlessness": ("Dyspnoea (severe)", "267036007", "R06.0"),
    "fatigue": ("Fatigue", "84229001", "R53"), "palpitations": ("Palpitations", "80313002", "R00.2"),
    "excessive_thirst": ("Polydipsia", "17173007", "R63.1"), "weight_gain": ("Weight gain", "8943002", "R63.5"),
    "numbness_tingling": ("Paraesthesia", "91019004", "R20.2"), "night_sweats": ("Night sweats", "42984000", ""),
    "blood_in_stool_urine": ("Blood in stool or urine", "", ""), "bleeding_gums_bruising": ("Bleeding gums, nose bleed or bruising", "", ""),
    "dark_urine": ("Dark urine", "", ""), "seizure_or_stiff_neck": ("Seizure or neck stiffness with fever", "", ""),
}


def public_schema() -> dict:
    """The sections and fields (used by the doctor's views and the tests; the patient never sees the form)."""
    return {"sections": SECTIONS, "fields": FIELDS}
