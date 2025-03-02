# YNAB Sync Tool (HIGHLY UNSTABLE AND UNTESTED)

This tool helps two people synchronize their YNAB (You Need A Budget) accounts by automatically splitting and mirroring transactions between their budgets.

## What This Tool Does

When you and another person (like a partner, roommate, or family member) share expenses, this tool makes it easy to:

1. Split a transaction between two YNAB budgets according to a predetermined percentage
2. Update the original transaction in the first person's budget, to record the split
3. Create a matching transaction in the second person's budget for their portion

## Account Setup Requirements

Before using this tool, both parties need to set up specific accounts in YNAB:

1. **Bank account**: Both parties need to have an account named "Bank" in YNAB. This is the main account where the synced transactions will be created.

2. **Reimbursements account**: Both parties need a tracking liability account named "Reimbursements". This account will track how much each person owes the other.

3. **Reimbursements category**: Both parties need a category named "Reimbursements". This category is used for transfers between the Bank and Reimbursements accounts.

### Understanding the Debt Balance

The Reimbursements account balance shows your debt relationship with the other person:

- **Negative balance** (-50): You owe the other person money
- **Positive balance** (+50): The other person owes you money

The numbers in both parties' Reimbursements accounts should be exactly the same amount but with opposite signs. For example, if Person 1 has +\$75, Person 2 should have -\$75.

### Why This Approach

This setup eliminates the need to send money back and forth constantly:

1. **No monthly settlements needed**: You don't need to send money at the end of the month if you owe the other party
2. **Natural balancing**: If you owe the other person, they can simply spend more on shared expenses, and the balance will naturally even out over time
3. **Continuous tracking**: You always know exactly where you stand financially with each other
4. **Reduced transaction costs**: No fees for transferring money between accounts
5. **Simplified financial relationship**: The system works well for couples or roommates who share many expenses

This approach works best when both parties spend roughly similar amounts over time, allowing the balance to naturally correct itself through regular spending patterns.

## Prerequisites

- Two YNAB accounts (one for each person)
- Python installed on your computer
- Basic understanding of terminal/command line

## Setup Instructions

### 1. Install Required Python Packages

Open your terminal/command line and run:

```
pip install requests python-dotenv
```

### 2. Create a .env File

In the same folder as the script, create a file named `.env` with the following content:

```
PERSON1_API_KEY=[Person 1's API key]
PERSON2_API_KEY=[Person 2's API key]
PERSON1_BUDGET_ID=[Person 1's budget ID]
PERSON2_BUDGET_ID=[Person 2's budget ID]
PERSON1_SPLIT=[Percentage split for Person 1]
```

#### How to Get Your API Key

1. Log in to your YNAB account
2. Click on your account in the top-left corner
3. Select "Account Settings"
4. Scroll down to "Developer Settings"
5. Click "New Token" and give it a name (e.g., "Sync Tool")
6. Copy the generated token - this is your API key

#### How to Get Your Budget ID

1. Log in to your YNAB account
2. Open the budget you want to use
3. Look at the URL in your browser
4. The budget ID is the long string of characters after `/budgets/`
   Example: In `https://app.ynab.com/12345abc-def6-7890-ghij-klmnopqrstuv/budget`, the budget ID is `12345abc-def6-7890-ghij-klmnopqrstuv`

#### Setting the Split Percentage

The `PERSON1_SPLIT` value determines how expenses are divided between the two people. It should be a number between 1 and 99.

Example:
- If set to `60`, Person 1 pays 60% of each transaction and Person 2 pays 40%
- If set to `50`, expenses are split 50/50

## How to Use the Tool

### Step 1: Prepare Your Transactions

Before running the script:

1. In your YNAB account, import or enter the transaction you want to split
2. Flag the transaction with a RED flag (this tells the script which transactions to process)

### Step 2: Run the Script

1. Open your terminal/command line
2. Navigate to the folder containing the script
3. Run the script by typing:
   ```
   python sync.py
   ```

### Step 3: Follow the Prompts

1. The script will ask how many days back you want to look for transactions to sync
2. For each transaction with a red flag, it will show you the details and ask for confirmation
3. If a payee or category in one budget doesn't match the other budget, you'll be asked to select a matching one or skip
4. Review the changes that will be made and confirm by typing 'y'

## Understanding the Flags

The script uses colored flags to track the status of transactions:

- **Red Flag**: A transaction that needs to be processed (you set this manually)
- **Blue Flag**: A transaction that has been processed and updated with the split
- **Purple Flag**: A mirrored transaction created in the other person's budget

## Important Notes

- **Be careful with split transactions**: The script currently doesn't support transactions that are already split in YNAB
- **Review before confirming**: Always check the details before confirming with 'y'
- **Manual reversal may be needed**: If something goes wrong, you may need to manually delete or adjust transactions. A JSON structure of relevant transactions is stored in history.txt file.

## How It Works Behind the Scenes

1. The script connects to both YNAB accounts using the provided API keys
2. It finds all transactions flagged red within the specified date range
3. For each transaction:
   - It updates the original transaction in the first budget, splitting it between the actual expense and a "Reimbursements" category
   - It creates a new transaction in the second budget with two parts: the person's portion of the expense and a corresponding "Reimbursements" entry
4. After processing, red flags are changed to blue (processed) and new transactions are marked with purple flags

## Troubleshooting

- **Missing variables error**: Make sure your .env file contains all required values
- **API connection errors**: Check that your API keys are correct and not expired
- **Matching errors**: If the script can't find a matching payee or category, it will ask you to provide one