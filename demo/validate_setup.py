"""
Quick validation script to ensure demo setup is correct.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

def validate_imports():
    """Check all imports work."""
    print("✓ Checking imports...")
    try:
        from test_schema import TestCase, TestResult, Domain, AttackPattern
        from test_runner import TestRunner
        from domains.banking_tools import BANKING_TOOLS
        from domains.retail_tools import RETAIL_TOOLS
        from domains.airline_tools import AIRLINE_TOOLS
        print("  ✓ All modules import successfully")
        return True
    except Exception as e:
        print(f"  ✗ Import error: {e}")
        return False


def validate_test_cases():
    """Check all test case files load correctly."""
    print("\n✓ Checking test cases...")
    try:
        from test_runner import TestRunner
        runner = TestRunner()
        test_cases = runner.load_all_tests()
        print(f"  ✓ Loaded {len(test_cases)} test cases")

        # Check we have all domains
        domains = set(tc.domain for tc in test_cases)
        expected_domains = {'banking', 'retail', 'airline'}
        if domains == expected_domains:
            print(f"  ✓ All 3 domains present: {sorted(domains)}")
        else:
            print(f"  ✗ Missing domains: {expected_domains - domains}")
            return False

        # Check we have all patterns
        patterns = set(tc.attack_pattern for tc in test_cases)
        expected_patterns = {
            'tool_chaining', 'timing_violation',
            'cross_context_leak', 'business_logic_bypass'
        }
        if patterns == expected_patterns:
            print(f"  ✓ All 4 attack patterns present")
        else:
            print(f"  ✗ Missing patterns: {expected_patterns - patterns}")
            return False

        # Show breakdown
        print("\n  Test Case Breakdown:")
        for domain in sorted(domains):
            count = sum(1 for tc in test_cases if tc.domain == domain)
            print(f"    {domain.upper()}: {count} tests")

        return True
    except Exception as e:
        print(f"  ✗ Error loading test cases: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_tools():
    """Check all domain tools are available."""
    print("\n✓ Checking domain tools...")
    try:
        from domains.banking_tools import BANKING_TOOLS
        from domains.retail_tools import RETAIL_TOOLS
        from domains.airline_tools import AIRLINE_TOOLS

        print(f"  ✓ Banking tools: {len(BANKING_TOOLS)} tools")
        print(f"  ✓ Retail tools: {len(RETAIL_TOOLS)} tools")
        print(f"  ✓ Airline tools: {len(AIRLINE_TOOLS)} tools")
        return True
    except Exception as e:
        print(f"  ✗ Error loading tools: {e}")
        return False


def validate_intentguard():
    """Check IntentGuard components are available."""
    print("\n✓ Checking IntentGuard components...")
    try:
        from src.deviation_detector import DeviationDetector
        from src.intent_contract import IntentContract
        print("  ✓ DeviationDetector available")
        print("  ✓ IntentContract available")
        return True
    except Exception as e:
        print(f"  ✗ Error loading IntentGuard components: {e}")
        print("  ℹ  Make sure you're running from the demo/ directory")
        return False


def main():
    """Run all validations."""
    print("="*60)
    print("IntentGuard Security Benchmark - Setup Validation")
    print("="*60)

    results = []

    results.append(validate_imports())
    results.append(validate_intentguard())
    results.append(validate_test_cases())
    results.append(validate_tools())

    print("\n" + "="*60)
    if all(results):
        print("✓ ALL CHECKS PASSED - Demo is ready!")
        print("="*60)
        print("\nRun the demo with:")
        print("  python dashboard_server.py")
        print("\nOr use the convenience script:")
        print("  ./run_demo.sh")
        print("\nThen open: http://localhost:8002")
        print("="*60)
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Please fix errors above")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
