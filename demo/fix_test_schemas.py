"""
Fix test case JSON files to match IntentContract schema.
"""
import json
import re
from pathlib import Path


def fix_test_case(filepath):
    """Fix test case to match IntentContract schema."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Extract intent_contract
    contract = data['intent_contract']

    # Add contract_id and goal if missing
    if 'contract_id' not in contract:
        contract['contract_id'] = data['test_id'].lower().replace('-', '_')

    if 'goal' not in contract:
        contract['goal'] = data['user_intent']

    # Fix resource_scope - convert list to object
    if isinstance(contract.get('resource_scope'), list):
        resource_list = contract['resource_scope']

        # Default structure
        contract['resource_scope'] = {
            "transaction_ids": [],
            "account_ids": [],
            "allowed_scope_expansion": False
        }

        # For banking, use transaction IDs directly
        if data['domain'] == 'banking':
            contract['resource_scope']['transaction_ids'] = resource_list

        # For retail, extract order IDs from user intent
        elif data['domain'] == 'retail':
            match = re.search(r'#(ORD-\d+)', data['user_intent'])
            if match:
                contract['resource_scope']['transaction_ids'] = [match.group(1)]

        # For airline, extract booking IDs from user intent
        elif data['domain'] == 'airline':
            match = re.search(r'#(BK-\d+)', data['user_intent'])
            if match:
                contract['resource_scope']['transaction_ids'] = [match.group(1)]

    # Clean up constraints - only keep standard fields
    if 'constraints' in contract:
        constraints = contract['constraints']
        cleaned_constraints = {}

        # Only keep fields that exist in Constraints class
        for key in ['max_transactions_affected', 'customer_communication', 'account_level_actions']:
            if key in constraints:
                cleaned_constraints[key] = constraints[key]

        contract['constraints'] = cleaned_constraints

    # Ensure approved_recipients exists
    if 'approved_recipients' not in contract:
        contract['approved_recipients'] = []

    # Ensure metadata exists at contract level
    if 'metadata' not in contract:
        contract['metadata'] = {}

    # Save back
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✓ Fixed {filepath.name}")
    return True


def main():
    """Fix all test files."""
    test_dir = Path('tests')

    if not test_dir.exists():
        print("Error: tests/ directory not found")
        return False

    fixed_count = 0
    for test_file in sorted(test_dir.glob('*.json')):
        try:
            if fix_test_case(test_file):
                fixed_count += 1
        except Exception as e:
            print(f"✗ Error fixing {test_file.name}: {e}")

    print(f"\n✓ Fixed {fixed_count} test files!")
    return True


if __name__ == "__main__":
    main()
