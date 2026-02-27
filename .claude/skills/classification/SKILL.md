# Reddit Classification System

## Overview
Multi-pattern LLM classification system for Reddit posts and comments. Uses Azure OpenAI to extract structured data from Reddit discussions.

## Three Classifiers

| Classifier | Purpose | Subreddits | Results Table |
|------------|---------|------------|---------------|
| **vintage** | Find sourcing markets for vintage items | Antiques, vintage, ThriftStoreHauls, etc. | `vintage_sources` |
| **sex** | Extract solutions that helped restore intimacy | DeadBedrooms, sex, Marriage, etc. | `sex_solutions` |
| **housing** | Extract shared ownership experiences | SharedOwnershipUK, HousingUK, etc. | `housing_experiences` |

## Project Structure
```
gumtree_parser/
├── common/
│   ├── database.py      # PostgreSQL connection pool
│   └── config.py        # Environment variables
├── llm_classifier/
│   ├── azure_client.py  # Azure OpenAI calls with rate limiting
│   ├── rate_limiter.py  # TPM sliding window rate limiter
│   ├── base_classifier.py  # Abstract base class
│   ├── vintage/         # Vintage sourcing classifier
│   ├── sex/             # Intimacy solutions classifier
│   └── housing/         # Shared ownership classifier
├── scripts/
│   ├── init_db.sql      # Database schema
│   ├── import_posts_to_db.py  # Import JSON to PostgreSQL
│   └── run_classifier.py      # Main entry point
└── data/                # Reddit JSON files by subreddit
```

## Database Setup

```bash
# Create database
createdb reddit_research

# Initialize tables
psql -d reddit_research -f scripts/init_db.sql
```

## Configuration

1. Copy `.env.example` to `.env`
2. Fill in PostgreSQL credentials
3. Fill in Azure OpenAI credentials (from ebay_research if same)

## Workflow

### 1. Import Data
```bash
# Import all subreddits
python scripts/import_posts_to_db.py

# Import specific subreddit with comments
python scripts/import_posts_to_db.py Antiques --with-comments
```

### 2. Configure Subreddit Mappings
```sql
-- Map subreddits to classifiers
INSERT INTO subreddit_classifiers (subreddit, classifier_type) VALUES
    ('Antiques', 'vintage'),
    ('ThriftStoreHauls', 'vintage'),
    ('DeadBedrooms', 'sex'),
    ('SharedOwnershipUK', 'housing');
```

### 3. Run Classification
```bash
# Check status
python scripts/run_classifier.py vintage --stats-only

# Process batch
python scripts/run_classifier.py vintage --limit 100

# Process single post
python scripts/run_classifier.py vintage --post abc123
```

## Classification Process

Each classifier follows a 2-stage pipeline:

1. **Stage 0: Relevance Check**
   - Quick check if post/comments contain relevant content
   - Saves API costs by skipping irrelevant posts

2. **Stage 1: Extraction**
   - Extracts ALL relevant items as JSON array
   - One post can yield multiple results (e.g., 5 different sources mentioned)

## Rate Limiting

Uses sliding window TPM (tokens per minute) tracking:
- Default quota: 200K TPM
- Target utilization: 70% (140K TPM)
- Automatic throttling when approaching limit
- Exponential backoff on 429 errors

## Adding New Classifiers

1. Create new folder: `llm_classifier/newtype/`
2. Create `prompts.py` with Stage 0 and Stage 1 prompts
3. Create `classifier.py` extending `BaseClassifier`
4. Add database tables to `init_db.sql`
5. Register in `run_classifier.py`

## Common Operations

### Check classification progress
```sql
SELECT * FROM get_classification_stats('vintage');
```

### View extracted sources
```sql
SELECT source_name, source_location, source_type, COUNT(*)
FROM vintage_sources
GROUP BY source_name, source_location, source_type
ORDER BY COUNT(*) DESC;
```

### Re-run failed posts
```sql
UPDATE vintage_post_status SET llm_processed = FALSE
WHERE stage_0_status = 'failed';
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | localhost | Database host |
| `POSTGRES_PORT` | 5432 | Database port |
| `POSTGRES_DB` | reddit_research | Database name |
| `AZURE_API_KEY` | - | Azure OpenAI key |
| `AZURE_ENDPOINT` | - | Azure endpoint URL |
| `AZURE_DEPLOYMENT` | gpt-4o-mini | Model deployment name |
| `AZURE_TPM_QUOTA` | 200000 | Your TPM quota |
| `PARALLEL_WORKERS` | 5 | Parallel processing workers |
