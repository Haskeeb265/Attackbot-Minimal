# Complete Guide: Extract ALL Bounty Details from HackerOne API

## Overview

This guide shows you **exactly** how to extract ALL available bounty program details using the HackerOne Hacker API with your API token and username.

## What Data Can You Extract?

Using the HackerOne API, you can extract:

### 1. **Program Basic Information**
- Program ID, handle, name
- Currency
- Policy text
- Profile picture
- Submission state (open/paused/closed)
- Program state (public_mode, private_mode, etc.)
- Number of reports for user
- Bounty earned by user
- Whether program is bookmarked
- Whether program allows bounty splitting

### 2. **Program Highlights**
- `offers_bounties` - Whether program pays bounties
- `fast_payments` - Fast payment status
- `gold_standard_safe_harbor` - Safe Harbor adherence
- `open_scope` - Whether scope is open
- `triage_active` - Whether triage is active

### 3. **In-Scope Assets (Structured Scopes)**
For each asset:
- Asset ID
- Asset type (URL, DOMAIN, IP_ADDRESS, CIDR, etc.)
- Asset identifier (the actual asset)
- Eligible for bounty (yes/no)
- Eligible for submission (yes/no)
- Max severity (critical, high, medium, low, none)
- Instructions (special notes about the asset)
- Confidentiality/Integrity/Availability requirements
- Created and updated timestamps

