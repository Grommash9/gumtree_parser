-- Reddit Research Database Schema
-- Run: psql -d reddit_research -f init_db.sql

-- ============================================
-- Core Tables
-- ============================================

-- Reddit posts table
CREATE TABLE IF NOT EXISTS reddit_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) UNIQUE NOT NULL,
    subreddit VARCHAR(100) NOT NULL,
    title TEXT,
    selftext TEXT,
    author VARCHAR(100),
    created_utc TIMESTAMP WITH TIME ZONE,
    score INTEGER,
    num_comments INTEGER,
    permalink TEXT,
    over_18 BOOLEAN DEFAULT FALSE,
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON reddit_posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_posts_created ON reddit_posts(created_utc);

-- Reddit comments table
CREATE TABLE IF NOT EXISTS reddit_comments (
    id SERIAL PRIMARY KEY,
    comment_id VARCHAR(20) UNIQUE NOT NULL,
    post_id VARCHAR(20) NOT NULL REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    parent_id VARCHAR(30),
    author VARCHAR(100),
    body TEXT,
    score INTEGER,
    created_utc TIMESTAMP WITH TIME ZONE,
    depth INTEGER DEFAULT 0,
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_post ON reddit_comments(post_id);

-- Subreddit to classifier mapping
CREATE TABLE IF NOT EXISTS subreddit_classifiers (
    subreddit VARCHAR(100) PRIMARY KEY,
    classifier_type VARCHAR(50) NOT NULL CHECK (classifier_type IN ('vintage', 'sex', 'housing', 'flipping'))
);


-- ============================================
-- Vintage Classification Tables
-- ============================================

-- Processing status for vintage (one per post)
CREATE TABLE IF NOT EXISTS vintage_post_status (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) UNIQUE REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    stage_0_status VARCHAR(20) DEFAULT 'pending',
    is_relevant BOOLEAN,
    relevance_reason TEXT,
    llm_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vintage_status_pending ON vintage_post_status(llm_processed) WHERE llm_processed = FALSE;

-- Extracted sources (MULTIPLE per post - one row per source found)
CREATE TABLE IF NOT EXISTS vintage_sources (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    source_comment_id VARCHAR(20),  -- Which comment mentioned it (NULL if from post body)

    source_type VARCHAR(50),      -- flea_market, estate_sale, auction, thrift_store, garage_sale, online, other
    source_name TEXT,             -- Specific name if mentioned (e.g., "Rose Bowl Flea Market")
    source_location TEXT,         -- City, state, country
    source_frequency TEXT,        -- weekly, monthly, annual, one-time
    item_categories TEXT[],       -- What types of items found there
    price_quality TEXT,           -- cheap, good_deals, expensive, mixed
    original_quote TEXT,          -- The actual text that mentioned this source

    confidence FLOAT,             -- LLM confidence score (0-1)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vintage_sources_post ON vintage_sources(post_id);
CREATE INDEX IF NOT EXISTS idx_vintage_sources_type ON vintage_sources(source_type);


-- ============================================
-- Sex/Intimacy Classification Tables
-- ============================================

-- Processing status for sex (one per post)
CREATE TABLE IF NOT EXISTS sex_post_status (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) UNIQUE REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    stage_0_status VARCHAR(20) DEFAULT 'pending',
    is_relevant BOOLEAN,
    mentions_solutions BOOLEAN,
    llm_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sex_status_pending ON sex_post_status(llm_processed) WHERE llm_processed = FALSE;

-- Extracted solutions (MULTIPLE per post - one row per solution found)
CREATE TABLE IF NOT EXISTS sex_solutions (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    source_comment_id VARCHAR(20),  -- Which comment mentioned it (NULL if from post body)

    solution_category VARCHAR(100),  -- communication, therapy, medical, lifestyle, scheduling, date_nights, other
    solution_description TEXT,       -- What exactly was the solution
    worked BOOLEAN,                  -- Did it help? (TRUE/FALSE/NULL if unclear)
    timeframe TEXT,                  -- How long until it worked
    relationship_context TEXT,       -- Married, dating, how long together
    original_quote TEXT,             -- The actual text describing the solution

    confidence FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sex_solutions_post ON sex_solutions(post_id);
CREATE INDEX IF NOT EXISTS idx_sex_solutions_category ON sex_solutions(solution_category);
CREATE INDEX IF NOT EXISTS idx_sex_solutions_worked ON sex_solutions(worked);


-- ============================================
-- Housing/Shared Ownership Classification Tables
-- ============================================

-- Processing status for housing (one per post)
CREATE TABLE IF NOT EXISTS housing_post_status (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) UNIQUE REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    stage_0_status VARCHAR(20) DEFAULT 'pending',
    is_relevant BOOLEAN,
    is_shared_ownership BOOLEAN,
    llm_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_housing_status_pending ON housing_post_status(llm_processed) WHERE llm_processed = FALSE;

-- Extracted experiences (MULTIPLE per post - one row per experience/lesson found)
CREATE TABLE IF NOT EXISTS housing_experiences (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    source_comment_id VARCHAR(20),  -- Which comment mentioned it (NULL if from post body)

    experience_type VARCHAR(50),     -- positive, negative, warning, tip, question
    experience_summary TEXT,         -- What was the experience/lesson
    category VARCHAR(100),           -- staircasing, service_charges, selling, buying, management, legal
    housing_association TEXT,        -- Name if mentioned
    location TEXT,                   -- Area/region if mentioned
    original_quote TEXT,             -- The actual text

    confidence FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_housing_experiences_post ON housing_experiences(post_id);
CREATE INDEX IF NOT EXISTS idx_housing_experiences_type ON housing_experiences(experience_type);
CREATE INDEX IF NOT EXISTS idx_housing_experiences_category ON housing_experiences(category);


-- ============================================
-- Flipping/Reselling Feedback Classification Tables
-- ============================================

-- Processing status for flipping (one per post)
CREATE TABLE IF NOT EXISTS flipping_post_status (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) UNIQUE REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    stage_0_status VARCHAR(20) DEFAULT 'pending',
    is_relevant BOOLEAN,
    mentions_tools BOOLEAN DEFAULT FALSE,
    llm_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flipping_status_pending ON flipping_post_status(llm_processed) WHERE llm_processed = FALSE;

-- Extracted feedback items (MULTIPLE per post - one row per feedback item found)
CREATE TABLE IF NOT EXISTS flipping_feedback_items (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) REFERENCES reddit_posts(post_id) ON DELETE CASCADE,
    feedback_type VARCHAR(20) NOT NULL
        CHECK (feedback_type IN ('pain', 'like', 'dislike', 'feature_request')),
    tool_or_area TEXT,
    description TEXT NOT NULL,
    author VARCHAR(100),
    source VARCHAR(10) DEFAULT 'comment' CHECK (source IN ('post', 'comment')),
    original_quote TEXT,
    sentiment_intensity VARCHAR(10) DEFAULT 'medium'
        CHECK (sentiment_intensity IN ('low', 'medium', 'high')),
    confidence FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flipping_items_post ON flipping_feedback_items(post_id);
CREATE INDEX IF NOT EXISTS idx_flipping_items_type ON flipping_feedback_items(feedback_type);
CREATE INDEX IF NOT EXISTS idx_flipping_items_author ON flipping_feedback_items(author);

-- Track each aggregation execution
CREATE TABLE IF NOT EXISTS flipping_aggregation_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    items_processed INTEGER DEFAULT 0,
    topics_created INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running'
);

-- LLM-generated topic clusters
CREATE TABLE IF NOT EXISTS flipping_topics (
    id SERIAL PRIMARY KEY,
    aggregation_run_id INTEGER REFERENCES flipping_aggregation_runs(id),
    feedback_type VARCHAR(20) NOT NULL,
    topic_title TEXT NOT NULL,
    topic_summary TEXT NOT NULL,
    tools_mentioned TEXT[],
    unique_user_count INTEGER DEFAULT 0,
    total_item_count INTEGER DEFAULT 0,
    priority_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flipping_topics_run ON flipping_topics(aggregation_run_id);
CREATE INDEX IF NOT EXISTS idx_flipping_topics_type ON flipping_topics(feedback_type);
CREATE INDEX IF NOT EXISTS idx_flipping_topics_priority ON flipping_topics(priority_score DESC);

-- Many-to-many: feedback items -> topics
CREATE TABLE IF NOT EXISTS flipping_topic_items (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER REFERENCES flipping_topics(id) ON DELETE CASCADE,
    feedback_item_id INTEGER REFERENCES flipping_feedback_items(id) ON DELETE CASCADE,
    UNIQUE(topic_id, feedback_item_id)
);


-- ============================================
-- Utility Views
-- ============================================

-- View: Posts with their classification status across all classifiers
CREATE OR REPLACE VIEW posts_classification_status AS
SELECT
    p.post_id,
    p.subreddit,
    p.title,
    p.created_utc,
    sc.classifier_type,
    CASE
        WHEN sc.classifier_type = 'vintage' THEN vs.llm_processed
        WHEN sc.classifier_type = 'sex' THEN ss.llm_processed
        WHEN sc.classifier_type = 'housing' THEN hs.llm_processed
        WHEN sc.classifier_type = 'flipping' THEN fs.llm_processed
        ELSE NULL
    END as llm_processed
FROM reddit_posts p
LEFT JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit
LEFT JOIN vintage_post_status vs ON p.post_id = vs.post_id AND sc.classifier_type = 'vintage'
LEFT JOIN sex_post_status ss ON p.post_id = ss.post_id AND sc.classifier_type = 'sex'
LEFT JOIN housing_post_status hs ON p.post_id = hs.post_id AND sc.classifier_type = 'housing'
LEFT JOIN flipping_post_status fs ON p.post_id = fs.post_id AND sc.classifier_type = 'flipping';


-- ============================================
-- Stats Functions
-- ============================================

-- Function to get classification stats by type
CREATE OR REPLACE FUNCTION get_classification_stats(p_classifier_type VARCHAR)
RETURNS TABLE (
    total_posts BIGINT,
    processed_posts BIGINT,
    remaining_posts BIGINT,
    total_results BIGINT
) AS $$
BEGIN
    IF p_classifier_type = 'vintage' THEN
        RETURN QUERY
        SELECT
            (SELECT COUNT(*) FROM reddit_posts p JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit WHERE sc.classifier_type = 'vintage'),
            (SELECT COUNT(*) FROM vintage_post_status WHERE llm_processed = TRUE),
            (SELECT COUNT(*) FROM reddit_posts p JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit WHERE sc.classifier_type = 'vintage') -
            (SELECT COUNT(*) FROM vintage_post_status WHERE llm_processed = TRUE),
            (SELECT COUNT(*) FROM vintage_sources);
    ELSIF p_classifier_type = 'sex' THEN
        RETURN QUERY
        SELECT
            (SELECT COUNT(*) FROM reddit_posts p JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit WHERE sc.classifier_type = 'sex'),
            (SELECT COUNT(*) FROM sex_post_status WHERE llm_processed = TRUE),
            (SELECT COUNT(*) FROM reddit_posts p JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit WHERE sc.classifier_type = 'sex') -
            (SELECT COUNT(*) FROM sex_post_status WHERE llm_processed = TRUE),
            (SELECT COUNT(*) FROM sex_solutions);
    ELSIF p_classifier_type = 'housing' THEN
        RETURN QUERY
        SELECT
            (SELECT COUNT(*) FROM reddit_posts p JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit WHERE sc.classifier_type = 'housing'),
            (SELECT COUNT(*) FROM housing_post_status WHERE llm_processed = TRUE),
            (SELECT COUNT(*) FROM reddit_posts p JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit WHERE sc.classifier_type = 'housing') -
            (SELECT COUNT(*) FROM housing_post_status WHERE llm_processed = TRUE),
            (SELECT COUNT(*) FROM housing_experiences);
    ELSIF p_classifier_type = 'flipping' THEN
        RETURN QUERY
        SELECT
            (SELECT COUNT(*) FROM reddit_posts p JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit WHERE sc.classifier_type = 'flipping'),
            (SELECT COUNT(*) FROM flipping_post_status WHERE llm_processed = TRUE),
            (SELECT COUNT(*) FROM reddit_posts p JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit WHERE sc.classifier_type = 'flipping') -
            (SELECT COUNT(*) FROM flipping_post_status WHERE llm_processed = TRUE),
            (SELECT COUNT(*) FROM flipping_feedback_items);
    END IF;
END;
$$ LANGUAGE plpgsql;
