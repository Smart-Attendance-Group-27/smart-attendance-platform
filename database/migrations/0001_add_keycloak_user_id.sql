-- Migration: 0001_add_keycloak_user_id
-- Purpose:   Link an application user to its Keycloak account.
--
-- Keycloak is the authentication provider. Its `sub` claim is an opaque string
-- that identifies the Keycloak account. This migration stores that string next
-- to the application user so the backend can resolve a token to the internal
-- identity.users.id, which stays the permanent application user ID.
--
-- This migration is additive and reversible:
--   * no column is dropped or renamed
--   * no data is deleted
--   * the legacy password, refresh-token, reset-token and lockout columns and
--     the identity.roles / identity.user_roles tables are all left untouched
--
-- The partial unique index allows many rows with NULL (users not yet linked)
-- while guaranteeing that one Keycloak account maps to at most one app user.
--
-- Apply with the Supabase SQL editor or psql. Never put database credentials
-- into this file or into the command used to run it.

BEGIN;

ALTER TABLE identity.users
  ADD COLUMN IF NOT EXISTS keycloak_user_id VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_keycloak_user_id
  ON identity.users (keycloak_user_id)
  WHERE keycloak_user_id IS NOT NULL;

COMMENT ON COLUMN identity.users.keycloak_user_id IS
  'Opaque Keycloak subject (sub) claim. NULL until the account is linked.';

COMMIT;
