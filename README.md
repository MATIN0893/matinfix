# MATINFIX

MATINFIX is an independent repair-service operations platform by MATIN.

This repository is completely separate from FAINA and does not reuse its code or architecture.

## Initial architecture
- FastAPI API
- PostgreSQL-ready persistence layer
- Redis-ready workers
- Telegram bot interface
- Mini App / web dashboard
- Deterministic Price Engine
- CRM, repairs, inventory, accounting and knowledge modules

## Core rule
LLMs may interpret intent and route requests, but customer-facing prices must come only from authoritative pricing providers or explicitly configured rules. The AI must never invent, round, or calculate a price.

## Development
See `pyproject.toml` and `.env.example` for the initial local setup.
