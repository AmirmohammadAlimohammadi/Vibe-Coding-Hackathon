# Deploying the Liara assistant

Liara does not run `docker-compose.yml` directly. Deploy the system as one application,
two managed databases, and one Qdrant Docker application, all in the same private network:

```text
Internet -> assistant Docker app (React + FastAPI, port 8000)
                         |-> PostgreSQL DBaaS
                         |-> Redis DBaaS
                         `-> Qdrant Docker app (port 6333 + persistent disk)
```

The repository root `Dockerfile` builds the React frontend and copies it into the FastAPI
runtime image. The browser and API therefore use one domain, and only the assistant app
needs to be connected to GitHub.

## 1. Push a deployment commit

Push the repository to GitHub with these files at its root:

- `Dockerfile`
- `liara.json`
- `backend/`
- `apps/`
- `packages/`
- the Node workspace and lock files

Never commit `backend/.env`, a filled production env file, database dumps, or Qdrant
snapshots. They are excluded from the production build context or Git where applicable.

## 2. Create one private network

In Liara Console, create a private network for this project. Select this same network when
creating the assistant application, PostgreSQL, Redis, and Qdrant. A service in a shared
private network is addressed with its Liara service identifier as the hostname.

The private network cannot be changed after a service is created. Recreate a service if it
was accidentally placed in a different network.

## 3. Create PostgreSQL and Redis

Create a PostgreSQL 16 database and a Redis database from Liara's managed database page.
Place both in the project private network. Public access is unnecessary after migration.

Copy each private connection URI from the database's **Connection** page. They become the
assistant application's `DATABASE_URL` and `REDIS_URL` values.

Redis contains OTPs, rate-limit counters, and cache data, so its local volume should not be
migrated. Start production Redis empty.

If local users and chats must be preserved, export PostgreSQL before deployment:

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
docker compose exec postgres pg_dump -U chatbot -d chatbot -Fc -f /tmp/chatbot.dump
docker cp liara-chatbot-postgres:/tmp/chatbot.dump ./backups/chatbot.dump
```

Temporarily enable public database access and restore the dump using the public connection
details shown by Liara:

```bash
pg_restore --no-owner --no-privileges \
  --host=DB_HOST --port=DB_PORT --username=DB_USERNAME \
  --dbname=DB_NAME backups/chatbot.dump
```

Disable public database access after verifying the restore. Skip this restore when there is
no local chat history worth preserving; the backend creates its tables at startup.

## 4. Deploy Qdrant with a disk

Create a separate **Docker** application for Qdrant in the private network. Set the
following environment variable in Liara Console before exposing the service:

```env
QDRANT__SERVICE__API_KEY=generate-a-long-random-secret
```

Create a disk named `qdrant-data`, then deploy the official image with port `6333` and mount
the disk at the absolute path `/qdrant/storage`. The example configuration is in
`deploy/liara/qdrant/liara.json.example`. With Liara CLI, after replacing the app ID:

```bash
liara deploy --platform=docker
```

Alternatively, select `qdrant/qdrant:v1.15.3` in the Console image-deployment flow and
attach the disk there. Use the exact version initially so the source and target Qdrant
formats match. The first deployment changes the disk state from **Ready** to **In use**.

### Move the existing vectors

Create and download a consistent collection snapshot from local Qdrant:

```bash
docker compose --profile tools run --rm export-qdrant-snapshot
```

The snapshot is written under `backups/` and contains the dense vectors, sparse vectors,
payloads, and collection configuration. It does not call the embedding provider.

Upload the resulting `.snapshot` file to the public Qdrant application URL:

```bash
curl -X POST \
  "https://QDRANT_PUBLIC_DOMAIN/collections/liara_documentation_hybrid/snapshots/upload?priority=snapshot" \
  -H "api-key: YOUR_QDRANT_API_KEY" \
  -F "snapshot=@backups/YOUR_SNAPSHOT_FILE.snapshot"
```

This restores the collection into the attached Liara disk. Do not copy the live raw Docker
volume while Qdrant is running; snapshots are consistent and portable. Liara FTPS disk
access is useful for ordinary files, but the Qdrant snapshot API is the safer migration
mechanism for this database.

Verify the collection and point count:

```bash
curl "https://QDRANT_PUBLIC_DOMAIN/collections/liara_documentation_hybrid" \
  -H "api-key: YOUR_QDRANT_API_KEY"
```

The restored collection should report the same point count as local Qdrant. Keep the disk
attached for every later Qdrant deployment. Create Liara disk backups before upgrades.

## 5. Create the assistant Docker application

Create one Docker application for the assistant in the same private network. The app must
listen on port `8000`; the checked-in `liara.json` already configures the root Dockerfile,
port, timezone, and `/health` deployment check.

The main application does not require a disk. Its persistent state lives in PostgreSQL,
Redis, and the Qdrant disk.

## 6. Set production environment variables

Copy `deploy/liara/app.env.example` to a file outside Git or fill it locally. Replace every
placeholder. In the assistant application, open **Settings -> Variables -> Upload ENV** and
upload that completed file.

Important values:

```env
DATABASE_URL=the-private-postgresql-uri-from-liara
REDIS_URL=the-private-redis-uri-from-liara
QDRANT_URL=http://YOUR_QDRANT_APP_ID:6333
QDRANT_API_KEY=the-same-value-as-QDRANT__SERVICE__API_KEY
QDRANT_COLLECTION=liara_documentation_hybrid
```

Generate independent authentication secrets locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use one result for `AUTH_TOKEN_SECRET` and the other for `OTP_HASH_SECRET`. Never place
secrets in `liara.json`; GitHub deployments read them from the Liara application settings.

## 7. Connect GitHub and deploy

1. Open Liara account settings and connect the GitHub account.
2. Edit GitHub access and grant Liara access to this repository.
3. Open the assistant app and select **New deployment -> GitHub**.
4. Select the repository, deployment branch, and automatic or manual deployment mode.
5. Connect the repository to the application.
6. Start the first manual deployment.

Do not add `app` or `platform` to the root `liara.json`; Liara determines both from the
GitHub-connected application. During the build, the multi-stage image compiles React and
installs the Python dependencies. At runtime FastAPI serves both the API and frontend.

## 8. Verify production

Check these URLs after the deployment becomes healthy:

```text
https://ASSISTANT_DOMAIN/          React login and chat UI
https://ASSISTANT_DOMAIN/health    {"status":"ok"}
https://ASSISTANT_DOMAIN/docs      Swagger UI
```

Then verify this complete flow:

1. Request and receive an email OTP.
2. Verify the OTP and obtain an authenticated session.
3. Send a documentation question and watch the answer stream incrementally.
4. Refresh the page and confirm the chat remains in history.
5. Inspect application events and logs for database, Qdrant, SMTP, or AvalAI errors.

If `/health` fails during deployment, check the private connection URIs first. The backend
initializes PostgreSQL during startup, so an invalid `DATABASE_URL` prevents it from becoming
healthy. A Qdrant or AvalAI failure affects queries but does not prevent application startup.
