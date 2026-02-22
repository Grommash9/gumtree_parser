# Reddit Post Scraper

## Goal
Collect latest posts from target subreddits and save as JSON for later processing.

## Target Subreddits
- r/relationship_advice
- r/relationships
- r/relationships_advice
- r/sex

## How It Works
1. Fetch up to 1000 most recent posts per subreddit (API limit)
2. Skip posts already saved (check by post ID)
3. Save each post as `{post_id}.json` in subreddit folder
4. Respect rate limits (1000 req / 10 min)
5. Show progress during run

## API Limits (Verified)
| Limit | Value |
|-------|-------|
| Rate limit | 1000 requests / 10 minutes |
| Posts per request | 100 max |
| Pagination depth | ~1000 posts max |

## Data Structure
```
data/
├── relationship_advice/
│   ├── abc123.json
│   ├── def456.json
│   └── ...
├── relationships/
├── relationships_advice/
└── sex/
```

## Phase 2 (Later)
- Fetch comments for saved posts
- Process and analyze data

## Usage
```bash
python reddit_scraper.py
```
