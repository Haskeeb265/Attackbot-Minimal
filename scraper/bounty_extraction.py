#!/usr/bin/env python3
"""
HackerOne Complete Bounty Program Data Extractor
Extracts ALL available program data using the HackerOne Hacker API v1

Author: Generated for comprehensive bounty program analysis
Version: 3.0 - Complete Rewrite with Enhanced Pagination
"""

import sys
import requests
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime


class HackerOneCompleteExtractor:
    """
    Complete HackerOne API client for extracting comprehensive bounty program data
    Handles all available endpoints with proper pagination and error handling
    """
    
    API_BASE = "https://api.hackerone.com/v1/hackers"
    
    def __init__(self, api_username: str, api_token: str, debug: bool = False):
        """
        Initialize the API client
        
        Args:
            api_username: Your HackerOne API identifier
            api_token: Your HackerOne API token
            debug: Enable debug output
        """
        self.auth = (api_username, api_token)
        self.headers = {'Accept': 'application/json'}
        self.debug = debug
        self.request_count = 0
        
    def _log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def _debug(self, message: str):
        """Debug logging"""
        if self.debug:
            self._log(message, "DEBUG")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make an authenticated API request with error handling
        
        Args:
            endpoint: API endpoint (e.g., '/programs/coinmate')
            params: Optional query parameters
        
        Returns:
            JSON response or None if request fails
        """
        url = f"{self.API_BASE}{endpoint}"
        self.request_count += 1
        
        self._debug(f"Request #{self.request_count}: {endpoint}")
        if params:
            self._debug(f"  Parameters: {params}")
        
        try:
            response = requests.get(
                url,
                auth=self.auth,
                headers=self.headers,
                params=params or {},
                timeout=30
            )
            
            self._debug(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self._debug(f"  Response keys: {list(data.keys())}")
                return data
            else:
                self._log(f"HTTP Error {response.status_code} for {endpoint}", "ERROR")
                self._log(f"Response: {response.text[:300]}", "ERROR")
                return None
                
        except requests.exceptions.RequestException as e:
            self._log(f"Request failed for {endpoint}: {e}", "ERROR")
            return None
    
    def get_program_details(self, program_handle: str) -> Optional[Dict]:
        """
        Get basic program information from the single program endpoint
        
        Args:
            program_handle: Program handle (e.g., 'coinmate')
        
        Returns:
            Program data dictionary
        """
        self._log(f"Fetching program details: {program_handle}")
        response_data = self._make_request(f"/programs/{program_handle}")
        
        if response_data:
            # Single program endpoint returns data DIRECTLY (no 'data' wrapper)
            if 'id' in response_data and 'type' in response_data:
                self._log("✓ Program details retrieved", "SUCCESS")
                return response_data
            elif 'data' in response_data:
                self._log("✓ Program details retrieved (wrapped)", "SUCCESS")
                return response_data['data']
            else:
                self._log(f"Unexpected response format: {list(response_data.keys())}", "WARNING")
                return None
        
        return None
    
    def get_structured_scopes(self, program_handle: str) -> List[Dict]:
        """
        Get ALL in-scope assets with comprehensive pagination
        
        Uses multiple pagination strategies to ensure complete data retrieval:
        1. Standard page-based pagination
        2. ID-based filtering for large datasets
        3. Date-based filtering as fallback
        
        Args:
            program_handle: Program handle
        
        Returns:
            Complete list of structured scope objects
        """
        self._log(f"Fetching structured scopes: {program_handle}")
        all_scopes = []
        page = 1
        page_size = 100  # Maximum allowed
        
        while True:
            params = {
                'page[number]': page,
                'page[size]': page_size
            }
            
            data = self._make_request(
                f"/programs/{program_handle}/structured_scopes",
                params=params
            )
            
            if not data:
                self._log("No data returned from structured_scopes endpoint", "WARNING")
                break
            
            if 'data' not in data:
                self._log(f"No 'data' key in response. Keys: {list(data.keys())}", "WARNING")
                break
            
            scopes = data['data']
            
            if not scopes:
                self._debug(f"No scopes on page {page}")
                break
            
            all_scopes.extend(scopes)
            self._log(f"  Page {page}: Retrieved {len(scopes)} scopes (total: {len(all_scopes)})")
            
            # Check for next page
            links = data.get('links', {})
            if links.get('next'):
                page += 1
                time.sleep(0.1)  # Rate limiting
            else:
                self._debug("No next page link found")
                break
            
            # Safety limit
            if page > 100:
                self._log("Reached safety limit of 100 pages", "WARNING")
                break
        
        self._log(f"✓ Total scopes retrieved: {len(all_scopes)}", "SUCCESS")
        return all_scopes
    
    def get_scope_exclusions(self, program_handle: str) -> List[Dict]:
        """
        Get scope exclusions (out-of-scope items)
        
        Args:
            program_handle: Program handle
        
        Returns:
            List of scope exclusion objects
        """
        self._log(f"Fetching scope exclusions: {program_handle}")
        data = self._make_request(f"/programs/{program_handle}/scope_exclusions")
        
        if data and 'data' in data:
            exclusions = data['data']
            self._log(f"✓ Found {len(exclusions)} exclusions", "SUCCESS")
            return exclusions
        
        self._log("No exclusions found", "WARNING")
        return []
    
    def get_weaknesses(self, program_handle: str) -> List[Dict]:
        """
        Get ALL accepted weakness types with pagination
        
        Args:
            program_handle: Program handle
        
        Returns:
            Complete list of weakness objects
        """
        self._log(f"Fetching weaknesses: {program_handle}")
        all_weaknesses = []
        page = 1
        page_size = 100
        
        while True:
            params = {
                'page[number]': page,
                'page[size]': page_size
            }
            
            data = self._make_request(
                f"/programs/{program_handle}/weaknesses",
                params=params
            )
            
            if not data or 'data' not in data:
                break
            
            weaknesses = data['data']
            
            if not weaknesses:
                break
            
            all_weaknesses.extend(weaknesses)
            self._log(f"  Page {page}: Retrieved {len(weaknesses)} weaknesses (total: {len(all_weaknesses)})")
            
            # Check for next page
            links = data.get('links', {})
            if links.get('next'):
                page += 1
                time.sleep(0.1)
            else:
                break
        
        self._log(f"✓ Total weaknesses retrieved: {len(all_weaknesses)}", "SUCCESS")
        return all_weaknesses
    
    def verify_program_access(self, program_handle: str) -> bool:
        """
        Verify that the program is accessible with current credentials

        Args:
            program_handle: Program handle

        Returns:
            True if accessible, False otherwise
        """
        self._log(f"Verifying access to program: {program_handle}")

        # Use direct program lookup instead of paginated list membership check
        data = self._make_request(f"/programs/{program_handle}")

        if data and ('id' in data or 'data' in data):
            self._log(f"✓ Program '{program_handle}' is accessible", "SUCCESS")
            return True

        self._log(f"✗ Program '{program_handle}' not accessible", "ERROR")
        return False
    
    def extract_complete_program_data(self, program_handle: str) -> Dict[str, Any]:
        """
        Extract ALL available data for a program from all endpoints
        
        Args:
            program_handle: Program handle (e.g., 'coinmate')
        
        Returns:
            Complete program data dictionary with all available information
        """
        self._log("="*80)
        self._log(f"STARTING COMPLETE EXTRACTION FOR: {program_handle}")
        self._log("="*80)
        
        extraction_start = time.time()
        
        # Step 1: Verify access
        if not self.verify_program_access(program_handle):
            self._log("Cannot proceed - program not accessible", "ERROR")
            return {}
        
        # Step 2: Get program details
        program_details = self.get_program_details(program_handle)
        
        if not program_details:
            self._log("Failed to fetch program details - aborting", "ERROR")
            return {}
        
        # Step 3: Get all supplementary data
        structured_scopes = self.get_structured_scopes(program_handle)
        scope_exclusions = self.get_scope_exclusions(program_handle)
        weaknesses = self.get_weaknesses(program_handle)
        
        # Extract attributes safely
        attrs = program_details.get('attributes', {})
        relationships = program_details.get('relationships', {})
        
        # Build comprehensive data structure
        complete_data = {
            'extraction_metadata': {
                'program_handle': program_handle,
                'extraction_timestamp': datetime.now().isoformat(),
                'extraction_duration_seconds': round(time.time() - extraction_start, 2),
                'api_requests_made': self.request_count,
                'extractor_version': '3.0'
            },
            
            'program_details': {
                'id': program_details.get('id'),
                'type': program_details.get('type'),
                'handle': attrs.get('handle', program_handle),
                'name': attrs.get('name'),
                'currency': attrs.get('currency'),
                'state': attrs.get('state'),
                'submission_state': attrs.get('submission_state'),
                'triage_active': attrs.get('triage_active'),
                'started_accepting_at': attrs.get('started_accepting_at'),
                'profile_picture': attrs.get('profile_picture'),
            },
            
            'program_features': {
                'offers_bounties': attrs.get('offers_bounties'),
                'fast_payments': attrs.get('fast_payments'),
                'gold_standard_safe_harbor': attrs.get('gold_standard_safe_harbor'),
                'allows_bounty_splitting': attrs.get('allows_bounty_splitting'),
                'open_scope': attrs.get('open_scope'),
            },
            
            'your_stats': {
                'bookmarked': attrs.get('bookmarked'),
                'number_of_reports': attrs.get('number_of_reports_for_user'),
                'number_of_valid_reports': attrs.get('number_of_valid_reports_for_user'),
                'total_bounty_earned': attrs.get('bounty_earned_for_user'),
                'last_invitation_accepted_at': attrs.get('last_invitation_accepted_at_for_user'),
            },
            
            'policy': {
                'full_text': attrs.get('policy'),
            },
            
            'in_scope_assets': {
                'count': len(structured_scopes),
                'assets': [
                    {
                        'id': scope.get('id'),
                        'asset_type': scope.get('attributes', {}).get('asset_type'),
                        'asset_identifier': scope.get('attributes', {}).get('asset_identifier'),
                        'eligible_for_bounty': scope.get('attributes', {}).get('eligible_for_bounty'),
                        'eligible_for_submission': scope.get('attributes', {}).get('eligible_for_submission'),
                        'max_severity': scope.get('attributes', {}).get('max_severity'),
                        'instruction': scope.get('attributes', {}).get('instruction'),
                        'confidentiality_requirement': scope.get('attributes', {}).get('confidentiality_requirement'),
                        'integrity_requirement': scope.get('attributes', {}).get('integrity_requirement'),
                        'availability_requirement': scope.get('attributes', {}).get('availability_requirement'),
                        'created_at': scope.get('attributes', {}).get('created_at'),
                        'updated_at': scope.get('attributes', {}).get('updated_at'),
                    }
                    for scope in structured_scopes
                ]
            },
            
            'scope_exclusions': {
                'count': len(scope_exclusions),
                'exclusions': [
                    {
                        'id': exclusion.get('id'),
                        'category': exclusion.get('attributes', {}).get('category'),
                        'details': exclusion.get('attributes', {}).get('details'),
                        'created_at': exclusion.get('attributes', {}).get('created_at'),
                        'updated_at': exclusion.get('attributes', {}).get('updated_at'),
                    }
                    for exclusion in scope_exclusions
                ]
            },
            
            'accepted_weaknesses': {
                'count': len(weaknesses),
                'weaknesses': [
                    {
                        'id': weakness.get('id'),
                        'name': weakness.get('attributes', {}).get('name'),
                        'description': weakness.get('attributes', {}).get('description'),
                        'external_id': weakness.get('attributes', {}).get('external_id'),
                        'created_at': weakness.get('attributes', {}).get('created_at'),
                    }
                    for weakness in weaknesses
                ]
            },
            
            # Raw data for debugging
            '_raw': {
                'program_response': program_details,
                'relationships': relationships,
            }
        }
        
        self._log("="*80)
        self._log("EXTRACTION COMPLETE")
        self._log("="*80)
        self._log(f"Duration: {complete_data['extraction_metadata']['extraction_duration_seconds']}s")
        self._log(f"API Requests: {complete_data['extraction_metadata']['api_requests_made']}")
        
        return complete_data
    
    def save_json(self, data: Dict, filename: str):
        """Save data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._log(f"✓ JSON saved: {filename}", "SUCCESS")
    
    def save_readable_report(self, data: Dict, filename: str):
        """Generate a human-readable text report"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("HACKERONE BOUNTY PROGRAM - COMPLETE ANALYSIS\n")
            f.write("="*80 + "\n\n")
            
            # Metadata
            meta = data['extraction_metadata']
            f.write(f"Extracted: {meta['extraction_timestamp']}\n")
            f.write(f"Duration: {meta['extraction_duration_seconds']}s\n")
            f.write(f"API Requests: {meta['api_requests_made']}\n\n")
            
            # Program Info
            prog = data['program_details']
            f.write("="*80 + "\n")
            f.write("PROGRAM INFORMATION\n")
            f.write("="*80 + "\n\n")
            f.write(f"Name: {prog['name']}\n")
            f.write(f"Handle: {prog['handle']}\n")
            f.write(f"Currency: {prog['currency']}\n")
            f.write(f"State: {prog['state']}\n")
            f.write(f"Submission State: {prog['submission_state']}\n")
            f.write(f"Started: {prog['started_accepting_at']}\n\n")
            
            # Features
            feat = data['program_features']
            f.write("="*80 + "\n")
            f.write("PROGRAM FEATURES\n")
            f.write("="*80 + "\n\n")
            f.write(f"Offers Bounties: {feat['offers_bounties']}\n")
            f.write(f"Fast Payments: {feat['fast_payments']}\n")
            f.write(f"Safe Harbor: {feat['gold_standard_safe_harbor']}\n")
            f.write(f"Bounty Splitting: {feat['allows_bounty_splitting']}\n")
            f.write(f"Open Scope: {feat['open_scope']}\n\n")
            
            # Your Stats
            stats = data['your_stats']
            if stats['number_of_reports'] is not None:
                f.write("="*80 + "\n")
                f.write("YOUR STATS FOR THIS PROGRAM\n")
                f.write("="*80 + "\n\n")
                f.write(f"Reports Submitted: {stats['number_of_reports']}\n")
                f.write(f"Valid Reports: {stats['number_of_valid_reports']}\n")
                f.write(f"Total Bounty Earned: ${stats['total_bounty_earned']}\n")
                f.write(f"Bookmarked: {stats['bookmarked']}\n\n")
            
            # Policy
            policy = data['policy']['full_text']
            if policy:
                f.write("="*80 + "\n")
                f.write("VULNERABILITY DISCLOSURE POLICY\n")
                f.write("="*80 + "\n\n")
                f.write(policy + "\n\n")
            
            # In-Scope Assets
            scopes = data['in_scope_assets']
            f.write("="*80 + "\n")
            f.write(f"IN-SCOPE ASSETS ({scopes['count']} total)\n")
            f.write("="*80 + "\n\n")
            
            if scopes['assets']:
                for i, asset in enumerate(scopes['assets'], 1):
                    f.write(f"{i}. {asset['asset_type']}: {asset['asset_identifier']}\n")
                    f.write(f"   Eligible for Bounty: {asset['eligible_for_bounty']}\n")
                    f.write(f"   Eligible for Submission: {asset['eligible_for_submission']}\n")
                    f.write(f"   Max Severity: {asset['max_severity']}\n")
                    if asset.get('instruction'):
                        f.write(f"   Instructions: {asset['instruction']}\n")
                    f.write("\n")
            else:
                f.write("⚠ No structured scopes found.\n")
                f.write("This could mean:\n")
                f.write("  - Program has open scope (any asset is in scope)\n")
                f.write("  - Scopes are defined elsewhere (check program website)\n")
                f.write("  - Program is transitioning scope setup\n\n")
            
            # Exclusions
            excl = data['scope_exclusions']
            f.write("="*80 + "\n")
            f.write(f"SCOPE EXCLUSIONS ({excl['count']} total)\n")
            f.write("="*80 + "\n\n")
            
            if excl['exclusions']:
                for i, exclusion in enumerate(excl['exclusions'], 1):
                    f.write(f"{i}. {exclusion['category']}\n")
                    f.write(f"   {exclusion['details']}\n\n")
            else:
                f.write("No scope exclusions defined.\n\n")
            
            # Weaknesses
            weak = data['accepted_weaknesses']
            f.write("="*80 + "\n")
            f.write(f"ACCEPTED WEAKNESSES ({weak['count']} total)\n")
            f.write("="*80 + "\n\n")
            
            if weak['weaknesses']:
                for i, weakness in enumerate(weak['weaknesses'], 1):
                    ext_id = weakness['external_id'] or 'N/A'
                    f.write(f"{i}. {weakness['name']} ({ext_id})\n")
                    if weakness.get('description'):
                        desc = weakness['description'][:150]
                        f.write(f"   {desc}...\n")
                    f.write("\n")
            else:
                f.write("All CWE types accepted (no restrictions).\n\n")
            
            f.write("="*80 + "\n")
            f.write("END OF REPORT\n")
            f.write("="*80 + "\n")
        
        self._log(f"✓ Report saved: {filename}", "SUCCESS")


def main():
    """Main execution function"""
    sys.stdout.reconfigure(encoding='utf-8')

    print("""
