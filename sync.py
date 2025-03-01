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
    response = requests.get(f"{API_BASE_URL}/budgets/{budget_id}/transactions", headers=get_headers(api_key), params={"since_date": since_date})
    
    if response.status_code == 200:
        return response.json()["data"]["transactions"]
    else:
        print(response.text)
        sys.exit(1)

def identify_sync_transactions(from_transactions, to_transactions, split):
    valid_to_transactions = {}
    valid_from_transactions = {}

    for transaction in to_transactions:
        subtransactions = transaction.get("subtransactions")
        if len(subtransactions) != 2:
            continue

        for index, subtransaction in enumerate(subtransactions):
            payee_name = subtransaction.get("payee_name")
            split_amount = subtransaction.get("amount")

            if not payee_name or not "reimbursements" in payee_name.lower() or not split_amount > 0: continue
            fingerprint = f"{transaction.get('date')}_-{split_amount}"

            if "--" in fingerprint:
                print(f"double negative? {fingerprint}")
                sys.exit(1)

            if fingerprint in valid_to_transactions:
                print(f"duplicate transaction from {fingerprint}")
                sys.exit(1)

            valid_to_transactions[fingerprint] = transaction
            break

    for transaction in from_transactions:
        subtransactions = transaction.get("subtransactions")
        if len(subtransactions) != 2:
            continue

        for index, subtransaction in enumerate(subtransactions):
            payee_name = subtransaction.get("payee_name")
            split_amount = subtransaction.get("amount")

            if not payee_name or not "reimbursements" in payee_name.lower() or not split_amount < 0: continue
            fingerprint = f"{transaction.get('date')}_{split_amount}"
            calculated_ratio = round(((100 - split) / 100) * transaction.get("amount"), -1)

            if calculated_ratio != split_amount:
                print(f"Transaction amount does not match split amount. {fingerprint} {calculated_ratio}")
                sys.exit(1)

            if fingerprint in valid_from_transactions:
                print(f"duplicate transaction to {fingerprint}")
                sys.exit(1)

            if fingerprint in valid_to_transactions:
                print(f"skipping {fingerprint}")
                break

            valid_from_transactions[fingerprint] = transaction
            break

    print(f"valid from transactions: {valid_from_transactions.keys()}")

    return valid_from_transactions

def create_mirrored_transaction(
        transaction,
        to_bank_account_id,
        to_payee_reimbursements_id,
        to_category_reimbursements_id,
        to_payee_id,
        to_category_id
):
    subtransactions = transaction.get("subtransactions")
    for index, subtransaction in enumerate(subtransactions):
        if subtransaction.get("payee_name") and "Reimbursements".lower() in subtransaction.get("payee_name").lower():
            main_subtransaction = subtransactions[0] if index == 1 else subtransactions[1]
            date = transaction.get("date")
            payee = main_subtransaction.get("payee_name")
            split_amount = subtransaction.get("amount")
            memo = "SYNCED"

            if payee and "Reimbursements".lower() in payee.lower():
                print("this should not happen")
                sys.exit(1)

            if split_amount > 0:
                print("this should not happen")
                sys.exit(1)

            mirrored_transaction = {
                "account_id": to_bank_account_id,
                "date": date,
                "amount": 0,
                "cleared": "cleared",
                "approved": True,
                "memo": memo + ("" if to_payee_id else main_subtransaction.get("payee_name") if main_subtransaction.get("payee_name") else "NoPayee") + ("" if to_category_id else main_subtransaction.get("category_name") if main_subtransaction.get("category_name") else "NoCategory"),
                "subtransactions": [
                    {
                        "amount": split_amount * -1,
                        "payee_id": to_payee_reimbursements_id,
                        "category_id": to_category_reimbursements_id
                    },
                    {
                        "amount": split_amount,
                        "payee_id": to_payee_id,
                        "category_id": to_category_id
                    },
                ]
            }

            return mirrored_transaction

