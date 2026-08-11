# Concerns

## Tech Debt

### 1. Incomplete Ingestion Pipeline
**Status:** In progress  
**Location:** `service/scraper/ingest.py`  
**Issue:** Ingestion orchestrator is partially implemented. `ingest_program()` calls `persist_program()` but the mapping and persistence logic may not fully align with scraper output contract.  
**Impact:** May cause data loss or incorrect storage during ingestion.  
**Reference:** `scope.md` §6.2 (field mapping contract)

### 2. Missing Schema Validation
**Status:** Not implemented  
**Location:** `db/mapper/hackerone_mapper.py`  
**Issue:** No validation that mapped data matches expected schema before persistence.  
**Impact:** Invalid data could corrupt database state.  
**Reference:** `scope.md` §6 (scraper output contract)

### 3. No Retry Logic for API Calls
**Status:** Not implemented  
**Location:** `service/scraper/helpers/send_request.py`  
**Issue:** No retry logic for HackerOne API failures (rate limits, network errors).  
**Impact:** Single API failure stops entire ingestion for that program.  
**Reference:** `scope.md` §6.1 (rate limit requirements)

### 4. Hardcoded Test Data
**Status:** Temporary  
**Location:** `test_detail_output.json`  
**Issue:** Test data file contains real HackerOne data (may become stale).  
**Impact:** Tests may fail if HackerOne data structure changes.  
**Reference:** `test_detail_output.json`

## Known Bugs (from scope.md §8)

### 1. `weakness_id` Sourced from Wrong Field
**Status:** ✅ Resolved  
**Issue:** Previously used `attributes.external_id` instead of the top-level `id` for `weakness_id`.  
**Fix:** `db/mapper/hackerone_mapper.py` → `_map_weaknesses` now stores the HackerOne API **top-level `id`** in `weakness_id`; the CWE identifier from `attributes.weakness_id` is stored in the nullable `hackerone_weakness_id` column (added by migration `0003` and present in the baseline schema/migration `0001`). Verified consistent across `001_schema.sql`, `db/init/models.py`, `db/repos/bounty_weaknesses.py`, and the smoke test (`tests/scraper/smoke_test_db.py` asserts the `CWE-79` round-trip).  
**Reference:** `docs/scaper_docs/schema.md` (Table: `bounty_weaknesses`)

### 2. `max_severity` Reduction Using Equality
**Status:** Documented, may still exist  
**Issue:** Using equality check instead of rank comparison for severity.  
**Impact:** Incorrect max_severity computation (only promotes to "critical").  
**Reference:** `scope.md` §8.2

### 3. Missing Per-Program Transaction Boundary
**Status:** Documented, may still exist  
**Issue:** No `atomic()` block wrapping entire `ingest_program()` body.  
**Impact:** Half-ingested programs on failure (master + some scopes committed).  
**Reference:** `scope.md` §8.3

## Security Risks

### 1. Environment Variables in Code
**Status:** Current implementation  
**Location:** `config.py`  
**Risk:** `DATABASE_URL` printed to stdout (includes credentials).  
**Impact:** Credentials exposed in logs/terminal output.  
**Mitigation:** Remove print statement or mask credentials.

### 2. No API Credential Rotation
**Status:** Not implemented  
**Risk:** HackerOne API credentials stored in environment variables without rotation.  
**Impact:** Stale credentials could cause authentication failures.

### 3. Database Credentials in Docker Compose
**Status:** Current implementation  
**Location:** `docker-compose.yml`  
**Risk:** Credentials passed via environment variables (visible in `docker inspect`).  
**Impact:** Credentials accessible to anyone with Docker access.

## Performance Bottlenecks

### 1. Sequential Program Processing
**Status:** Current implementation  
**Location:** `service/scraper/ingest.py`  
**Issue:** Programs processed sequentially (one at a time).  
**Impact:** Slow ingestion for large number of programs.  
**Note:** Deliberate design choice (per `scope.md` §7.3)

### 2. No Connection Pool Tuning
**Status:** Current implementation  
**Location:** `shared/db.py`  
**Issue:** Default pool settings (`min_size=2`, `max_size=10`).  
**Impact:** May be suboptimal for high-concurrency scenarios.

### 3. No Caching for Repeated API Calls
**Status:** Not implemented  
**Issue:** Same program data may be fetched multiple times across runs.  
**Impact:** Unnecessary API calls and rate limit consumption.

## Maintenance Issues

### 1. Empty Dockerfile
**Status:** Current implementation  
**Location:** `Dockerfile`  
**Issue:** Dockerfile is empty (no container build instructions).  
**Impact:** Cannot build application container (only PostgreSQL via Docker Compose).

### 2. No CI/CD Pipeline
**Status:** Not implemented  
**Issue:** No automated testing or deployment pipeline.  
**Impact:** Manual testing required for all changes.

### 3. Incomplete Documentation
**Status:** Current implementation  
**Location:** `README.md`  
**Issue:** README file is empty.  
**Impact:** No onboarding documentation for new contributors.

## Risk Assessment

| Category | High Risk | Medium Risk | Low Risk |
|----------|-----------|-------------|----------|
| **Security** | Credential exposure | API credential rotation | Database credential visibility |
| **Reliability** | Missing retry logic | Sequential processing | Pool tuning |
| **Maintainability** | No CI/CD | Empty Dockerfile | Incomplete docs |
| **Data Integrity** | Transaction boundary | Schema validation | Hardcoded test data |

## Recommendations

### Immediate Actions
1. Remove `DATABASE_URL` print statement from `config.py`
2. Add retry logic for HackerOne API calls
3. Implement schema validation in mapper

### Short-term Improvements
1. Add CI/CD pipeline with pytest
2. Implement API response caching
3. Add connection pool monitoring

### Long-term Considerations
1. Implement parallel program processing
2. Add API credential rotation
3. Create comprehensive README

## Evidence
- `scope.md` §8 (known-bad patterns)
- `config.py` (credential exposure)
- `service/scraper/ingest.py` (sequential processing)
- `shared/db.py` (pool configuration)
- `Dockerfile` (empty)
- `README.md` (empty)
