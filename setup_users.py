#!/usr/bin/env python3
"""
AERO User Setup Script

This script initializes the AERO_USERS.xlsx file with users defined in the .env file.
It reads AERO_SEED_USER_* environment variables and creates bcrypt-hashed credentials.

Run this script once during project setup:
    python setup_users.py
"""

import os
import sys

# Ensure the aero module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from aero.auth.service import seed_users

def main():
    """Initialize users from .env file."""
    print("=" * 70)
    print("AERO User Setup Script")
    print("=" * 70)
    
    # Load environment variables from .env
    load_dotenv()
    
    print("\n✓ Loading environment variables from .env file...")
    
    # Get the credential seeding data
    seed_count = 0
    for n in range(1, 11):
        uid = os.getenv(f"AERO_SEED_USER_{n}_ID", "").strip()
        pwd = os.getenv(f"AERO_SEED_USER_{n}_PASS", "").strip()
        role = os.getenv(f"AERO_SEED_USER_{n}_ROLE", "").strip()
        name = os.getenv(f"AERO_SEED_USER_{n}_NAME", uid).strip()
        
        if uid and pwd and role:
            seed_count += 1
            print(f"\n  [{n}] User: {uid}")
            print(f"      Role: {role}")
            print(f"      Display Name: {name}")
    
    if seed_count == 0:
        print("\n✗ No users found in .env file!")
        print("  Please set AERO_SEED_USER_1_ID, AERO_SEED_USER_1_PASS, AERO_SEED_USER_1_ROLE")
        return False
    
    print(f"\n✓ Found {seed_count} user(s) to seed")
    
    # Call seed_users() which creates AERO_USERS.xlsx
    print("\nGenerating credentials file...")
    seed_users()
    
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    users_file = os.path.join(data_dir, "AERO_USERS.xlsx")
    
    if os.path.exists(users_file):
        print(f"\n✓ SUCCESS: User credentials file created at:")
        print(f"  {users_file}")
        print(f"\n✓ {seed_count} user(s) created with bcrypt-hashed passwords")
        print("\nYou can now login to the application with:")
        for n in range(1, seed_count + 1):
            uid = os.getenv(f"AERO_SEED_USER_{n}_ID", "").strip()
            if uid:
                print(f"  • User ID: {uid}")
        return True
    else:
        print(f"\n✗ FAILED: Could not create {users_file}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
