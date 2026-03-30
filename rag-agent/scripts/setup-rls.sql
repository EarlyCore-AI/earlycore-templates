-- EarlyCore RAG Agent -- PostgreSQL Row-Level Security (RLS) setup
--
-- Run this script after the initial schema migration to enable tenant isolation
-- on all pgvector tables. The application MUST call:
--
--   SET app.current_tenant_id = '<client_name>';
--
-- on every connection before executing queries.
-- ---------------------------------------------------------------------------

-- 1. Enable RLS on the documents table (pgvector embeddings + metadata)
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners (defence-in-depth)
ALTER TABLE documents FORCE ROW LEVEL SECURITY;

-- 2. Tenant isolation policy: each row only visible to its owning tenant
CREATE POLICY tenant_isolation_select ON documents
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation_insert ON documents
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation_update ON documents
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation_delete ON documents
    FOR DELETE
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- 3. Ensure tenant_id column exists (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE documents ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '';
        CREATE INDEX idx_documents_tenant_id ON documents (tenant_id);
    END IF;
END $$;
