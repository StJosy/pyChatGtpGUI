-- sql_queries.sql

-- Drop the applog table
DROP TABLE IF EXISTS "chatlog";

-- Drop the thread table
DROP TABLE IF EXISTS "thread";

-- Create the threads table
CREATE TABLE "thread" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "title" TEXT
);

-- Create the chatlog table
CREATE TABLE IF NOT EXISTS "chatlog" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "timestamp" TIMESTAMP,
    "thread_id" INTEGER,
    "role" TEXT,
    "content" TEXT,
    FOREIGN KEY ("thread_id") REFERENCES "thread" ("id")
);



