import requests
import json
import time
import logging

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# API Endpoint
LABEL_API_URL = "https://api.fda.gov/drug/label.json"

# Headers
HEADERS = {
    "accept": "application/json",
    "User-Agent": "ENTDrugFetcher/1.0"
}

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
TIME_LAG = 1.5  # Time delay between API requests

# Load ENT Problems from JSON file
def load_ent_problems(filename="ent_problems.json"):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading ENT problems file: {e}")
        return []

ENT_PROBLEMS = load_ent_problems()

# Drug Label Fields to Extract
LABEL_FIELDS = [
    "indications_and_usage", "dosage_and_administration",
    "contraindications", "warnings_and_cautions",
    "adverse_reactions", "drug_interactions",
    "use_in_specific_populations", "description",
    "clinical_pharmacology"
]

def fetch_drugs_for_ent_problem(ent_problem, limit=10):
    """Fetches drugs mentioning the ENT condition in their indications_and_usage."""
    params = {
        "search": f"indications_and_usage:\"{ent_problem}\"",
        "limit": limit
    }

    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"🔍 Fetching drugs for ENT problem: {ent_problem} (Attempt {attempt+1})")
            response = requests.get(LABEL_API_URL, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            drugs = []

            for result in data.get("results", []):
                generic_names = result.get("openfda", {}).get("generic_name", [])
                if not generic_names:
                    logging.info(f"⚠️ Skipping result with missing generic_name for {ent_problem}")
                    continue
                drugs.extend(generic_names)
                if len(drugs) >= limit:
                    break

            return list(set(drugs))[:limit]

        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching drugs for {ent_problem} (Attempt {attempt+1}): {e}")
            time.sleep(RETRY_DELAY)

    return []

def fetch_drug_label(drug_name):
    """Fetches structured drug label details for a given generic drug name."""
    params = {"search": f"openfda.generic_name:\"{drug_name}\"", "limit": 1}

    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"📖 Fetching label for drug: {drug_name} (Attempt {attempt+1})")
            response = requests.get(LABEL_API_URL, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "results" in data:
                label_data = data["results"][0]
                return {field: label_data.get(field, "N/A") for field in LABEL_FIELDS}

            return {}

        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching label for {drug_name} (Attempt {attempt+1}): {e}")
            time.sleep(RETRY_DELAY)

    return {}

def is_ent_relevant(label_info):
    """Quick check to confirm ENT relevance based on label content."""
    ENT_KEYWORDS = ["ear", "nose", "throat", "hearing", "tinnitus", "vertigo", "dizziness", "otitis", "rhinitis"]
    combined_info = " ".join([str(label_info.get(field, "")) for field in LABEL_FIELDS])
    return any(keyword in combined_info.lower() for keyword in ENT_KEYWORDS)

def create_ent_drug_dataset():
    ent_drug_data = {}

    for ent_problem in ENT_PROBLEMS:
        try:
            logging.info(f"🔬 Processing ENT problem: {ent_problem}")
            drugs = fetch_drugs_for_ent_problem(ent_problem, limit=10)
            logging.info(f"✅ Found {len(drugs)} drugs for {ent_problem}")

            drug_info = {}
            for drug in drugs:
                label_info = fetch_drug_label(drug)

                if is_ent_relevant(label_info):
                    drug_info[drug] = label_info
                    logging.info(f"✔️ Relevant drug added: {drug}")
                else:
                    logging.info(f"🚫 Skipped irrelevant drug: {drug}")

                time.sleep(TIME_LAG)

            ent_drug_data[ent_problem] = drug_info
            logging.info(f"🏁 Completed {ent_problem}")

            # Save intermediate progress
            with open("ent_drug_data.json", "w") as f:
                json.dump(ent_drug_data, f, indent=2)

            time.sleep(TIME_LAG * 2)
        except Exception as e:
            logging.error(f"🔥 Failed to process {ent_problem}: {e}")
            continue

    logging.info("🎉 ENT drug data ingestion complete. Saved to ent_drug_data.json")

if __name__ == "__main__":
    create_ent_drug_dataset()
