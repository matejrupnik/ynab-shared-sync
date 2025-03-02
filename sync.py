import sys
import requests
import datetime
import os
import dotenv

dotenv.load_dotenv()

API_BASE_URL = "https://api.ynab.com/v1"

PERSON1_API_KEY = os.getenv("PERSON1_API_KEY")
PERSON2_API_KEY = os.getenv("PERSON2_API_KEY")
PERSON1_BUDGET_ID = os.getenv("PERSON1_BUDGET_ID")
PERSON2_BUDGET_ID = os.getenv("PERSON2_BUDGET_ID")
PERSON1_SPLIT = os.getenv("PERSON1_SPLIT")

# class terminal_styling:
#     HEADER = '\033[95m'
#     OKBLUE = '\033[94m'
#     OKCYAN = '\033[96m'
#     OKGREEN = '\033[92m'
#     WARNING = '\033[93m'
#     FAIL = '\033[91m'
#     ENDC = '\033[0m'
#     BOLD = '\033[1m'
#     UNDERLINE = '\033[4m'

def get_headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

def get_budget(api_key, budget_id):
    response = requests.get(f"{API_BASE_URL}/budgets/{budget_id}", headers=get_headers(api_key))
    if not response.status_code == 200:
        print(response.text)
        sys.exit(1)

    budget = response.json()["data"]["budget"]
    categories = budget["categories"]
    payees = budget["payees"]
    accounts = budget["accounts"]

    bank_account_id = ""
    payee_reimbursements_id = ""
    category_reimbursements_id = ""

    for account in accounts:
        if account["name"].lower() == "Bank".lower():
            bank_account_id = account["id"]
            break

    for payee in payees:
        if payee["name"] and "Reimbursements".lower() in payee["name"].lower():
            payee_reimbursements_id = payee["id"]
            break

    for category in categories:
        if category["name"] and "Reimbursements".lower() in category["name"].lower():
            category_reimbursements_id = category["id"]
            break

    return bank_account_id, payees, categories, payee_reimbursements_id, category_reimbursements_id

def get_transactions(api_key, budget_id, since_date):
    response = requests.get(f"{API_BASE_URL}/budgets/{budget_id}/transactions", headers=get_headers(api_key),
                            params={"since_date": since_date})

    if response.status_code != 200:
        print(response.text)
        sys.exit(1)

    valid_from_transactions = []

    for transaction in response.json()["data"]["transactions"]:
        if transaction["flag_color"] != "red": continue
        valid_from_transactions.append(transaction)
        break

    return valid_from_transactions

def calculate_amount(split, full_amount):
    return round((split / 100) * full_amount, -1)

def create_updated_transaction(transaction, from_reimbursements_payee_id, from_reimbursements_category_id, split):
    return {
        "id": transaction["id"],
        "flag_color": "blue",
        "payee_id": None,
        "payee_name": None,
        "category_id": None,
        "category_name": None,
        "subtransactions": [
            {
                "payee_id": transaction["payee_id"],
                "category_id": transaction["category_id"],
                "amount": int(calculate_amount(split, transaction["amount"])),
            },
            {
                "payee_id": from_reimbursements_payee_id,
                "category_id": from_reimbursements_category_id,
                "amount": int(calculate_amount(100 - split, transaction["amount"])),
            }
        ],
    }

def create_mirrored_transaction(o_transaction, to_bank_account_id, to_reimbursements_payee_id, to_reimbursements_category_id, to_matched_payee_id, to_matched_category_id, split):
    return {
        "flag_color": "purple",
        "account_id": to_bank_account_id,
        "date": o_transaction["date"],
        "cleared": "cleared",
        "approved": True,
        "memo": "SYNCED - " + o_transaction["memo"],
        "amount": 0,
        "subtransactions": [
            {
                "payee_id": to_reimbursements_payee_id,
                "category_id": to_reimbursements_category_id,
                "amount": int(calculate_amount(split, o_transaction["amount"]) * -1)
            },
            {
                "payee_id": to_matched_payee_id,
                "category_id": to_matched_category_id,
                "amount": int(calculate_amount(split, o_transaction["amount"]))
            }
        ],
    }

def match(match_with, candidates):
    if match_with == "s": return None

    candidate = None
    for candidate in candidates:
        if match_with and match_with.lower() in candidate["name"].lower():
            candidate = candidate["id"]
            break

    if candidate is None:
        print(f"could not match candidate (payee/category) name {match_with}. options: ")
        print(list(map(lambda x: x["name"], candidates)))
        match(input(f"please enter payee name, or 's' for skip: "), candidates)

    return candidate

