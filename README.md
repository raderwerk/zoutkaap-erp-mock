# zoutkaap-erp-mock

ERP-nabootsing van Zoutkaap: een echte, draaiende REST-service met een automatisch gegenereerde OpenAPI-beschrijving voor producten, voorraad en orders.

## Doel

Zoutkaap verkoopt zoutwaterbestendige buitenkleding via een eigen Shopify-webshop, maar voorraad en orders worden nu met de hand overgetikt tussen de shop en het ERP. Deze service bootst dat ERP na, zodat `zoutkaap-erp-bridge` (de middleware) er een echte voorraadsync en orderdoorgifte tegenaan kan bouwen en testen, inclusief foutscenario's, zonder dat er een echt ERP-contract nodig is.

## Klant

[Zoutkaap](https://github.com/raderwerk) is een demonstratiebedrijf van Raderwerk en bestaat niet. Zie `raderwerk/hq` voor het volledige klantdossier.

## Stack

Python 3.12 + [FastAPI](https://fastapi.tiangolo.com/). Gekozen omdat FastAPI de OpenAPI-beschrijving die dit project als kernvereiste heeft (producten, voorraad, orders) automatisch uit de code genereert (`/openapi.json`, interactief op `/docs`), in plaats van dat die spec los onderhouden moet worden.

## Lokaal draaien

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

De service draait dan op poort **8000**. Interactieve documentatie op `http://localhost:8000/docs`, de ruwe OpenAPI-spec op `http://localhost:8000/openapi.json`.

## Checks draaien

```bash
ruff check .
pytest -q
```

Beide moeten slagen voordat je een pull request opent; de `ci`-workflow draait exact dezelfde twee commando's.

## Bijdragen via PR

1. Vertak vanaf `main`.
2. Draai `ruff check .` en `pytest -q` lokaal; los alles op voordat je pusht.
3. Open een pull request met het sjabloon (wat, waarom, bewijs, DoD-checklist).
4. `main` is beschermd: een pull request met een geslaagde `ci`-check is verplicht. Een mens keurt goed en merget; agents mergen nooit zelf.

Zie `AGENTS.md` voor de volledige scope, Definition of Done en verboden acties voor AI-agents die aan deze repo werken.
