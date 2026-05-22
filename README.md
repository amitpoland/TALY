# TALY Local App

Start the local desktop-first web app with one command:

```bash
./scripts/start-local.sh
```

Or double-click:

```text
Start_TALY.command
```

The launcher:

- seeds the local foundation data, including the active local operator user
- builds the frontend
- starts the backend on `http://127.0.0.1:8010`
- serves the app from `http://127.0.0.1:8010`
- opens the browser automatically
- writes logs to `app-data/logs/`

Stop the managed local servers with:

```bash
./scripts/stop-local.sh
```
