# Email Data Extraction and Anonymization

This project extracts and anonymizes business entities from email text stored in PDF files. It is designed for Singapore-specific identifiers while also supporting general entities such as people, email addresses, dates, locations, organizations, and URLs.

The application combines:

- Microsoft Presidio as the entity-analysis framework.
- GLiNER as the AI named-entity model.
- Regular-expression recognizers for structured and Singapore-specific values.
- Validation and normalization rules to reject weak or incorrect detections.
- A Flask API and browser interface for analysis and anonymization.

## Supported entities

- `EMAIL_ADDRESS`
- `EMAIL_DATE`
- `DATE_TIME`
- `PERSON`
- `BANK_ACCOUNT_NUMBER`
- `BANKRUPTCY_NUMBER`
- `SG_VEHICLE_NUMBER`
- `SG_NRIC_FIN`
- `PHONE_NUMBER`
- `PASSPORT_NUMBER`
- `URL`
- `LOCATION`
- `JOB_TITLE`
- `ORGANIZATION`
- `CREDITOR_NAME`
- `BANKRUPT_NAME`
- `LAW_FIRM`
- `GOVERNMENT_AGENCY`

The recognizers include protection for PDF-extracted email addresses containing spaces, addresses split across lines, Singapore telephone numbers, NRIC/FIN values, vehicle numbers, and bankruptcy formats such as `HC/B/668/2024`, `B/668/2024`, and `HC 1394/2023`.

## Anonymization policy

General entities are replaced with readable tags:

```text
John Tan                 -> <PERSON>
john@example.com         -> <EMAIL_ADDRESS>
RSM Corporate Advisory  -> <ORGANIZATION>
```

Fixed-format private identifiers are masked. Only the first two and last two characters remain visible:

```text
SMD4125Y       -> SM****5Y
S1234567D      -> S1*****7D
1234567890     -> 12******90
HC/B/668/2024  -> HC*********24
```

Masked entity types:

- `BANK_ACCOUNT_NUMBER`
- `BANKRUPTCY_NUMBER`
- `SG_VEHICLE_NUMBER`
- `SG_NRIC_FIN`
- `PHONE_NUMBER`
- `PASSPORT_NUMBER`

All other supported entities are replaced. Hashing is not currently used.

The final safety pass also masks labelled identifiers such as policy numbers, UENs, authentication numbers, feedback numbers, company numbers, and reference numbers. Repeated detected values and safe person-name aliases are anonymized throughout the document.

## Project structure

```text
app.py
entity_collector.py
entity_rules.py
proces_pdfs.py
recognizers/
  business_recognizers.py
  gliner_recognizer.py
  singapore_recognizers.py
templates/
  index.html
static/
  styles.css
Dockerfile
docker-compose.yml
requirements.txt
ENTITY_GUIDE.md
```

## Processing flow

```text
PDF files
  -> pypdf extracts text
  -> proces_pdfs.py sends text to the local API
  -> Presidio runs pattern recognizers and GLiNER
  -> entity_rules.py validates and normalizes candidates
  -> entity_collector.py removes duplicates and overlaps
  -> the API replaces or masks detected private data
  -> two JSON output files are written
```

GLiNER processes long documents in overlapping chunks so entities near chunk boundaries are not lost. When detections overlap, the most specific, longest, highest-confidence entity is retained.

## Prerequisites

- Docker Desktop for running the API.
- Python 3.11 or 3.12 for running `proces_pdfs.py` on the host computer.
- At least several gigabytes of free disk space for the Docker image and downloaded language models.

The first Docker startup can take several minutes because spaCy and GLiNER model files are downloaded and loaded. The named Docker volume `presidio_models` keeps the model cache for later starts.

## Setup with Docker

Open PowerShell in the project folder and run:

```powershell
docker compose up -d --build
```

Check the container:

```powershell
docker compose ps
```

Wait until the status is `healthy`. The service is then available at:

- Browser interface: <http://localhost:5001/>
- Health check: <http://localhost:5001/health>
- Analyze API: <http://localhost:5001/analyze>
- Anonymize API: <http://localhost:5001/anonymize>
- Entity list: <http://localhost:5001/entity-types>

Docker publishes host port `5001` to application port `3000` inside the container. The PDF processor connects to Docker through `http://localhost:5001/anonymize`.

## Python environment for PDF processing

The Docker container runs the API, but `proces_pdfs.py` runs on the host. Create a virtual environment once:

```powershell
py -3.12 -m venv .venv312
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv312\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For later sessions, only activate the existing environment:

```powershell
.\.venv312\Scripts\Activate.ps1
```

## Process PDFs

1. Place the source files inside the `pdfs` folder.
2. Make sure the Docker container is healthy.
3. Run:

```powershell
python proces_pdfs.py
```

The script creates exactly one main result object per PDF in both files:

- `pdf_extracted_entities.json` contains grouped, normalized entity values.
- `pdf_anonymized_text.json` contains the complete readable anonymized text.

Seven PDF input files therefore produce seven main JSON objects in each output file.

## Browser interface

Open <http://localhost:5001/>. You can:

- Paste plain text and send it to the anonymization API.
- Paste the contents of `pdf_anonymized_text.json`.
- Switch between PDF results using document tabs.
- Read the complete anonymized text.
- See replaced values highlighted in blue and masked values highlighted in yellow.
- Copy the selected anonymized document.

## API examples

Analyze text:

```powershell
$body = @{
    text = "Email john@example.com. Vehicle SMD4125Y. Case HC/B/668/2024."
    language = "en"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:5001/analyze" `
    -ContentType "application/json" `
    -Body $body
```

Anonymize text:

```powershell
$body = @{
    text = "Dear John Tan, call +65 9123 4567. Vehicle SMD4125Y."
    language = "en"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:5001/anonymize" `
    -ContentType "application/json" `
    -Body $body
```

Both endpoints also accept an optional `entities` array containing only the entity types that should be processed.

## Add a new entity

1. Add the recognizer or pattern in `recognizers/business_recognizers.py` or `recognizers/singapore_recognizers.py`.
2. Add its validator, normalizer, and confidence threshold to `entity_rules.py`.
3. Add the entity name to `TARGET_ENTITIES` in `proces_pdfs.py`.
4. Decide whether the entity belongs in `MASK_ENTITY_TYPES` in `app.py`. Otherwise, it will be replaced.
5. Rebuild Docker and test with positive and negative examples.

## Useful commands

Rebuild after code or rule changes:

```powershell
docker compose up -d --build
```

View service logs:

```powershell
docker compose logs -f
```

Stop the service:

```powershell
docker compose down
```

Check installed Python dependencies:

```powershell
python -m pip check
```

## Files excluded from Git

The virtual environments, source PDFs, generated JSON results, caches, local environment files, and editor settings are excluded through `.gitignore`. Do not commit documents containing real private information.

## Important limitation

The current rules were verified against the seven supplied PDFs. Text-based PDFs are supported directly. Scanned image PDFs require OCR before this pipeline can analyze them. New layouts or identifier formats should be added as test examples and handled with new recognizer and validation rules.
