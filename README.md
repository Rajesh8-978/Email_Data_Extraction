# Email Data Extraction and Anonymization

This project detects and anonymizes private/business data from text and PDF files. It is built for Singapore-focused email/PDF documents, with extra rules for bankruptcy cases, Singapore phone numbers, NRIC/FIN, vehicle numbers, passport-style values, bank accounts, names, organizations, locations, dates, URLs, and government/legal entities.

The backend is an API service. A separate local browser UI is included only for review/testing.

## What This Project Does

The project has two main outputs:

- Analyzer output: returns only extracted entities in JSON format.
- Anonymizer output: returns safe anonymized text, where private values are replaced or masked.

Example:

```text
Dear John Tan, call +65 9123 4567. Vehicle SMD4125Y. Case HC/B/668/2024.
```

Analyzer finds:

```text
PERSON: John Tan
PHONE_NUMBER: +6591234567
SG_VEHICLE_NUMBER: SMD4125Y
BANKRUPTCY_NUMBER: HC/B/668/2024
```

Anonymizer returns:

```text
Dear <PERSON>, call +6*********67. Vehicle SM****5Y. Case HC*********24.
```

## Main Technologies

- Flask: creates the HTTP API endpoints.
- Microsoft Presidio Analyzer: framework that runs recognizers and returns detected entities.
- GLiNER: AI named-entity model used for names, organizations, locations, job titles, and other natural-language entities.
- spaCy: NLP runtime used by GLiNER/Presidio dependencies.
- pypdf: extracts selectable text from PDF files.
- requests: sends API requests from scripts and the local UI proxy.
- Docker: packages and runs the backend API consistently on different machines.

Presidio is the framework, not the AI model. GLiNER is the AI model used for flexible named-entity detection. Regex recognizers are used for fixed-format entities such as bankruptcy numbers, phone numbers, NRIC/FIN, vehicle numbers, and bank account-like values.

## Supported Entities

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

Singapore/business recognizers include formats such as:

- `HC/B/668/2024`
- `B/668/2024`
- `HC/1394/2023`
- Singapore phone numbers
- Singapore vehicle numbers
- Singapore NRIC/FIN-style values
- bankruptcy/bankrupt/creditor names from legal context
- government agencies and legal/business organizations

## Anonymization Policy

General entities are replaced with readable tags:

```text
John Tan                -> <PERSON>
john@example.com        -> <EMAIL_ADDRESS>
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

## Project Structure

```text
app.py                         Backend Flask API
entity_collector.py            Deduplication and overlap handling
entity_rules.py                Validation, confidence, normalization rules
proces_pdfs.py                 Batch PDF processor for the local pdfs folder
result_formatter.py            Shared output formatting for PDF results
recognizers/
  business_recognizers.py      Business/legal recognizers
  gliner_recognizer.py         GLiNER model recognizer
  singapore_recognizers.py     Singapore-specific pattern recognizers
ui/
  frontend_ui.py               Separate local UI proxy/server
  index.html                   UI page
  app.js                       UI API integration and highlighting
  styles.css                   UI styling
Dockerfile
docker-compose.yml
requirements.txt
ENTITY_GUIDE.md
```

## Backend API Endpoints

The backend supports both text input and PDF upload.

| Input type | Analyzer endpoint | Anonymizer endpoint |
|---|---|---|
| Text JSON | `POST /api/extracted-entities` | `POST /api/anonymized-text` |
| PDF upload | `POST /api/pdf/extracted-entities` | `POST /api/pdf/anonymized-text` |

Other endpoints:

- `GET /health`
- `GET /entity-types`
- `POST /analyze`
- `POST /anonymize`

Opening an API URL in a browser sends `GET`. Real processing must use `POST`.

## Run Locally With Docker

Open PowerShell in the project folder:

```powershell
docker compose up -d --build
```

Check the service:

```powershell
docker compose ps
```

Local backend URL:

```text
http://localhost:5001
```

Health check:

```powershell
curl.exe "http://localhost:5001/health"
```

Docker maps:

```text
Computer port 5001 -> container port 3000
```

So other systems call port `5001` locally, while Azure Container Apps should use target port `3000`.

## Run The Local Review UI

The UI is separate from the backend API. It can call either:

- local Docker API: `http://localhost:5001`
- Azure deployed API: `https://<your-app>.azurecontainerapps.io`

Start the UI:

```powershell
.\.venv312\Scripts\python.exe ui\frontend_ui.py
```

Open:

```text
http://127.0.0.1:8080
```

The UI lets you:

- choose text or PDF input
- run analyzer
- run anonymizer
- run both
- view analyzer entity cards
- view anonymized full text with highlights
- copy JSON output

The UI does not replace the API. It is only a friendly review screen.

## Python Setup For Local Scripts

The Docker container runs the API. The script `proces_pdfs.py` runs on your computer and sends PDF text to the API.

Create the Python environment once:

