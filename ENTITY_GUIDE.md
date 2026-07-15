# Entity collection

`app.py` now returns only validated and deduplicated entities. Detection and
acceptance are separate:

1. Presidio, GLiNER, and pattern recognizers propose candidates.
2. `entity_rules.py` checks confidence, format, and nearby context.
3. `entity_collector.py` normalizes values and removes duplicates.

## API request

```json
{
  "text": "Email sent on 23 Jun 2026 by John Doe. Account: 123-456-789.",
  "language": "en",
  "entities": ["EMAIL_DATE", "PERSON", "BANK_ACCOUNT_NUMBER"]
}
```

Omit `entities` to collect every configured type. Use `GET /entity-types` to
see the available types and their minimum confidence.

## Adding an entity

1. Add a recognizer in `recognizers/business_recognizers.py` when the entity
   has a reliable text pattern. For semantic entities, add its GLiNER label in
   `recognizers/gliner_recognizer.py`.
2. Add one `EntityRule` entry in `ENTITY_RULES` with its minimum score,
   validator, and normalizer.
3. Add examples and false-positive cases to the collector test.

Never accept an identification number using its shape alone. Require nearby
labels such as `account`, `passport`, `vehicle`, or `case number`.
