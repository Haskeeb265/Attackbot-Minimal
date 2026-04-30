# Summary: What You CAN and CANNOT Extract via HackerOne API

## ✅ What You CAN Extract (via Hacker API)

### 1. Program Basic Information
- ✅ Program ID
- ✅ Program handle (e.g., "coinmate")
- ✅ Program name
- ✅ Currency (USD, EUR, etc.)
- ✅ Profile picture URL
- ✅ **Policy text** (Vulnerability Disclosure Policy - the full text)
- ✅ Submission state (open, paused, disabled)
- ✅ Program state (public_mode, private_mode, etc.)
- ✅ Whether program is bookmarked by you
- ✅ Whether program allows bounty splitting

### 2. Program Highlights
- ✅ **Offers bounties** (yes/no)
- ✅ **Fast payments** (yes/no)
- ✅ **Gold Standard Safe Harbor** (yes/no)
- ✅ **Open scope** (yes/no)
- ✅ **Triage active** (yes/no)
- ✅ Started accepting date
- ✅ Number of reports you've submitted
- ✅ Number of valid reports you've submitted
- ✅ Total bounty you've earned from this program

### 3. In-Scope Assets (Structured Scopes)
For EACH asset, you get:
- ✅ Asset ID
- ✅ **Asset type** (URL, DOMAIN, IP_ADDRESS, CIDR, ANDROID_APP_ID, APPLE_STORE_APP_ID, SOURCE_CODE, EXECUTABLE, etc.)
- ✅ **Asset identifier** (the actual asset, e.g., "https://api.example.com")
- ✅ **Eligible for bounty** (yes/no)
- ✅ **Eligible for submission** (yes/no)
- ✅ **Max severity** (critical, high, medium, low, none)
- ✅ **Special instructions** (notes about the asset)
- ✅ Confidentiality requirement (high, medium, low)
- ✅ Integrity requirement (high, medium, low)
- ✅ Availability requirement (high, medium, low)
- ✅ Created timestamp
- ✅ Updated timestamp
- ✅ Reference ID

