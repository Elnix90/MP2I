-- Memory system schema for MP2I Bot
-- Uses sqlite-vec for vector search, FTS5 for keyword search

-- Core turns table (replaces in-memory dict)
CREATE TABLE IF NOT EXISTS memory_turns (
    turn_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    guild_id INTEGER,
    channel_id INTEGER,
    thread_id INTEGER,
    user_content TEXT NOT NULL,
    assistant_content TEXT,
    scope_key TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_memory_turns_scope ON memory_turns(scope_key);
CREATE INDEX IF NOT EXISTS idx_memory_turns_user ON memory_turns(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_turns_channel ON memory_turns(channel_id);
CREATE INDEX IF NOT EXISTS idx_memory_turns_created ON memory_turns(created_at);

-- User facts (cross-session persistent memory)
CREATE TABLE IF NOT EXISTS user_facts (
    fact_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    fact TEXT NOT NULL,
    source_turn_ids TEXT,  -- JSON array of turn_ids
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_facts_user ON user_facts(user_id);

-- Channel facts (per-channel context)
CREATE TABLE IF NOT EXISTS channel_facts (
    fact_id TEXT PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    fact TEXT NOT NULL,
    source_turn_ids TEXT,  -- JSON array of turn_ids
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_channel_facts_channel ON channel_facts(channel_id);
