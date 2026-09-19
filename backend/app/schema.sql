-- Local store for opinion text, the retrieval index, and the citation graph.
--
-- SQLite because it needs no server and cannot fail to start at a venue. The
-- shapes here map one-to-one onto Postgres: `embedding` becomes a pgvector
-- column and `cites` mirrors CourtListener's `search_opinionscited` bulk table
-- (id, depth, cited_opinion_id, citing_opinion_id), so loading their CSV is a
-- direct import rather than a transformation.

CREATE TABLE IF NOT EXISTS opinions (
    id            INTEGER PRIMARY KEY,
    citation      TEXT NOT NULL UNIQUE,
    case_name     TEXT,
    court         TEXT,
    date_filed    TEXT,
    url           TEXT,
    text          TEXT NOT NULL DEFAULT '',
    -- 1 when the body text is invented sample data rather than a real opinion.
    -- The auditor refuses to present synthetic text as a real court record.
    is_synthetic  INTEGER NOT NULL DEFAULT 0,
    source        TEXT NOT NULL DEFAULT 'unknown'
);

CREATE INDEX IF NOT EXISTS idx_opinions_citation ON opinions(citation);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    opinion_id  INTEGER NOT NULL REFERENCES opinions(id) ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL,
    text        TEXT NOT NULL,
    UNIQUE (opinion_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_chunks_opinion ON chunks(opinion_id);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id  INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    model     TEXT NOT NULL,
    dim       INTEGER NOT NULL,
    vector    BLOB NOT NULL        -- float32 array; becomes vector(dim) in Postgres
);

-- Which opinion cites which. Powers the "is it still good law?" check.
CREATE TABLE IF NOT EXISTS cites (
    citing_opinion_id  INTEGER NOT NULL,
    cited_opinion_id   INTEGER NOT NULL,
    depth              INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (citing_opinion_id, cited_opinion_id)
);

CREATE INDEX IF NOT EXISTS idx_cites_cited ON cites(cited_opinion_id);
