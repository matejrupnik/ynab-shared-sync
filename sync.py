# TODO s for skip remove maybe,if no payee/category, just append to memo
# also either remove the last confirm prompt or make it glanceable
import json
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

class TerminalStyling:
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

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
        if transaction["flag_color"] != None or transaction["amount"] > 0: continue
        if "bank" not in transaction["account_name"].lower() and "cash" not in transaction["account_name"].lower():
            if "reimbursement" not in transaction["account_name"].lower():
                print(transaction)
                print("Transaction not in known account")
                sys.exit(1)
            else: continue
        valid_from_transactions.append(transaction)

    return valid_from_transactions

def calculate_amount(split, full_amount):
    return round((split / 100) * full_amount, -1)

def create_updated_transaction(
        transaction,
        from_reimbursements_payee_id,
        from_reimbursements_category_id,
        split
):
    return {
        "id": transaction["id"],
        "flag_color": "blue",
        "payee_id": None,
        "payee_name": None,
        "category_id": None,
        "category_name": None,
        "cleared": "cleared",
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

def create_mirrored_transaction(
        o_transaction,
        to_bank_account_id,
        to_reimbursements_payee_id,
        to_reimbursements_category_id,
        to_matched_payee_id,
        to_matched_category_id,
        split
):
    return {
        "flag_color": "purple",
        "account_id": to_bank_account_id,
        "date": o_transaction["date"],
        "cleared": "cleared",
        "approved": True,
        "memo": "SYNCED - " + o_transaction["memo"] if o_transaction["memo"] else '/',
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

def match(match_with, candidates, candidate_type):
    if match_with == "s": return None

    candidate_id = None
    for candidate in candidates:
        if match_with and match_with.lower() in candidate["name"].lower():
            candidate_id = candidate["id"]
            break

    if candidate_id is None:
        print(
            f"{TerminalStyling.YELLOW}Could not match {candidate_type} "
            f"name {TerminalStyling.RED}{match_with}{TerminalStyling.YELLOW}. Available candidates: {TerminalStyling.BLUE}"
        )
        print(chr(10).join(list(map(lambda x: x["name"], candidates))))
        return match(input(
            f"{TerminalStyling.GREEN}Please enter candidate name, or "
            f"'{TerminalStyling.BLUE}s{TerminalStyling.GREEN}' for skip:{chr(10)}"
        ), candidates, candidate_type)

    return candidate_id

def print_status(transaction, payees, categories):
    print("Split transaction with two subtransactions:")
    print(
        f"{TerminalStyling.ENDC}Subtransaction 1 payee:{TerminalStyling.GREEN}",
        next(
            (payee for payee in payees if payee["id"] == transaction["subtransactions"][0]["payee_id"]),
            {"name": None}
        )["name"]
    )
    print(
        f"{TerminalStyling.ENDC}Subtransaction 1 category:{TerminalStyling.GREEN}",
        next(
            (category for category in categories if category["id"] == transaction["subtransactions"][0]["category_id"]),
            {"name": None}
        )["name"]
    )
    print(f"{TerminalStyling.ENDC}Subtransaction 1 amount:{TerminalStyling.GREEN}", transaction["subtransactions"][0]["amount"])
    print(
        f"{TerminalStyling.ENDC}Subtransaction 2 payee:{TerminalStyling.GREEN}",
        next(
            (payee for payee in payees if payee["id"] == transaction["subtransactions"][1]["payee_id"]),
            {"name": None}
        )["name"]
    )
    print(
        f"{TerminalStyling.ENDC}Subtransaction 2 category:{TerminalStyling.GREEN}",
        next(
            (category for category in categories if category["id"] == transaction["subtransactions"][1]["category_id"]),
            {"name": None}
        )["name"]
    )
    print(f"{TerminalStyling.ENDC}Subtransaction 2 amount:{TerminalStyling.GREEN}", transaction["subtransactions"][0]["amount"])


def sync_budgets():
    print(
        f"{TerminalStyling.PURPLE}{chr(10) * 3}YNAB SYNC v3{chr(10) * 3}"
        f"{TerminalStyling.ENDC}Using this YNAB script requires you to follow a very delicate "
        f"process when importing transactions. {TerminalStyling.RED}Split transactions are currently not "
        f"supported and will probably break your YNAB!"
    )
    print(
        f"{TerminalStyling.ENDC}Person 1 should import a transaction they want to split with person 2 by "
        f"flagging it with a red flag. If the payee or category do not match on Person 2's side, Person 2 "
        f"will have to enter them manually. Memo is copied over. All of this goes both ways."
    )
    print(
        f"{TerminalStyling.ENDC}Only transactions with a red flag will be synced. Blue flag means it "
        f"was synced to the other side (or was attempted). Purple flag means the "
        f"transaction is a sync transaction."
    )
    since_date = (datetime.datetime.now() - datetime.timedelta(
        days=int(input(f"{TerminalStyling.BLUE}How many days back do you want to be synced?{chr(10)}"))
    )).strftime("%Y-%m-%d")

    (person1_bank_account_id,
     person1_payees,
     person1_categories,
     person1_payee_reimbursements_id,
     person1_category_reimbursements_id
     ) = get_budget(PERSON1_API_KEY, PERSON1_BUDGET_ID)

    (person2_bank_account_id,
     person2_payees,
     person2_categories,
     person2_payee_reimbursements_id,
     person2_category_reimbursements_id
     ) = get_budget(PERSON2_API_KEY, PERSON2_BUDGET_ID)

    person1_mirrored_transactions = []
    person1_updated_transactions = []
    person2_mirrored_transactions = []
    person2_updated_transactions = []

    will_be_processed_transactions_person_1 = get_transactions(PERSON1_API_KEY, PERSON1_BUDGET_ID, since_date)
    will_be_processed_transactions_person_2 = get_transactions(PERSON2_API_KEY, PERSON2_BUDGET_ID, since_date)

    for transaction in will_be_processed_transactions_person_1:
        to_payee = match(transaction.get("payee_name"), person2_payees, "payee")
        to_category = match(transaction.get("category_name"), person2_categories, "category")

        person1_updated_transactions.append(
            create_updated_transaction(
                transaction,
                person1_payee_reimbursements_id,
                person1_category_reimbursements_id,
                int(PERSON1_SPLIT)
            )
        )

        person1_mirrored_transactions.append(
            create_mirrored_transaction(
                transaction,
                person2_bank_account_id,
                person2_payee_reimbursements_id,
                person2_category_reimbursements_id,
                to_payee,
                to_category,
                100 - int(PERSON1_SPLIT)
            )
        )

    for transaction in will_be_processed_transactions_person_2:
        to_payee = match(transaction.get("payee_name"), person1_payees, "payee")
        to_category = match(transaction.get("category_name"), person1_categories, "category")

        person2_updated_transactions.append(
            create_updated_transaction(
                transaction,
                person2_payee_reimbursements_id,
                person2_category_reimbursements_id,
                100 - int(PERSON1_SPLIT)
            )
        )

        person2_mirrored_transactions.append(
            create_mirrored_transaction(
                transaction,
                person1_bank_account_id,
                person1_payee_reimbursements_id,
                person1_category_reimbursements_id,
                to_payee,
                to_category,
                int(PERSON1_SPLIT)
            )
        )

    print(f"{TerminalStyling.BLUE}Updated Person 1 transactions:{TerminalStyling.YELLOW}")
    for transaction in person1_updated_transactions:
        print_status(transaction, person1_payees, person1_categories)

    print(f"{TerminalStyling.BLUE}Synced Person 1 transactions:{TerminalStyling.YELLOW}")
    for transaction in person1_mirrored_transactions:
        print_status(transaction, person2_payees, person2_categories)

    print(f"{TerminalStyling.BLUE}Updated Person 2 transactions:{TerminalStyling.YELLOW}")
    for transaction in person2_updated_transactions:
        print_status(transaction, person2_payees, person2_categories)

    print(f"{TerminalStyling.BLUE}Synced Person 2 transactions:{TerminalStyling.YELLOW}")
    for transaction in person2_mirrored_transactions:
        print_status(transaction, person1_payees, person1_categories)

    if input(f"Ok? (Y/N){chr(10)}").lower() != 'y': sys.exit(1)

    with open("history.txt", "a") as f:
        f.write(f"{chr(10)}Person 1 processed transactions:{chr(10)}")
        f.write(json.dumps(will_be_processed_transactions_person_1))
        f.write(f"{chr(10)}Person 2 processed transactions:{chr(10)}")
        f.write(json.dumps(will_be_processed_transactions_person_2))

    if person1_updated_transactions and person1_mirrored_transactions:
        patch_transactions(PERSON1_BUDGET_ID, PERSON1_API_KEY, person1_updated_transactions)
        post_transactions(PERSON2_BUDGET_ID, PERSON2_API_KEY, person1_mirrored_transactions)
    if person2_updated_transactions and person2_mirrored_transactions:
        patch_transactions(PERSON2_BUDGET_ID, PERSON2_API_KEY, person2_updated_transactions)
        post_transactions(PERSON1_BUDGET_ID, PERSON1_API_KEY, person2_mirrored_transactions)

    print(f"{TerminalStyling.CYAN}Budget sync completed.")

def patch_transactions(budget_id, api_key, transactions):
    response = requests.patch(
        f"{API_BASE_URL}/budgets/{budget_id}/transactions",
        headers=get_headers(api_key),
        json={"transactions": transactions}
    )

    if response.status_code == 200:
        print(
            f"{TerminalStyling.ENDC}Successfully patched existing transactions. "
            f"{TerminalStyling.RED}IF MIRRORING FAILED, REVERT THE NEW TRANSACTIONS MANUALLY{TerminalStyling.ENDC}"
        )
    else:
        print(f"Error patching existing transaction: {response.status_code}")
        print(response.text)

def post_transactions(budget_id, api_key, transactions):
    response = requests.post(
        f"{API_BASE_URL}/budgets/{budget_id}/transactions",
        headers=get_headers(api_key),
        json={"transactions": transactions}
    )

    if response.status_code == 201:
        print(
            f"{TerminalStyling.ENDC}Successfully created mirrored transactions. "
            f"{TerminalStyling.RED}IF PATCHING FAILED, REVERT THE NEW TRANSACTIONS MANUALLY{TerminalStyling.ENDC}"
        )
    else:
        print(f"Error creating mirrored transactions: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    if not all([PERSON1_API_KEY, PERSON2_API_KEY, PERSON1_BUDGET_ID, PERSON2_BUDGET_ID, PERSON1_SPLIT]):
        print(
            "Missing .env variables: "
            "PERSON1_API_KEY, PERSON2_API_KEY, PERSON1_BUDGET_ID, PERSON2_BUDGET_ID, PERSON1_SPLIT"
        )
        sys.exit(1)

    sync_budgets()