### 4. **Scope Exclusions**
- Exclusion ID
- Category (e.g., "Vulnerabilities on sites hosted by third parties")
- Details (description of what's excluded)
- Created and updated timestamps

### 5. **Accepted Weaknesses**
- Weakness ID
- Name (e.g., "Cross-Site Request Forgery (CSRF)")
- Description
- External ID (CWE number)
- Created timestamp

## What the API DOESN'T Provide

Unfortunately, the Hacker API does NOT provide:
- **Response time metrics** (avg time to first response, bounty, resolution)
- **Bounty ranges by severity** (the table showing $10-$20, $20-$50, etc.)
- **Percentage of submissions** by severity
- **Detailed program statistics**

**These metrics are only visible on the website and not exposed via the Hacker API.**

## Setup Instructions

### Step 1: Get Your API Credentials

1. Log in to HackerOne
2. Go to **https://hackerone.com/settings/api_tokens**
3. Click **"Create API Token"**
4. Enter an identifier (e.g., "bounty-extractor")
5. Select appropriate groups (Standard group should work)
6. Click **"Create"**
7. **IMPORTANT:** Copy both:
   - **API Identifier** (this is your username)
   - **API Token** (this is your password)

### Step 2: Update the Script

Open `complete_bounty_extractor.py` and replace:

```python
API_USERNAME = 'your_api_identifier_here'
API_TOKEN = 'your_api_token_here'
```

With your actual credentials:

```python
API_USERNAME = 'my-bounty-tool'  # Your API Identifier
API_TOKEN = 'abc123def456...'     # Your API Token
```

### Step 3: Choose a Program

Change the program handle to the one you want to extract:

```python
PROGRAM_HANDLE = 'coinmate'  # Change to any program handle
```

Program handles are found in the URL, e.g.:
- `https://hackerone.com/coinmate` → handle is `coinmate`
- `https://hackerone.com/security` → handle is `security`

### Step 4: Run the Script

```bash
python complete_bounty_extractor.py
```

## Output Files

The script creates two files:

### 1. `{program}_complete_data.json`
Complete structured data in JSON format - perfect for processing with other tools.

```json
{
  "program_handle": "coinmate",
  "extraction_timestamp": "2026-04-30 14:30:45",
  "basic_info": {
    "id": "123",
    "type": "program",
    "attributes": { ... }
  },
  "in_scope_assets": [ ... ],
  "scope_exclusions": [ ... ],
  "accepted_weaknesses": [ ... ],
  "key_metrics": { ... }
}
```

### 2. `{program}_report.txt`
Human-readable report format.

## API Endpoints Used

The script uses these official HackerOne Hacker API endpoints:

```
GET /v1/hackers/programs/{handle}
  → Returns basic program information

GET /v1/hackers/programs/{handle}/structured_scopes
  → Returns all in-scope assets (paginated)

GET /v1/hackers/programs/{handle}/scope_exclusions
  → Returns scope exclusions

GET /v1/hackers/programs/{handle}/weaknesses
  → Returns accepted weakness types (paginated)
```

## Authentication

All requests use **HTTP Basic Authentication**:

```python
auth=(API_USERNAME, API_TOKEN)
```

The API identifier is the username, and the API token is the password.

## Rate Limiting

The HackerOne API has rate limits:
- **600 requests per minute** for read operations

The script includes automatic rate limiting (0.5 second delays between paginated requests).

## Pagination

Some endpoints return paginated results (max 100 items per page):
- Structured Scopes
- Weaknesses

The script automatically handles pagination and fetches ALL pages.

## Example: Extract Multiple Programs

```python
# List of programs to extract
programs = ['coinmate', 'security', 'gitlab', 'shopify']

api = HackerOneAPI(API_USERNAME, API_TOKEN)

for program_handle in programs:
    print(f"\nExtracting: {program_handle}")
    
    data = api.extract_complete_program_data(program_handle)
    
    if data:
        api.save_to_json(data, f'{program_handle}_data.json')
    
    time.sleep(2)  # Rate limiting between programs
```

## Advanced: Extract Bounty Table (NOT in Hacker API)

The bounty ranges table you see on the website is **NOT available** via the Hacker API.

According to the changelog, there's a **Customer API** endpoint added April 10, 2026:

```
GET /v1/programs/{program_id}/bounty_table
```

**But this is only available to program managers via the Customer API, not hackers.**

To get bounty ranges, you would need to:
1. Use web scraping (as covered in the earlier files)
2. Or request access to the Customer API if you're a program manager

## Common Issues

### Issue: `401 Unauthorized`
**Solution:** Check your API credentials. Make sure you copied both the identifier and token correctly.

### Issue: `403 Forbidden`
**Solution:** Your API token doesn't have the right permissions. Recreate it with the Standard group selected.

### Issue: `404 Not Found`
**Solution:** The program handle is incorrect. Check the URL on HackerOne to get the correct handle.

### Issue: Empty results
**Solution:** 
- The program might not be public
- You might not have access to the program
- The program might not have any data in that category

## Data Structure Details

### Asset Types
Possible values for `asset_type`:
- `URL`
- `DOMAIN`
- `IP_ADDRESS`
- `CIDR`
- `ANDROID_APP_ID`
- `APPLE_STORE_APP_ID`
- `WINDOWS_APP_ID`
- `SOURCE_CODE`
- `EXECUTABLE`
- `HARDWARE_DEVICE`
- `TESTFLIGHT` (added recently)
- And more...

### Severity Levels
- `critical`
- `high`
- `medium`
- `low`
- `none`

### Program States
- `public_mode` - Public program
- `private_mode` - Private/invite-only
- `disabled` - Program disabled
- `soft_launched` - Soft launch mode

## Complete Example

```python
from complete_bounty_extractor import HackerOneAPI

# Initialize
api = HackerOneAPI('my-api-id', 'my-api-token')

# Extract complete data
data = api.extract_complete_program_data('coinmate')

# Access specific data
print(f"Program: {data['key_metrics']['program_name']}")
print(f"Currency: {data['key_metrics']['currency']}")
print(f"Fast Payments: {data['key_metrics']['fast_payments']}")

# List all in-scope assets
for asset in data['in_scope_assets']:
    print(f"{asset['asset_type']}: {asset['asset_identifier']}")

# List exclusions
for exclusion in data['scope_exclusions']:
    print(f"{exclusion['category']}: {exclusion['details']}")

# Save to file
api.save_to_json(data, 'output.json')
```

## Summary

**What you CAN extract with the API:**
✅ Program details (name, handle, policy)
✅ All in-scope assets
✅ Scope exclusions
✅ Accepted weaknesses
✅ Program highlights (fast payments, safe harbor, etc.)

**What you CANNOT extract with the Hacker API:**
❌ Response time metrics
❌ Bounty ranges by severity
❌ Percentage distributions
❌ Detailed statistics

For the data not available via API, you'll need to use web scraping (see the earlier files in this toolkit).

## Next Steps

1. Run the script for a test program
2. Verify the output files
3. Modify the script to extract multiple programs
4. Combine with web scraping if you need the metrics not available via API

## Resources

- [HackerOne Hacker API Documentation](https://api.hackerone.com/hacker-resources/)
- [API Reference](https://api.hackerone.com/hacker-reference/)
- [Getting Started Guide](https://api.hackerone.com/getting-started-hacker-api/)