```powershell
py -3.12 -m venv .venv312
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv312\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For later sessions:

```powershell
.\.venv312\Scripts\Activate.ps1
```

## Process PDFs From The Local Folder

Put PDF files inside:

```text
pdfs/
```

Run:

```powershell
python proces_pdfs.py
```

Outputs:

- `pdf_extracted_entities.json`
- `pdf_anonymized_text.json`

If 7 PDFs are in the folder, the output file contains 7 main result objects.

## Text API Examples

Create request body:

```powershell
$body = @{
    text = "Dear John Tan, call +65 9123 4567. Vehicle SMD4125Y. Case HC/B/668/2024."
    language = "en"
} | ConvertTo-Json
```

Analyzer:

```powershell
Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:5001/api/extracted-entities" `
    -ContentType "application/json" `
    -Body $body
```

Anonymizer:

```powershell
Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:5001/api/anonymized-text" `
    -ContentType "application/json" `
    -Body $body
```

## PDF API Examples

Use forward slashes in Windows paths when calling with `curl.exe`.

Analyzer:

```powershell
curl.exe --max-time 300 -X POST "http://localhost:5001/api/pdf/extracted-entities" -F "file=@C:/Users/Admin/OneDrive - Zest Labs/Desktop/Rajesh_Documents/POD -2 (1).pdf" -F "language=en" -F "email_message_id=1"
```

Anonymizer:

```powershell
curl.exe --max-time 300 -X POST "http://localhost:5001/api/pdf/anonymized-text" -F "file=@C:/Users/Admin/OneDrive - Zest Labs/Desktop/Rajesh_Documents/POD -2 (1).pdf" -F "language=en" -F "email_message_id=1"
```

For Azure, replace `http://localhost:5001` with the Azure URL:

```text
https://<your-app>.azurecontainerapps.io
```

## Azure Deployment Notes

Recommended flow:

1. Build Docker image locally.
2. Push image to Azure Container Registry.
3. Create Azure Container Apps environment.
4. Create Azure Container App with external ingress.
5. Use target port `3000`.

Example deployed API shape:

```text
https://presidio-test-api.<region>.azurecontainerapps.io/api/pdf/extracted-entities
https://presidio-test-api.<region>.azurecontainerapps.io/api/pdf/anonymized-text
```

For testing, `min-replicas 1` keeps the API warm. For production, add authentication/API key protection before exposing private document processing publicly.

## Host The Review UI On Vercel

Vercel should host only the lightweight browser UI. The analyzer/anonymizer backend should continue running on Azure Container Apps because it uses Docker, Presidio, GLiNER, spaCy, and large model files.

Production flow:

```text
User browser
  -> Vercel UI
  -> Vercel /api/proxy serverless function
  -> Azure Container Apps backend API
  -> JSON result back to browser
```

Files used by Vercel:

```text
vercel.json
api/proxy.js
ui/index.html
ui/app.js
ui/styles.css
```

Deploy from GitHub:

1. Push this repository to GitHub.
2. Open Vercel.
3. Choose `Add New Project`.
4. Import this GitHub repository.
5. Keep the root directory as the project root.
6. Add this environment variable:

```text
AZURE_API_BASE=https://<your-azure-container-app-url>
```

Example:

```text
AZURE_API_BASE=https://presidio-test-api.bravesand-5605c72b.southeastasia.azurecontainerapps.io
```

7. Deploy.

After deployment, the public Vercel URL can be opened by anyone:

```text
https://<your-vercel-project>.vercel.app
```

The API base URL is hidden from the UI. Users only see the upload/text interface and the analyzer/anonymizer results.

Important: if the Azure backend is stopped or deleted, the Vercel UI will open but analysis/anonymization will fail because the actual processing API is not running.

## Docker Image Export And Import

Save image to a tar file:

```powershell
docker save -o C:\presidio-singapore.tar presidio-singapore-presidio-singapore:latest
```

Load image on another machine:

```powershell
docker load -i C:\presidio-singapore.tar
```

The tar file can be large. Use an NTFS or exFAT USB drive, not FAT32.

## Add A New Entity

1. Add a recognizer in `recognizers/business_recognizers.py` or `recognizers/singapore_recognizers.py`.
2. Add validation and normalization in `entity_rules.py`.
3. Add the entity to `TARGET_ENTITIES` in `result_formatter.py`.
4. Decide whether it should be masked in `MASK_ENTITY_TYPES` in `app.py`.
5. Rebuild Docker and test with positive and negative examples.

## Useful Commands

Rebuild backend:

```powershell
docker compose up -d --build
```

View logs:

```powershell
docker compose logs -f
```

Stop backend:

```powershell
docker compose down
```

Check Python dependencies:

```powershell
python -m pip check
```

## Important Limitations

- Text-based PDFs are supported directly.
- Scanned/image PDFs need OCR before this project can read them.
- New document layouts may need additional recognizers or validation rules.
- The Azure test API currently has no built-in API key check.
- Do not commit real private PDFs or generated output containing private information.
