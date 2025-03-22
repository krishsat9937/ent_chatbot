import requests
import json
import time
import logging

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# API Endpoints
EVENT_API_URL = "https://api.fda.gov/drug/event.json"
LABEL_API_URL = "https://api.fda.gov/drug/label.json"

# Headers
HEADERS = {"accept": "application/json"}

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
TIME_LAG = 1.5  # Time delay between API requests

# Load ENT Problems from JSON file
def load_ent_problems(filename="ent_problems.json"):
    """Loads the ENT problems from an external JSON file."""
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
    "dosage_forms_and_strengths", "contraindications",
    "warnings_and_cautions", "adverse_reactions",
    "drug_interactions", "use_in_specific_populations",
    "drug_abuse_and_dependence", "overdosage",
    "description", "clinical_pharmacology",
    "clinical_studies", "how_supplied"
]

def fetch_drugs_for_ent_problem(ent_problem):
    """Fetches a list of drugs associated with a given ENT problem."""
    params = {
        "search": f"patient.drug.drugindication:\"{ent_problem}\"",
        "count": "patient.drug.openfda.generic_name.exact"
    }

    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Fetching drugs for ENT problem: {ent_problem} (Attempt {attempt+1})")
            response = requests.get(EVENT_API_URL, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return [entry["term"] for entry in data.get("results", [])]
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching drugs for {ent_problem} (Attempt {attempt+1}): {e}")
            time.sleep(RETRY_DELAY)

    return []  # Return empty list on failure

def fetch_drug_label(drug_name):
    """Fetches structured drug label details for a given generic drug name."""
    params = {"search": f"openfda.generic_name:\"{drug_name}\"", "limit": 1}

    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Fetching label for drug: {drug_name} (Attempt {attempt+1})")
            response = requests.get(LABEL_API_URL, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "results" in data:
                label_data = data["results"][0]
                return {field: label_data.get(field, "N/A") for field in LABEL_FIELDS}  # Filter relevant fields
            return {}
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching label for {drug_name} (Attempt {attempt+1}): {e}")
            time.sleep(RETRY_DELAY)

    return {}  # Return empty dict on failure

def create_ent_drug_dataset():
    """Runs the full ingestion pipeline: fetch drug list for ENT problems, get details, save to JSON."""
    ent_drug_data = {}

    for ent_problem in ENT_PROBLEMS:
        logging.info(f"Processing ENT problem: {ent_problem}")
        drugs = fetch_drugs_for_ent_problem(ent_problem)
        logging.info(f"Found {len(drugs)} drugs for {ent_problem}")

        drug_info = {}
        for drug in drugs:
            logging.info(f"Fetching details for drug: {drug}")
            label_info = fetch_drug_label(drug)
            drug_info[drug] = label_info
            logging.info(f"Successfully retrieved label info for {drug}")
            time.sleep(TIME_LAG)  # Avoid API rate limits

        ent_drug_data[ent_problem] = drug_info
        logging.info(f"Completed processing for {ent_problem}")
        time.sleep(TIME_LAG * 2)  # Additional delay between ENT problem requests

    # Save to JSON
    with open("ent_drug_data.json", "w") as f:
        json.dump(ent_drug_data, f, indent=2)
    
    logging.info("ENT drug data ingestion complete. Data saved to ent_drug_data.json")

if __name__ == "__main__":
    create_ent_drug_dataset()
