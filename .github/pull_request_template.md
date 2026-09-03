## Wat

<!-- Wat verandert er in deze PR, in één tot drie zinnen. -->

## Waarom

<!-- Welk issue of welke aanleiding. Link naar het Linear-issue als dat er is. -->

## Bewijs

<!-- Testuitvoer, curl-voorbeeld, screenshot van /docs, of link naar een preview. -->

```
$ ruff check .
$ pytest -q
```

## DoD-checklist

- [ ] Elk acceptatiecriterium uit het issue afgevinkt met een link naar bewijs
- [ ] Tests voor het gelukkige pad en minimaal één foutpad; volledige suite groen
- [ ] `ruff check .` levert geen bevindingen op
- [ ] CI (`ci`-check) is groen
- [ ] Twee onafhankelijke reviews, uit verschillende modelfamilies
- [ ] Geen geheimen of productiecredentials in de diff
- [ ] README of AGENTS.md bijgewerkt als het gedrag of de scope verandert

## Poort

<!-- Draait lokaal op poort 8000. Geen deploy vanuit deze repo; een mens keurt goed en merget. -->
