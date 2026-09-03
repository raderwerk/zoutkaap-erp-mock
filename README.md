# zoutkaap-erp-mock

Een echte, lokaal draaiende REST-nabootsing van het fictieve Zoutkaap-ERP. De service bevat een deterministische catalogus met 24 testartikelen en persistente SQLite-data voor artikelen, voorraad, prijzen en orders.

> Zoutkaap is een demonstratiebedrijf van Raderwerk en bestaat niet. Alle data en de API-sleutel in deze repository zijn uitsluitend lokale testdata.

## Lokaal draaien

Python 3.12 of nieuwer is vereist.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

De API draait vervolgens op `http://localhost:8000`. De interactieve documentatie staat op [`/docs`](http://localhost:8000/docs); de uit de routes gegenereerde en geteste OpenAPI-beschrijving staat op [`/openapi.json`](http://localhost:8000/openapi.json). Er wordt bewust geen tweede, handmatig bijgehouden OpenAPI-bestand opgeslagen.

Standaard wordt de SQLite-database geschreven naar `instance/zoutkaap.sqlite3`. Dit pad is instelbaar met `ZOUTKAAP_DATABASE`.

## Publiek als preview uitrollen

De repository bevat een `Dockerfile` en een Render Blueprint (`render.yaml`). Daarmee kan een
mens de service in één handeling als publieke preview uitrollen, zonder lokaal een image te
bouwen:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/raderwerk/zoutkaap-erp-mock)

1. Klik op **Deploy to Render**, kies de branch van de pull request en bevestig de Blueprint.
2. Wacht tot `/health` op de door Render toegewezen URL `200 OK` geeft.
3. Kopieer de publieke URL naar een attachment bij WV-171. De automatisch gegenereerde waarde
   van `ZOUTKAAP_API_KEY` staat in de omgevingsvariabelen van de Render-service en is nodig voor
   de bedrijfsroutes.

De gratis preview gebruikt tijdelijke SQLite-opslag. Een nieuwe instantie seedt zichzelf daarom
automatisch met de 24 testartikelen. Dit manifest is alleen deployvoorbereiding; agents voeren de
deploy niet zelf uit.

## Authenticatie

Alle bedrijfs- en beheerroutes vereisen de header:

```http
X-API-Key: zoutkaap-local-demo-key
```

Dit is een publieke ontwikkelsleutel, **geen geheim of productiecredential**. Stel voor een andere lokale waarde de omgevingsvariabele `ZOUTKAAP_API_KEY` in voordat de server start. Een ontbrekende of onjuiste sleutel geeft `401 Unauthorized`. Alleen `/health`, `/docs` en `/openapi.json` zijn publiek.

Voorbeeld:

```bash
curl -H 'X-API-Key: zoutkaap-local-demo-key' http://localhost:8000/articles
```

## REST-routes

| Domein | Methode en route | Gedrag |
| --- | --- | --- |
| Artikelen | `GET /articles` | Alle 24 artikelen |
| Artikelen | `GET /articles/{sku}` | Eén artikel |
| Voorraad | `GET /inventory` | Alle voorraadstanden |
| Voorraad | `GET /inventory/{sku}` | Voorraadstand per SKU |
| Prijzen | `GET /prices` | Alle prijzen in eurocenten |
| Prijzen | `GET /prices/{sku}` | Prijs per SKU |
| Orders | `POST /orders` | Order aanmaken en voorraad afboeken |
| Orderstatus | `GET /orders/{order_id}/status` | Actuele status van een order |
| Beheer | `POST /admin/seed` | Data binnen de draaiende service resetten |

De precieze request- en responsemodellen, foutresponses en authenticatie staan altijd actueel in de interactieve OpenAPI-documentatie.

## Bewust fouten opwekken

Stuur op een geauthenticeerde route de testheader `X-Test-Status` met exact `404`, `429` of `500`. De API antwoordt dan onmiddellijk met die status. Een geforceerde `429` bevat altijd `Retry-After: 2`.

```bash
curl -i \
  -H 'X-API-Key: zoutkaap-local-demo-key' \
  -H 'X-Test-Status: 429' \
  http://localhost:8000/articles
```

Andere waarden zijn ongeldig en leveren FastAPI's reguliere `422`-validatiefout op. De testheader is ook als parameter zichtbaar in de OpenAPI-beschrijving.

## Startstaat herstellen

Herstel in één commando de 24 oorspronkelijke artikelen en voorraadstanden en verwijder alle orders:

```bash
python -m app.seed
```

Het commando gebruikt hetzelfde `ZOUTKAAP_DATABASE`-pad als de service. Voor een reeds draaiende service kan hetzelfde atomair met:

```bash
curl -X POST -H 'X-API-Key: zoutkaap-local-demo-key' http://localhost:8000/admin/seed
```

## Checks

```bash
ruff check .
pytest -q
```

Deze commando's zijn gelijk aan de CI-checks. De tests dekken onder andere authenticatie, alle vier domeinen, order/voorraadgedrag, alle drie geforceerde fouten, de `Retry-After`-header, resetgedrag en validatie van de gegenereerde OpenAPI-beschrijving.

## Bijdragen

Werk via een feature- of fix-branch en open een pull request naar `main`. Een mens keurt goed en merget; agents mergen en deployen nooit. Zie `AGENTS.md` en `CLAUDE.md` voor alle werkafspraken.
