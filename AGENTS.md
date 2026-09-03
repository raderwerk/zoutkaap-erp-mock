# AGENTS.md

Instructies voor Codex, Cursor en Claude die aan deze repo werken. Zie ook `raderwerk/hq` voor het klantportfolio, het Linear-werkplaatsontwerp en het agentrooster.

## Scope van deze repo

`zoutkaap-erp-mock` is de ERP-nabootsing van klant Zoutkaap (fictief): een echte, draaiende REST-service met een automatisch gegenereerde OpenAPI-beschrijving voor **producten, voorraad en orders**. Deze repo bootst het ERP na waar `raderwerk/zoutkaap-erp-bridge` (de middleware) tegenaan synct en waarvan `raderwerk/zoutkaap-shop` (de Shopify-theme) de voorraad toont.

Wat hier wél thuishoort:
- Endpoints en datamodellen voor producten, voorraad en orders.
- Opwekbare foutscenario's (bijv. trage responses, 4xx/5xx, kapotte payloads) waarmee de bridge-repo retry en idempotentie kan testen.
- De OpenAPI-spec die uit deze code voortkomt.

Wat hier niet thuishoort:
- Shopify-theme-code (hoort in `zoutkaap-shop`).
- Voorraadsync- of orderdoorgiftelogica (hoort in `zoutkaap-erp-bridge`); deze repo is de service die gesynct wordt, niet de sync zelf.
- Echte klantdata of echte credentials. Alles is testdata; er gaat geen bericht naar een echt mens en er wordt geen euro uitgegeven.

## Definition of Done

Deze repo valt onder dienstlijn `dienst/web` (route: Codex, zie `client-portfolio.md` issue Z02). De DoD komt uit het `Feature`-issuesjabloon in `linear-workspace-spec.md` (§5.4), toegepast op een backend-service in plaats van een frontend:

- [ ] Elk acceptatiecriterium uit het issue afgevinkt met een link naar bewijs.
- [ ] Tests voor het gelukkige pad en minimaal één foutpad; volledige suite groen, uitvoer in de PR of comment.
- [ ] PR geopend met beschrijving en groene `ci`-check (ruff + pytest).
- [ ] Twee onafhankelijke reviews afgerond, uit verschillende modelfamilies (zie agentrooster).
- [ ] `ruff check .` levert geen bevindingen op.
- [ ] Geen geheimen in de repo, geen productiecredentials gebruikt.
- [ ] README of `AGENTS.md` bijgewerkt als het gedrag of de scope verandert.
- [ ] De OpenAPI-spec (`/openapi.json`) blijft consistent met de daadwerkelijke endpoints; geen los bijgehouden spec-bestand dat uit de pas kan lopen.

De UI-specifieke DoD-punten uit §5.4 (toetsenbordpad, contrast, 360/768/1440 px) zijn hier niet van toepassing: deze repo heeft geen frontend.

## PR-conventies

- Branch: `feat/<issue-kort>` of `fix/<issue-kort>`.
- Commits en PR-titel/-beschrijving in het Engels.
- Draai vóór het openen van een PR altijd:
  ```bash
  ruff check .
  pytest -q
  ```
  Dit zijn exact de commando's die de `ci`-workflow draait; een lokaal groene run voorkomt verrassingen.
- Onderteken je PR-beschrijving of samenvattende comment met je rol, bijvoorbeeld `**Ontwikkelaar · Opus 5 · run <id> · <tijd>**`. Codex en Cursor tekenen niet expliciet: hun agent-sessie is de handtekening.

## Verboden acties

- **Nooit mergen.** Een mens keurt goed en merget bij de mergepoort.
- **Nooit force-pushen** naar `main`.
- **Nooit deployen.** Deze repo heeft geen GitHub Pages en geen productie-deploy; hij draait alleen lokaal en in CI.
- **Nooit geheimen** toevoegen, loggen, of om vragen (API-sleutels, tokens, wachtwoorden). Er zijn geen echte credentials nodig: het is een nagebouwde service met testdata.
- **Nooit** buiten deze werkplaats communiceren of doen alsof Zoutkaap een bestaand bedrijf is.