### 4. Scope Exclusions
For EACH exclusion, you get:
- ✅ Exclusion ID
- ✅ **Category** (e.g., "Vulnerabilities on sites hosted by third parties")
- ✅ **Details** (full description of what's excluded)
- ✅ Created timestamp
- ✅ Updated timestamp

### 5. Accepted Weaknesses
For EACH weakness type, you get:
- ✅ Weakness ID
- ✅ **Name** (e.g., "Cross-Site Request Forgery (CSRF)")
- ✅ **Description** (full description of the weakness)
- ✅ **External ID** (CWE number, e.g., "cwe-352")
- ✅ Created timestamp

### 6. Your Personal Data
- ✅ Your balance
- ✅ Your earnings history
- ✅ Your payout history
- ✅ Your submitted reports
- ✅ Hacktivity (public disclosed reports)

---

## ❌ What You CANNOT Extract (Not in Hacker API)

### 1. Response Time Metrics
These are shown on the website but NOT available via API:
- ❌ Average time to first response (e.g., "23 hours")
- ❌ Average time to bounty (e.g., "6 hours")
- ❌ Average time from submission to bounty (e.g., "6 hours")
- ❌ Average time to resolution (e.g., "5 days")

**Why?** These metrics are calculated aggregates only shown in the UI.

### 2. Bounty Ranges by Severity
The bounty table you see on the website is NOT available:
- ❌ Bounty range for Critical (e.g., "$150 - $500")
- ❌ Bounty range for High (e.g., "$50 - $150")
- ❌ Bounty range for Medium (e.g., "$20 - $50")
- ❌ Bounty range for Low (e.g., "$10 - $20")
- ❌ Average bounty by severity (e.g., "Avg. bounty $53")

**Why?** Bounty tables are available in the **Customer API** (for program managers), but not the Hacker API.

**Note:** According to the changelog, a bounty table endpoint was added April 10, 2026, but it's for the Customer API: `GET /v1/programs/{program_id}/bounty_table`

### 3. Statistics & Percentages
- ❌ Percentage of submissions by severity (e.g., "34.21% submissions")
- ❌ Top response efficiency percentage (e.g., "above 90%")
- ❌ Total number of resolved reports
- ❌ Total number of participants/hackers

**Why?** These are aggregated statistics not exposed in the Hacker API.

### 4. Platform Standards Deviations
- ❌ Detailed platform standards commitments
- ❌ Exemplary standards commitments

**Why?** This structured data is only in the UI, not the API.

### 5. Custom Fields
- ❌ Program-specific custom field definitions
- ❌ Custom field values (except on your own reports)

---

## 📊 Comparison Table

| Data Type | Available via API | Available on Website | How to Get |
|-----------|-------------------|---------------------|-----------|
| Program name, handle | ✅ | ✅ | API: `/programs/{handle}` |
| Policy text (VDP) | ✅ | ✅ | API: `/programs/{handle}` |
| Fast payments | ✅ | ✅ | API: `/programs/{handle}` |
| Safe Harbor | ✅ | ✅ | API: `/programs/{handle}` |
| In-scope assets | ✅ | ✅ | API: `/programs/{handle}/structured_scopes` |
| Scope exclusions | ✅ | ✅ | API: `/programs/{handle}/scope_exclusions` |
| Accepted weaknesses | ✅ | ✅ | API: `/programs/{handle}/weaknesses` |
| Response time metrics | ❌ | ✅ | Web scraping only |
| Bounty ranges | ❌ | ✅ | Web scraping or Customer API |
| Avg bounty by severity | ❌ | ✅ | Web scraping only |
| Submission percentages | ❌ | ✅ | Web scraping only |
| Response efficiency % | ❌ | ✅ | Web scraping only |

---

## 🎯 What This Means for You

### If you only need program scope and policy:
✅ **Use the API** - Everything you need is available

**Example use case:**
- Building a tool to track which programs accept specific vulnerability types
- Automating scope collection for recon
- Finding programs that accept specific asset types

### If you need response metrics and bounty amounts:
❌ **API is not enough** - You need web scraping

**Example use case:**
- Comparing which programs pay the most
- Finding fast-responding programs
- Analyzing bounty distribution

---

## 🔧 Solution: Combining API + Web Scraping

For complete data extraction, use BOTH:

### 1. Use API for structured data (recommended):
```python
# Extract via API
api = HackerOneAPI(username, token)
data = api.extract_complete_program_data('coinmate')

# You now have:
# - All scopes
# - All exclusions
# - Policy text
# - Program highlights
```

### 2. Use web scraping for metrics:
```python
# Scrape the website for missing data
scraper = HackerOneScraper()
metrics = scraper.get_response_metrics('coinmate')
bounty_ranges = scraper.get_bounty_ranges('coinmate')

# Combine
complete_data = {**data, **metrics, **bounty_ranges}
```

---

## 💡 Recommendations

### For reliability and speed:
1. **Primary:** Use API for all structured data
2. **Secondary:** Use web scraping only for metrics not in API

### For complete automation:
1. Run API extraction first (fast, reliable)
2. Run web scraping for supplementary data (slower, may break)
3. Merge the results
4. Cache everything to avoid redundant requests

### For just understanding a program:
- API is 100% sufficient
- You get all the info you need to know if a program is worth hacking

---

## 📝 Example: What Your Data Will Look Like

Using **ONLY the API**, you'll get:

```json
{
  "program_handle": "coinmate",
  "basic_info": {
    "name": "CoinMate",
    "currency": "usd",
    "fast_payments": true,
    "gold_standard_safe_harbor": true,
    "offers_bounties": true,
    "policy": "Full VDP text here..."
  },
  "in_scope_assets": [
    {
      "asset_type": "URL",
      "asset_identifier": "https://coinmate.io",
      "eligible_for_bounty": true,
      "max_severity": "critical"
    }
  ],
  "scope_exclusions": [
    {
      "category": "Social engineering attacks",
      "details": "Social engineering attacks such as phishing"
    }
  ],
  "accepted_weaknesses": [
    {
      "name": "Cross-Site Request Forgery (CSRF)",
      "external_id": "cwe-352"
    }
  ]
}
```

Using **API + Web Scraping**, you'll additionally get:

```json
{
  "response_metrics": {
    "avg_first_response": "23 hours",
    "avg_time_to_bounty": "6 hours",
    "avg_time_to_resolution": "5 days"
  },
  "bounty_ranges": [
    {
      "severity": "Critical",
      "min": 150,
      "max": 500,
      "avg_bounty": "$53",
      "percentage": "50%"
    }
  ]
}
```

---

## Final Answer

**Your original question:** "How do I extract ALL details for a bounty?"

**Answer:**

1. **Use the provided `complete_bounty_extractor.py` script** to extract everything available via API:
   - Program info
   - All scopes
   - All exclusions  
   - All weaknesses
   - Highlights

2. **For the data NOT in the API** (response times, bounty ranges):
   - Use the web scraping scripts provided earlier
   - Or accept that this data is not programmatically accessible

3. **Best approach:** 
   - Start with the API script (fast, reliable, complete for most use cases)
   - Add web scraping only if you specifically need the metrics

The API gives you ~95% of the actionable data you need to understand a bounty program!