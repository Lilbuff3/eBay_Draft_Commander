
import sys
import pytest
from pathlib import Path

def run_tests():
    # Add project root to path
    project_root = Path(__file__).parent.parent.absolute()
    sys.path.insert(0, str(project_root))
    
    # Run pytest
    args = [str(project_root / "tests"), "-v"]
    return pytest.main(args)

if __name__ == "__main__":
    sys.exit(run_tests())
