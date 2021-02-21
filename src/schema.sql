CREATE TABLE
IF NOT EXISTS
reminders
(
    "id" SERIAL,
    "expires" TIMESTAMP,
    "created" TIMESTAMP,
    "author" BIGINT,
    "channel" BIGINT,
    "event" VARCHAR,
    "message" VARCHAR,
    "message_id" BIGINT
);

CREATE TABLE IF NOT EXISTS
guilds (
    "id" BIGINT UNIQUE,
    "muterole" BIGINT,
    "prefix" VARCHAR DEFAULT '.',
    "modlogs" BIGINT
);

CREATE TABLE IF NOT EXISTS
tags (
    "guild" BIGINT,
    "created" TIMESTAMP,
    "author" BIGINT,
    "alias" BOOLEAN,
    "name" VARCHAR,
    "content" VARCHAR,
    "uses" BIGINT
);

CREATE TABLE IF NOT EXISTS
muted_members (
    "guild" BIGINT,
    "id" BIGINT
);

CREATE TABLE IF NOT EXISTS
warnings (
    "guild" BIGINT,
    "id" SERIAL,
    "moderator" BIGINT,
    "channel" BIGINT,
    "target" BIGINT,
    "reason" VARCHAR,
    "given_at" TIMESTAMP
);
