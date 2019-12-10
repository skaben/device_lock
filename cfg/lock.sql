CREATE TABLE IF NOT EXISTS "lock" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
  "uid" integer NOT NULL, 
  "card_list" varchar(256),
  "sound" bool default 0 NOT NULL, 
  "opened" bool default 0 NOT NULL, 
  "timer" int default 10 NOT NULL,
  "blocked" bool default 0 NOT NULL, 
  "ts" integer default 1 NOT NULL
);
