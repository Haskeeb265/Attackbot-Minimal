#!/usr/bin/env python3
"""
List all HackerOne programs accessible with your API credentials
"""

import requests
import json


def list_accessible_programs(api_username, api_token):
    """List all programs you have access to"""
    
    auth = (api_username, api_token)
    headers = {'Accept': 'application/json'}
    
    print("\n" + "="*80)
    print("FETCHING YOUR ACCESSIBLE HACKERONE PROGRAMS")
    print("="*80 + "\n")
    
    all_programs = []
    page = 1
    
    while True:
        params = {
            'page[number]': page,
            'page[size]': 100
        }
        
        try:
            response = requests.get(
                'https://api.hackerone.com/v1/hackers/programs',
                auth=auth,
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                return []
            
            data = response.json()
            programs = data.get('data', [])
            
            if not programs:
                break
            
            all_programs.extend(programs)
            print(f"Page {page}: Retrieved {len(programs)} programs")
            
            # Check for next page
            if 'links' in data and data['links'].get('next'):
                page += 1
            else:
                break
                
        except Exception as e:
            print(f"Error: {e}")
            break
    
    print(f"\n✓ Total programs found: {len(all_programs)}\n")
    print("="*80)
    print("YOUR ACCESSIBLE PROGRAMS")
    print("="*80 + "\n")
    
    # Sort by name
    all_programs.sort(key=lambda p: p.get('attributes', {}).get('name', '').lower())
    
    for i, program in enumerate(all_programs, 1):
        attrs = program.get('attributes', {})
        handle = attrs.get('handle', 'N/A')
        name = attrs.get('name', 'N/A')
        state = attrs.get('state', 'N/A')
        offers_bounties = attrs.get('offers_bounties', False)
        currency = attrs.get('currency', 'N/A')
        
        bounty_icon = "💰" if offers_bounties else "🏆"
        
        print(f"{i:3d}. {bounty_icon} {name}")
        print(f"      Handle: {handle}")
        print(f"      State: {state} | Currency: {currency}")
        print()
    
    # Save to JSON
    output_file = 'accessible_programs.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_count': len(all_programs),
            'programs': [
                {
                    'handle': p.get('attributes', {}).get('handle'),
                    'name': p.get('attributes', {}).get('name'),
                    'state': p.get('attributes', {}).get('state'),
                    'offers_bounties': p.get('attributes', {}).get('offers_bounties'),
                    'currency': p.get('attributes', {}).get('currency'),
                }
                for p in all_programs
            ]
        }, f, indent=2)
    
    print("="*80)
    print(f"✓ Program list saved to: {output_file}")
    print("="*80 + "\n")
    
    return all_programs


def main():
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║              HackerOne Accessible Programs Lister                          ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Your credentials
    API_USERNAME = 'p0zzam'
    API_TOKEN = 'Sv1B67yLZNP5C+3TYFrUwZW+u6zH6kglPhBn+TTPQxg='
    
    programs = list_accessible_programs(API_USERNAME, API_TOKEN)
    
    if programs:
        print("\n🎯 WHAT TO DO NEXT:\n")
        print("1. Choose a program handle from the list above")
        print("2. Update PROGRAM_HANDLE in the extractor script")
        print("3. Run the extractor to get complete program data\n")
        print("Example handles to try:")
        print("  - 'security' (HackerOne's own program)")
        print("  - 'rails' (Ruby on Rails)")
        print("  - 'cloudflare' (Cloudflare)")
        print()


if __name__ == '__main__':
    main()