def sync_budgets():
    print("Starting YNAB budget sync for last 30 days...")
    since_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")

    person1_budget_details = get_budget(PERSON1_API_KEY, PERSON1_BUDGET_ID)
    person2_budget_details = get_budget(PERSON2_API_KEY, PERSON2_BUDGET_ID)

    person1_transactions = get_transactions(PERSON1_API_KEY, PERSON1_BUDGET_ID, since_date)
    person2_transactions = get_transactions(PERSON2_API_KEY, PERSON2_BUDGET_ID, since_date)

    person1_sync_transactions = identify_sync_transactions(person1_transactions, person2_transactions, int(PERSON1_SPLIT))
    person2_sync_transactions = identify_sync_transactions(person2_transactions, person1_transactions, 100 - int(PERSON1_SPLIT))

    if input(f"Is ok? (Y/N)").lower() != 'y': sys.exit(1)

    person1_mirrored_transactions = []

    for _, transaction in person1_sync_transactions:
        bank_account_id, payees, categories, payee_reimbursements_id, category_reimbursements_id = person2_budget_details

        subtransactions = transaction.get("subtransactions")

        for index, subtransaction in enumerate(subtransactions):
            if subtransaction.get("payee_name") and "Reimbursements".lower() in subtransaction.get("payee_name").lower():
                main_subtransaction = subtransactions[0] if index == 1 else subtransactions[1]
                payee = main_subtransaction.get("payee_name")
                category = main_subtransaction.get("category_name")

                to_payee = None
                to_category = None

                for candidate in payees:
                    if payee and payee.lower() in candidate["name"].lower():
                        to_payee = candidate["id"]
                        break

                for candidate in categories:
                    if category and category.lower() in candidate["name"].lower():
                        to_category = candidate["id"]
                        break

                person1_mirrored_transactions.append(create_mirrored_transaction(
                    transaction,
                    bank_account_id,
                    payee_reimbursements_id,
                    category_reimbursements_id,
                    to_payee,
                    to_category
                ))

                break

    print(person1_mirrored_transactions)

    if person1_mirrored_transactions:
        post_transactions(PERSON2_BUDGET_ID, PERSON2_API_KEY, person1_mirrored_transactions)

    person2_mirrored_transactions = []

    for transaction in person2_sync_transactions:
        bank_account_id, payees, categories, payee_reimbursements_id, category_reimbursements_id = person1_budget_details
        actual_transaction = person2_sync_transactions[transaction]

        subtransactions = actual_transaction.get("subtransactions")

        for index, subtransaction in enumerate(subtransactions):
            if subtransaction.get("payee_name") and "Reimbursements".lower() in subtransaction.get("payee_name").lower():
                main_subtransaction = subtransactions[0] if index == 1 else subtransactions[1]
                payee = main_subtransaction.get("payee_name")
                category = main_subtransaction.get("category_name")

                to_payee = None
                to_category = None

                for candidate in payees:
                    if payee and payee.lower() in candidate["name"].lower():
                        to_payee = candidate["id"]
                        break

                for candidate in categories:
                    if category and category.lower() in candidate["name"].lower():
                        to_category = candidate["id"]
                        break

                person2_mirrored_transactions.append(create_mirrored_transaction(
                    actual_transaction,
                    bank_account_id,
                    payee_reimbursements_id,
                    category_reimbursements_id,
                    to_payee,
                    to_category
                ))

                break

    print(person2_mirrored_transactions)

    if person2_mirrored_transactions:
        post_transactions(PERSON1_BUDGET_ID, PERSON1_API_KEY, person2_mirrored_transactions)

    print("Budget sync completed.")

def post_transactions(budget_id, api_key, transactions):
    response = requests.post(f"{API_BASE_URL}/budgets/{budget_id}/transactions", headers=get_headers(api_key), json={"transactions": transactions})

    if response.status_code == 201:
        print("Successfully created mirrored transactions")
    else:
        print(f"Error creating mirrored transaction: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    if not all([PERSON1_API_KEY, PERSON2_API_KEY, PERSON1_BUDGET_ID, PERSON2_BUDGET_ID]):
        print("Error: Missing environment variables. Please check your .env file.")
        print("Required variables: PERSON1_API_KEY, PERSON2_API_KEY, PERSON1_BUDGET_ID, PERSON2_BUDGET_ID")
        exit(1)
    
    sync_budgets()
