#!/usr/bin/env python3
"""
HackerOne API Diagnostic Tool
Tests your API credentials and connection to HackerOne
"""

import requests
import json


def test_api_connection(api_username, api_token):
    """Test API connection with detailed error reporting"""
    
    print("="*80)
    print("HACKERONE API DIAGNOSTIC TEST")
    print("="*80)
    print()
    
    # Test 1: Basic connectivity
    print("TEST 1: Basic connectivity to HackerOne API")
    print("-" * 80)
    try:
        response = requests.get(
            "https://api.hackerone.com/v1/hackers/programs",
            auth=(api_username, api_token),
            headers={'Accept': 'application/json'},
            timeout=10
        )
        
        print(f"✓ Connection successful")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            print("✓ Authentication successful!")
            data = response.json()
            programs = data.get('data', [])
            print(f"✓ Found {len(programs)} accessible programs")
            print()
            
            if programs:
                print("First 5 programs you have access to:")
                for i, program in enumerate(programs[:5], 1):
                    handle = program.get('attributes', {}).get('handle', 'N/A')
                    name = program.get('attributes', {}).get('name', 'N/A')
                    print(f"  {i}. {handle} ({name})")
            print()
            
        elif response.status_code == 401:
            print("❌ AUTHENTICATION FAILED")
            print("  Error: Invalid API credentials")
            print()
            print("  Possible causes:")
            print("  1. Incorrect API username (identifier)")
            print("  2. Incorrect API token")
            print("  3. API token has been revoked")
            print()
            print("  Solution:")
            print("  - Go to https://hackerone.com/settings/api_tokens")
            print("  - Verify your credentials or create a new token")
            print()
            return False
            
        elif response.status_code == 403:
            print("❌ AUTHORIZATION FAILED")
            print("  Error: Insufficient permissions")
            print()
            print("  Possible causes:")
            print("  1. API token doesn't have the required permissions")
            print("  2. API token is not in the correct group")
            print()
            print("  Solution:")
            print("  - Go to https://hackerone.com/settings/api_tokens")
            print("  - Edit your token and ensure 'Standard' group is selected")
            print("  - Or create a new token with proper permissions")
            print()
            return False
            
        else:
            print(f"❌ UNEXPECTED RESPONSE: {response.status_code}")
            print(f"  Response: {response.text[:500]}")
            print()
            return False
            
    except requests.exceptions.ConnectionError as e:
        print("❌ CONNECTION ERROR")
        print(f"  Error: {e}")
        print()
        print("  Possible causes:")
        print("  1. No internet connection")
        print("  2. Firewall blocking the request")
        print("  3. HackerOne API is down")
        print()
        return False
        
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT ERROR")
        print("  The request took too long to complete")
        print()
        return False
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print()
        return False
    
    # Test 2: Test specific program access
    print("\nTEST 2: Testing access to 'coinmate' program")
    print("-" * 80)
    
    try:
        response = requests.get(
            "https://api.hackerone.com/v1/hackers/programs/coinmate",
            auth=(api_username, api_token),
            headers={'Accept': 'application/json'},
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ Successfully accessed 'coinmate' program")
            data = response.json()
            program = data.get('data', {})
            attrs = program.get('attributes', {})
            
            print()
            print("Program Details:")
            print(f"  Handle: {attrs.get('handle')}")
            print(f"  Name: {attrs.get('name')}")
            print(f"  Currency: {attrs.get('currency')}")
            print(f"  State: {attrs.get('state')}")
            print(f"  Submission State: {attrs.get('submission_state')}")
            print(f"  Offers Bounties: {attrs.get('offers_bounties')}")
            print()
            
        elif response.status_code == 404:
            print("❌ PROGRAM NOT FOUND")
            print()
            print("  Possible causes:")
            print("  1. Program 'coinmate' doesn't exist")
            print("  2. Program is private and you don't have access")
            print("  3. Program handle is incorrect")
            print()
            print("  Solution:")
            print("  - Check the program URL on HackerOne")
            print("  - Try a different public program (e.g., 'security', 'gitlab')")
            print()
            return False
            
        elif response.status_code == 401:
            print("❌ Authentication failed for this program")
            return False
            
        elif response.status_code == 403:
            print("❌ You don't have permission to access this program")
            print("  This program may be private/invite-only")
            print()
            return False
            
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            print()
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Test 3: Test other endpoints
    print("\nTEST 3: Testing other API endpoints")
    print("-" * 80)
    
    endpoints = [
        ("Get Structured Scopes", "https://api.hackerone.com/v1/hackers/programs/coinmate/structured_scopes"),
        ("Get Scope Exclusions", "https://api.hackerone.com/v1/hackers/programs/coinmate/scope_exclusions"),
        ("Get Weaknesses", "https://api.hackerone.com/v1/hackers/programs/coinmate/weaknesses"),
    ]
    
    for name, url in endpoints:
        try:
            response = requests.get(
                url,
                auth=(api_username, api_token),
                headers={'Accept': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                count = len(data.get('data', []))
                print(f"  ✓ {name}: {count} items")
            else:
                print(f"  ✗ {name}: Status {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ {name}: Error - {e}")
    
    print()
    print("="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
    
    return True


def main():
    print("\nPlease enter your HackerOne API credentials:")
    print("(You can find these at https://hackerone.com/settings/api_tokens)\n")
    
    api_username = input("API Username (Identifier): ").strip()
    api_token = input("API Token: ").strip()
    
    print()
    
    if not api_username or not api_token:
        print("❌ Error: Both API username and token are required!")
        return
    
    if api_username == 'your_api_identifier_here':
        print("❌ Error: Please use your actual API credentials, not the placeholder!")
        return
    
    # Run diagnostic tests
    success = test_api_connection(api_username, api_token)
    
    if success:
        print("\n✓ All tests passed! Your API setup is working correctly.")
        print("\nYou can now use the complete_bounty_extractor.py script.")
    else:
        print("\n❌ Some tests failed. Please fix the issues above and try again.")
        print("\nCommon solutions:")
        print("1. Verify your API credentials at https://hackerone.com/settings/api_tokens")
        print("2. Make sure your API token has the 'Standard' group permission")
        print("3. Try creating a new API token")
        print("4. Check if you have access to the program you're trying to query")


if __name__ == '__main__':
    main()