def sync_budgets():
    print("Starting YNAB budget sync for last 30 days...")
    since_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")

    person1_budget_details = get_budget(PERSON1_API_KEY, PERSON1_BUDGET_ID)
    person2_budget_details = get_budget(PERSON2_API_KEY, PERSON2_BUDGET_ID)

    person1_sync_transactions = get_transactions(PERSON1_API_KEY, PERSON1_BUDGET_ID, since_date)
    person2_sync_transactions = get_transactions(PERSON2_API_KEY, PERSON2_BUDGET_ID, since_date)

    person1_bank_account_id, person1_payees, person1_categories, person1_payee_reimbursements_id, person1_category_reimbursements_id = person1_budget_details
    person2_bank_account_id, person2_payees, person2_categories, person2_payee_reimbursements_id, person2_category_reimbursements_id = person2_budget_details

    person1_mirrored_transactions = []
    person1_updated_transactions = []
    person2_mirrored_transactions = []
    person2_updated_transactions = []

    for transaction in person1_sync_transactions:
        to_payee = match(transaction.get("payee_name"), person2_payees)
        to_category = match(transaction.get("category_name"), person2_categories)

        person1_updated_transactions.append(create_updated_transaction(transaction, person1_payee_reimbursements_id, person1_category_reimbursements_id, int(PERSON1_SPLIT)))
        person1_mirrored_transactions.append(create_mirrored_transaction(transaction, person2_bank_account_id, person2_payee_reimbursements_id, person2_category_reimbursements_id, to_payee, to_category, 100 - int(PERSON1_SPLIT)))

    for transaction in person2_sync_transactions:
        to_payee = match(transaction.get("payee_name"), person1_payees)
        to_category = match(transaction.get("category_name"), person1_categories)

        person2_updated_transactions.append(create_updated_transaction(transaction, person2_payee_reimbursements_id, person2_category_reimbursements_id, 100 - int(PERSON1_SPLIT)))
        person2_mirrored_transactions.append(create_mirrored_transaction(transaction, person1_bank_account_id, person1_payee_reimbursements_id, person1_category_reimbursements_id, to_payee, to_category, int(PERSON1_SPLIT)))

    print(person1_updated_transactions, person1_mirrored_transactions, person2_updated_transactions, person2_mirrored_transactions)

    if input(f"Is ok? (Y/N)").lower() != 'y': sys.exit(1)

    if person1_updated_transactions and person1_mirrored_transactions:
        patch_transactions(PERSON1_BUDGET_ID, PERSON1_API_KEY, person1_updated_transactions)
        post_transactions(PERSON2_BUDGET_ID, PERSON2_API_KEY, person1_mirrored_transactions)
    if person2_updated_transactions and person2_mirrored_transactions:
        patch_transactions(PERSON2_BUDGET_ID, PERSON2_API_KEY, person2_updated_transactions)
        post_transactions(PERSON1_BUDGET_ID, PERSON1_API_KEY, person2_mirrored_transactions)

    print("Budget sync completed.")

def patch_transactions(budget_id, api_key, transactions):
    response = requests.patch(f"{API_BASE_URL}/budgets/{budget_id}/transactions", headers=get_headers(api_key), json={"transactions": transactions})

    if response.status_code == 200:
        print("Successfully patched existing transactions. IF MIRRORING FAILED, REVERT THE NEW TRANSACTIONS MANUALLY")
    else:
        print(f"Error patching existing transaction: {response.status_code}")
        print(response.text)

def post_transactions(budget_id, api_key, transactions):
    response = requests.post(f"{API_BASE_URL}/budgets/{budget_id}/transactions", headers=get_headers(api_key), json={"transactions": transactions})

    if response.status_code == 201:
        print("Successfully created mirrored transactions. IF PATCHING FAILED, REVERT THE NEW TRANSACTIONS MANUALLY")
    else:
        print(f"Error creating mirrored transactions: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    if not all([PERSON1_API_KEY, PERSON2_API_KEY, PERSON1_BUDGET_ID, PERSON2_BUDGET_ID]):
        print("Missing .env variables: PERSON1_API_KEY, PERSON2_API_KEY, PERSON1_BUDGET_ID, PERSON2_BUDGET_ID")
        sys.exit(1)

    sync_budgets()