-- Strip legacy "memory/" prefix from Jira paths so they match the convention
-- used by the rest of the memory system. Safe to re-run: noop when no rows
-- need fixing.

BEGIN;

UPDATE notes
   SET path = substr(path, length('memory/') + 1),
       folder = CASE
                  WHEN folder LIKE 'memory/%' THEN substr(folder, length('memory/') + 1)
                  ELSE folder
                END
 WHERE path LIKE 'memory/jira/%';

UPDATE note_embeddings
   SET path = substr(path, length('memory/') + 1)
 WHERE path LIKE 'memory/jira/%';

UPDATE chunk_embeddings
   SET path = substr(path, length('memory/') + 1)
 WHERE path LIKE 'memory/jira/%';

UPDATE issues
   SET note_path = substr(note_path, length('memory/') + 1)
 WHERE note_path LIKE 'memory/jira/%';

-- Rebuild FTS so its stored paths match the updated notes table.
INSERT INTO notes_fts(notes_fts) VALUES('rebuild');

COMMIT;
