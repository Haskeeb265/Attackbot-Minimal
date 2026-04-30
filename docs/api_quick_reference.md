# HackerOne API Quick Reference

## Authentication
```bash
curl "https://api.hackerone.com/v1/hackers/programs/coinmate" \
  -u "YOUR_API_USERNAME:YOUR_API_TOKEN" \
  -H "Accept: application/json"
```

## Available Endpoints (Hacker API)

### 1. Get Program Details
```
GET /v1/hackers/programs/{handle}
```
**Returns:** Basic program info, policy, highlights

**Example:**
```bash
curl "https://api.hackerone.com/v1/hackers/programs/coinmate" \
  -u "api-user:api-token" \
  -H "Accept: application/json"
```

**Response includes:**
- handle, name, currency
- policy (vulnerability disclosure policy text)
- offers_bounties, fast_payments, gold_standard_safe_harbor
- submission_state, state
- profile_picture

---

### 2. Get Structured Scopes (In-Scope Assets)
```
GET /v1/hackers/programs/{handle}/structured_scopes
```
**Returns:** All in-scope assets (URLs, domains, IPs, etc.)

**Parameters:**
- `page[number]` - Page number (default: 1)
- `page[size]` - Items per page (max: 100)
- `filter[id__gt]` - Get scopes with ID > specified value

**Example:**
```bash
curl "https://api.hackerone.com/v1/hackers/programs/coinmate/structured_scopes?page[size]=100" \
  -u "api-user:api-token" \
  -H "Accept: application/json"
```

**Response includes (per asset):**
- asset_type (URL, DOMAIN, IP_ADDRESS, etc.)
- asset_identifier (the actual asset)
- eligible_for_bounty (boolean)
- eligible_for_submission (boolean)
- max_severity (critical, high, medium, low, none)
- instruction (special notes)
- confidentiality_requirement, integrity_requirement, availability_requirement

---

### 3. Get Scope Exclusions
```
GET /v1/hackers/programs/{handle}/scope_exclusions
```
**Returns:** Out-of-scope items and categories

**Example:**
```bash
curl "https://api.hackerone.com/v1/hackers/programs/coinmate/scope_exclusions" \
  -u "api-user:api-token" \
  -H "Accept: application/json"
```

**Response includes:**
- category (e.g., "Vulnerabilities on sites hosted by third parties")
- details (description)
- created_at, updated_at

---

### 4. Get Weaknesses (Accepted Vulnerability Types)
```
GET /v1/hackers/programs/{handle}/weaknesses
```
**Returns:** Vulnerability types program accepts

**Parameters:**
- `page[number]` - Page number
- `page[size]` - Items per page (max: 100)

**Example:**
```bash
curl "https://api.hackerone.com/v1/hackers/programs/coinmate/weaknesses" \
  -u "api-user:api-token" \
  -H "Accept: application/json"
```

**Response includes:**
- name (e.g., "Cross-Site Request Forgery (CSRF)")
- description
- external_id (CWE number, e.g., "cwe-352")
- created_at

---

### 5. Get All Programs
```
GET /v1/hackers/programs
```
**Returns:** List of all accessible programs

**Parameters:**
- `page[number]` - Page number
- `page[size]` - Items per page (max: 100)

**Example:**
```bash
curl "https://api.hackerone.com/v1/hackers/programs?page[size]=100" \
  -u "api-user:api-token" \
  -H "Accept: application/json"
```

---

### 6. Get Your Reports
```
GET /v1/hackers/me/reports
```
**Returns:** Your submitted reports

---

### 7. Get Hacktivity
```
GET /v1/hackers/hacktivity
```
**Returns:** Public disclosed reports

**Parameters:**
- `queryString` - Lucene query for filtering

---

## Data NOT Available in Hacker API

❌ Response time metrics (avg time to first response, bounty, resolution)
❌ Bounty ranges by severity ($10-$20, $20-$50, etc.)
❌ Percentage of submissions by severity
❌ Detailed program statistics

**These require:**
- Customer API (for program managers only)
- Web scraping

---

## Python Example

```python
import requests

API_USERNAME = 'your-api-id'
API_TOKEN = 'your-api-token'
PROGRAM = 'coinmate'

# Get program details
response = requests.get(
    f'https://api.hackerone.com/v1/hackers/programs/{PROGRAM}',
    auth=(API_USERNAME, API_TOKEN),
    headers={'Accept': 'application/json'}
)

data = response.json()
print(f"Program: {data['data']['attributes']['name']}")
print(f"Currency: {data['data']['attributes']['currency']}")
print(f"Fast Payments: {data['data']['attributes']['fast_payments']}")
```

---

## Rate Limits

- **Read operations:** 600 requests/minute
- **Pagination:** Max 100 items per page
- **Structured Scopes:** Max 10,000 via pagination (use filter[id__gt] for more)

---

## Response Format

All responses follow JSON API specification:

```json
{
  "data": {
    "id": "123",
    "type": "program",
    "attributes": { ... },
    "relationships": { ... }
  },
  "links": {
    "self": "...",
    "next": "...",
    "last": "..."
  }
}
```

---

## Common Asset Types

- `URL` - Web application URL
- `DOMAIN` - Domain name
- `IP_ADDRESS` - IP address
- `CIDR` - IP range
- `ANDROID_APP_ID` - Android app
- `APPLE_STORE_APP_ID` - iOS app
- `SOURCE_CODE` - Source code repository
- `EXECUTABLE` - Binary/executable
- `HARDWARE_DEVICE` - Hardware device
- `TESTFLIGHT` - TestFlight app

---

## Error Codes

- `401` - Unauthorized (invalid credentials)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (program doesn't exist or not accessible)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

---

## Tips

1. Always include `Accept: application/json` header
2. Use pagination for large datasets
3. Add delays between requests (0.5s recommended)
4. Handle pagination with `links.next`
5. For >10k scopes, use `filter[id__gt]` instead of pagination
6. Cache responses to avoid redundant calls
7. Check `submission_state` before submitting reports

---

## Complete Extraction Workflow

```python
# 1. Get program details
program = get_program('coinmate')

# 2. Get all scopes (paginated)
scopes = get_all_structured_scopes('coinmate')

# 3. Get exclusions
exclusions = get_scope_exclusions('coinmate')

# 4. Get weaknesses
weaknesses = get_weaknesses('coinmate')

# 5. Combine and save
data = {
    'program': program,
    'scopes': scopes,
    'exclusions': exclusions,
    'weaknesses': weaknesses
}

with open('coinmate_complete.json', 'w') as f:
    json.dump(data, f, indent=2)
```

---

## Resources

- API Docs: https://api.hackerone.com/hacker-resources/
- API Reference: https://api.hackerone.com/hacker-reference/
- Getting Started: https://api.hackerone.com/getting-started-hacker-api/
- Changelog: https://api.hackerone.com/getting-started/#changelog