
import sys
import argparse
from pathlib import Path

# Ensure project root is in path
ROOT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

def main():
    parser = argparse.ArgumentParser(description="eBay Draft Commander Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Update Policies Command
    subparsers.add_parser("update_policies", help="Update .env with policies from eBay")

    args = parser.parse_args()

    if args.command == "update_policies":
        from tools.update_policies import update_env_policies
        update_env_policies()
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
