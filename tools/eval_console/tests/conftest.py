"""Pytest configuration for eval_console integration tests.

Sets up the Python path and injects test credentials *before* any
eval_console module-level code (auth._SECRET, auth._REVIEWER_PASSWORDS)
can read from the environment.
"""
import os
import sys
from pathlib import Path

# Make eval_console importable as the root package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Override credentials with known test values.
# load_dotenv() in main.py will NOT override these (override=False is default).
os.environ["REVIEWER_1_PASSWORD"] = "int_test_r1_pass"
os.environ["REVIEWER_2_PASSWORD"] = "int_test_r2_pass"
os.environ["ADMIN_PASSWORD"] = "int_test_admin_pass"
os.environ["SECRET_KEY"] = "int_test_secret_key_32bytes!!"
