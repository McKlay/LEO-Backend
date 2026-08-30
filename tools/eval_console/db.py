import os

from supabase import Client, create_client


def get_client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def init_db() -> None:
    pass  # Table created once via Supabase SQL Editor (see DEPLOYMENT.md §2)
