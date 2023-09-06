-- sql_queries.sql

-- Drop the setting table
DROP TABLE IF EXISTS "setting";

-- Drop the applog table
DROP TABLE IF EXISTS "chatlog";

-- Drop the thread table
DROP TABLE IF EXISTS "thread";

-- Drop the applog table
DROP TABLE IF EXISTS "applog";

-- Create the setting table
CREATE TABLE IF NOT EXISTS "setting" (
    "key" TEXT,
    "value" TEXT,
    PRIMARY KEY("key")
);


-- Create the threads table
CREATE TABLE "thread" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "chat_gpt_id" TEXT
    "title" TEXT
);

-- Create the chatlog table
CREATE TABLE IF NOT EXISTS "chatlog" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "timestamp" TIMESTAMP,
    "thread_id" TEXT,
    "role" TEXT,
    "content" TEXT,
    FOREIGN KEY ("thread_id") REFERENCES "thread" ("id")
);

-- Create the applog table
CREATE TABLE IF NOT EXISTS "applog" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "event_time" TIMESTAMP,
    "event_type" TEXT,
    "message" TEXT
);


