
import sys
import argparse
import importlib
from pathlib import Path

# Ensure project root is in path
ROOT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

def main():
    parser = argparse.ArgumentParser(description="eBay Draft Commander Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Fix Publish Command
    fix_parser = subparsers.add_parser("fix_publish", help="Fix policies and publish an offer")
    fix_parser.add_argument("offer_id", help="The Offer ID to fix and publish")

    # Update Policies Command
    subparsers.add_parser("update_policies", help="Update .env with policies from eBay")

    args = parser.parse_args()

    if args.command == "fix_publish":
        from tools.fix_and_publish import fix_and_publish
        fix_and_publish(args.offer_id)
        
    elif args.command == "update_policies":
        from tools.update_policies import update_env_policies
        update_env_policies()
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
