-- Rollback for: 0001_add_keycloak_user_id
--
-- Running this removes the Keycloak link for every user. Only run it if the
-- Keycloak integration is being abandoned. Nothing else in the schema depends
-- on this column, so no other table is affected.

BEGIN;

DROP INDEX IF EXISTS identity.uq_users_keycloak_user_id;

ALTER TABLE identity.users
  DROP COLUMN IF EXISTS keycloak_user_id;

COMMIT;