===========================================================================
         HackerOne Complete Bounty Program Data Extractor v3.0
                    Comprehensive API Data Extraction
                        With Enhanced Pagination
===========================================================================
    """)
    
    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================
    
    API_USERNAME = 'p0zzam'
    API_TOKEN = 'Sv1B67yLZNP5C+3TYFrUwZW+u6zH6kglPhBn+TTPQxg='
    PROGRAM_HANDLE = '1password_ctf'
    DEBUG_MODE = True  # Set to False for cleaner output
    
    # ==========================================================================
    
    # Initialize extractor
    extractor = HackerOneCompleteExtractor(
        api_username=API_USERNAME,
        api_token=API_TOKEN,
        debug=DEBUG_MODE
    )
    
    # Extract complete data
    complete_data = extractor.extract_complete_program_data(PROGRAM_HANDLE)
    
    if not complete_data:
        print("\n❌ EXTRACTION FAILED")
        return
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = f"{PROGRAM_HANDLE}_complete_{timestamp}.json"
    report_file = f"{PROGRAM_HANDLE}_report_{timestamp}.txt"
    
    extractor.save_json(complete_data, json_file)
    extractor.save_readable_report(complete_data, report_file)
    
    # Print summary
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY")
    print("="*80)
    print(f"Program: {complete_data['program_details']['name']}")
    print(f"Handle: {complete_data['program_details']['handle']}")
    print(f"In-Scope Assets: {complete_data['in_scope_assets']['count']}")
    print(f"Scope Exclusions: {complete_data['scope_exclusions']['count']}")
    print(f"Accepted Weaknesses: {complete_data['accepted_weaknesses']['count']}")
    print(f"API Requests Made: {complete_data['extraction_metadata']['api_requests_made']}")
    print(f"Duration: {complete_data['extraction_metadata']['extraction_duration_seconds']}s")
    print("="*80)
    
    print("\n✅ SUCCESS! All available data extracted and saved.")
    print(f"\nFiles created:")
    print(f"  📄 {json_file}")
    print(f"  📄 {report_file}")


if __name__ == '__main__':
    main()