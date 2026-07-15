# Email Data Extraction

This project extracts useful business entities from PDF email records.

It reads PDF files, sends the text to a local Presidio + GLiNER API, applies custom validation rules, and saves clean extracted data into JSON.

## What it extracts

The system can extract:

- Email addresses
- Email dates
- Date/time values
- Person names
- Bank account numbers
- Bankruptcy/case numbers
- Singapore vehicle numbers
- Singapore NRIC/FIN numbers
- Phone/mobile numbers
- Passport numbers
- URLs
- Locations
- Job titles
- Organizations
- Creditor names
- Bankrupt names
- Law firms
- Government agencies

## Project structure

```text
.
├── app.py                         # API service
├── proces_pdfs.py                 # Reads PDFs and saves JSON output
├── entity_rules.py                # Conditions/validation for each entity
├── entity_collector.py            # Cleans, validates, deduplicates entities
├── recognizers/
│   ├── business_recognizers.py    # Bank, phone, date, bankruptcy patterns
│   ├── gliner_recognizer.py       # AI-based entity recognizer
│   └── singapore_recognizers.py   # Singapore-specific recognizers
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── ENTITY_GUIDE.md
```

## How it works

Simple flow:

```text
PDF files
   ↓
proces_pdfs.py reads PDF text
   ↓
Text is sent to the API
   ↓
Presidio + GLiNER detect possible entities
   ↓
entity_rules.py checks conditions
   ↓
entity_collector.py cleans and removes duplicates
   ↓
pdf_extracted_entities.json is created
```

## Setup

Create and activate a Python virtual environment if needed.

Install requirements:

```powershell
pip install -r requirements.txt
```

## Run the API

Start the Docker API:

```powershell
docker compose up --build
```

The API will run at:

```text
http://localhost:5001
```

Health check:

```text
http://localhost:5001/health
```

## Process PDFs

Put PDF files inside a folder named:

```text
pdfs
```

Then run:

```powershell
python proces_pdfs.py
```

The output will be saved as:

```text
pdf_extracted_entities.json
```

## Output format

The output is one JSON object per PDF.

Example:

```json
[
  {
    "EmailMessageId": 1,
    "SourceFileName": "Vehicle - 2.pdf",
    "ExtractionEngine": "presidio-analyzer",
    "ModelName": "gliner + pattern recognizers",
    "LanguageCode": "en",
    "TotalEntitiesFound": 13,
    "EMAIL_ADDRESS": [],
    "EMAIL_DATE": ["16 June 2026"],
    "DATE_TIME": ["2:30 PM", "16 June 2026"],
    "PERSON": ["Ms Kamila", "Lin Yueh Hung"],
    "BANK_ACCOUNT_NUMBER": [],
    "BANKRUPTCY_NUMBER": ["B/668/2024"],
    "SG_VEHICLE_NUMBER": ["SMD4125Y"],
    "SG_NRIC_FIN": [],
    "PHONE_NUMBER": [],
    "PASSPORT_NUMBER": [],
    "URL": [],
    "LOCATION": [],
    "JOB_TITLE": ["Executive"],
    "ORGANIZATION": [],
    "CREDITOR_NAME": [],
    "BANKRUPT_NAME": ["Mr Lin Yueh Hung"],
    "LAW_FIRM": [],
    "GOVERNMENT_AGENCY": ["LAND TRANSPORT AUTHORITY OF SINGAPORE"]
  }
]
```

If 7 PDFs are processed, the output will contain 7 main JSON objects.

## API usage

Analyze text directly:

```powershell
curl -X POST http://localhost:5001/analyze `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Tel: +6590681834. Vehicle SMD4125Y. Case HC/B/668/2024.\",\"language\":\"en\"}"
```

List supported entity types:

```text
http://localhost:5001/entity-types
```

## Adding a new entity

To add a new entity later:

1. Add a recognizer pattern in:

```text
recognizers/business_recognizers.py
```

2. Add validation logic in:

```text
entity_rules.py
```

3. Add the entity name to `TARGET_ENTITIES` in:

```text
proces_pdfs.py
```

The basic idea is:

```text
Recognizer finds possible values.
Entity rule decides if the value is correct.
PDF processor includes it in the final output.
```

## Files not recommended for GitHub

Do not upload:

```text
.venv/
.venv312/
pdfs/
pdf_extracted_entities.json
analyze_output.json
email_entity_link.json
email_extracted_entities.json
```

These are local/generated files.

## Main commands

Start API:

```powershell
docker compose up --build
```

Run PDF extraction:

```powershell
python proces_pdfs.py
```

Rebuild after changing recognizers/rules:

```powershell
docker compose down
docker compose up --build
```
