# notion_migration

Lightweight migration tooling and helpers for working with Notion pages and databases.

This repository provides a small abstraction over the Notion API and a thin service layer that contains domain logic and schema-level queries.

## Goals

- Provide testable, composable primitives for reading and writing Notion pages.
- Separate persistence concerns (pagination, API shape) from domain concerns (which property to query, validation, business flows).

## Layout

The code lives under `src/notion_migration`:

- `models/` — domain data classes (ClientPage, properties, relations)
- `repo/` — repository interfaces and implementations (persistence primitives, pagination, translation to provider API)
- `service/` — domain/service layer (compose repo calls, validation, business rules)

Top-level `tests/` contains unit tests.

## Setup

This project uses Poetry. From the repo root:

```bash
poetry install
poetry shell
```

For integration scenarios, set your Notion token in the environment:

```bash
export NOTION_TOKEN="<your-token>"
```

## Running tests

```bash
pytest -q
```

## Repo vs Service: where does `query_descendants_of_parent` live?

Short answer: put domain intent in the service, persistence translation in the repo.

Rationale:

- Service: expresses "what" you want (e.g. "descendants of parent X") and performs validation and composition.
- Repo: implements "how" to run queries against the provider (Notion JSON shape, pagination, retries) and maps raw responses to domain models.

Approaches you can choose:

1. Service-only (recommended): service constructs a domain-level intent and calls `repo.query_database(database_id, filter)`; the repo handles provider details.

2. DomainFilter abstraction: service builds a small DomainFilter object (e.g. `AncestorContains(parent_id)`) and repo translates it to provider JSON before calling Notion. Useful when you want stronger typing and many predicates.

3. Pragmatic: service builds provider-shaped JSON and passes it to repo. Works for small projects but couples service to provider JSON.

Prefer option 1 or 2 for maintainability and testability.

## Example (service-focused)

```py
from src.notion_migration.repo.repo_page_interface import RepoPageInterface
from src.notion_migration.service.page_service import PageService

repo: RepoPageInterface = NotionClientAPI()  # your repo implementation
svc = PageService(repo=repo)
pages = svc.query_descendants_of_parent(parent_page_id="parent-123", database_id="db-abc")
```

## Repo Structure
This project is a monorepo handled py `uv`. The members' structure is as follows:
- `/packages` contain the libraries package, which are common requirements for the apps. They contain data models among other things.
- `/apps` contain the apps members: currently the `migration-engine`.
- the root is a non-package member.
- each member has their own dev dependencies, and therefore are responsible for their own linting, type checking and testings. But they share the common standard they inherit from at the root `pyproject.toml`.

## Setup
Docker compose takes care of containerizing and launching the apps with a local network they're at. The context is the root directory and all the `Dockerfile`s assume the root dir as their contexts too.

## Tests guidance

- Service unit tests: mock/fake the repo and assert the service expresses the correct domain intent.
- Repo unit tests: validate translation of domain intent to provider API calls and correct pagination/response mapping.

## Contributing

PRs welcome. Add unit tests for changes and aim to keep interfaces backward-compatible.

## License

MIT
