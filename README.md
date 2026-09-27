# FFH Translation Service

Lightweight self-hosted machine-translation service for **Fermenting Foods for Health (FFH)**.

## Scope
This deliberately supports only the directions FFH currently needs:
- English → Spanish
- English → French
- English → Japanese

It uses Argos Translate directly rather than the full LibreTranslate application.

## API
- `GET /health` — health check
- `GET /languages` — LibreTranslate-style language metadata
- `POST /translate` — accepts JSON `q`, `source`, and `target`, returning `translatedText`

Only `source=en` and targets `es`, `fr`, and `ja` are accepted.

## Deployment
`render.yaml` defines a Render Python web service. `install_models.py` installs only the three required Argos models at build time. Gunicorn runs one worker and one thread to keep runtime resource use controlled.

## FFH policy
Machine translations are candidates, not approved terminology or publication-ready translations. FFH's database remains authoritative for reviewed terminology, safety-critical language, translation memory, and human verification.

This repository contains no Supabase, Render, Netlify, or other credentials.

Validate deployment memory, cold-start behaviour, and all three translation directions before connecting the FFH production worker.
