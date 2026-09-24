# Access and credential handoff

Give collaborators access by responsibility. This file is an inventory and
handoff checklist; it contains no password, token, connection string, or
private key. Share any required secret through an approved encrypted password
manager or one-to-one secure channel, never through Git, a PR, a group chat,
an AI prompt, or a terminal command that prints it. Ask teammates to keep
their agents' tool output free of secret values.

## What Manushan should grant

| Collaborator task | Access to provide | Where it currently lives / boundary |
| --- | --- | --- |
| Read code, make PRs, review CI | Invite the person's own GitHub account to `Smart-Attendance-Group-27/smart-attendance-platform` with the needed repository role. They use their own GitHub CLI login. | No need to share Manushan's GitHub token or CLI credentials. Branch protection and PR review remain in force. |
| Run the web/mobile attendance pilot | Provide only the relevant mock Keycloak lecturer or student login through a secure channel. | Account names appear in the [pilot guide](../home-attendance-pilot.md). Random passwords are in Manushan's protected local `C:\Users\LOQ\.uniattend-backups\pilot-logins.txt`, outside Git and the VPS. A tester does not need VPS, Supabase, or Keycloak-admin access. |
| Change courses and classrooms through the UI | Give a designated administrator the mock administrator login after the academic-options fix is deployed. | The same protected login file contains the test administrator password. Current Core returns 500 on the options endpoint until PR #97 is released. |
| Operate or deploy the VPS | Approve a named operator and install that person's **public** SSH key. Prefer a separate Linux account with narrowly assigned sudo and auditability; the existing `uniattend` account has passwordless sudo and therefore full host access. | Host: `152.53.33.198`. Do not distribute the owner private SSH key, root password, or a shared SSH login secret. An operator can use the existing protected env on-host rather than copying it to a laptop. |
| Run GitHub release workflows or pull private GHCR images | Grant the person's GitHub account the appropriate repo/package permission. If direct private GHCR pull is used on the VPS, arrange a dedicated package-read credential through the protected procedure in the runbook. | Main-branch Actions publish SHA-tagged images. The current VPS was built from source because no read-package credential was supplied to the host. Do not put a token in a PR, shell argument, Dockerfile, or Compose file. |
| Apply an application database migration | Limit to a named database operator. Invite them to the Supabase project with the least role that permits the task, review the exact SQL and backup first, and use a controlled migration job. | The active Supabase pooler URI is in `/etc/uniattend/private.env` and the owner workstation's ignored `.env`; neither belongs in Git. Most contributors need only a local/sanitized database. |
| Manage Keycloak realm or clients | Give one identity operator the necessary admin access and a private tunnel/host path. | Keycloak's public `/admin/*` route is blocked. Bootstrap admin credentials and client secrets are in protected deployment config. Test-role passwords do not grant realm administration. |
| Restore backups | Name one recovery custodian, share the encrypted archive and decryption material separately only when needed, and test in an isolated container. | Encrypted Keycloak archives exist on the VPS and owner workstation; the age private key is only off-host. Encrypted Supabase archives and their keys are in the owner's protected backup directory. Never restore over the live Keycloak volume for a drill. |
| Manage provider billing or emergency console | Keep with Manushan or a specifically delegated billing operator. | netcup customer portal and root recovery password are separate from normal SSH deployment. Their values are not in this repository. |
| Build or install the Android pilot APK | Share the internal APK through a controlled file transfer, or have the developer build from source with the HTTPS origins in `apps/mobile/eas.json`. Verify the artifact hash before install. | Owner artifact: `C:\Users\LOQ\.uniattend-artifacts\uniattend-pilot-arm64-5f923545d.apk`; SHA-256 `FBFF880D41000BC2DC51EEF74D9A3A71BD5836E4789009A3A2A1A01D05DF6103`. This is debug-signed and not a public store release. |

Cloudflare R2 and a permanent-domain DNS account **do not exist for this
pilot yet**, so there are no R2 or DNS credentials to hand over. The temporary
`sslip.io` hostnames need no account. If R2 or a domain is created, record the
owner and provision scoped access then; do not reuse VPS or database secrets.

## Deployment configuration names

The public hostname template is `deployment/public.env.example`; the
protected app template is `deployment/private.env.example`. The actual
`/etc/uniattend/private.env` holds, among others, `CORE_DB_URI`,
`FACE_DB_URI`, `FACE_EMBEDDING_ENCRYPTION_KEY`, Keycloak database/admin/client
secrets, `WEB_SESSION_SECRET`, and `DYNAMIC_QR_HMAC_SECRET`. The realm import
file is also protected. Team members need the **variable names and code
paths** to work on the deployment; only designated operators need values.
The repository root `.env` on Manushan's workstation is ignored by Git and
contains sensitive development values. Do not copy it into a shared archive.

## Minimum handoff by role

1. **Feature developer or AI agent:** repository access, this handoff, local
   sample env files, a development database, and the assigned PR. No live
   secret by default.
2. **Attendance tester:** only one lecturer and one student mock login plus
   the web URL or internal APK. Keep test results free of passwords and raw
   coordinates.
3. **Deployment operator:** own GitHub account, own SSH key and approved VPS
   account, read access to the on-host config, and the release runbook. Add
   Supabase or Keycloak admin rights only for a task that needs them.
4. **Recovery custodian:** encrypted backup archives and separately protected
   decryption keys, plus the restore procedure and a non-live restore target.

Rotate any shared pilot login after handoff or when a collaborator no longer
needs it. Record who has each privileged access and revoke it at pilot end.
