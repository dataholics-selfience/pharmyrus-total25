# Pharmyrus v29.1-COMPLETE

## Pharmaceutical Patent Search System

3-Layer patent discovery + Intelligent merge + R&D data

### Features

**Patent Discovery:**
- ✅ EPO OPS API (WO patents + BR family)
- ✅ Google Patents (Playwright crawler)
- ✅ INPI Brazil (Login + complete parse)
- ✅ Intelligent merge (EPO + INPI + Google)
- ✅ Complete metadata (all fields, documents, links)

**R&D Data:**
- ✅ PubChem (molecular data, synonyms, dev codes)
- 🔄 OpenFDA (placeholder)
- 🔄 FDA Orange Book (placeholder)
- 🔄 PubMed (placeholder)
- 🔄 ClinicalTrials.gov (placeholder)
- 🔄 DrugBank (placeholder)

### Deploy

**Railway:**
```bash
railway up
```

**Environment Variables:**
- `INPI_PASSWORD` (required for INPI login)
- `GROQ_API_KEY` (optional for Portuguese translation)

### API

**POST /search**
```json
{
  "nome_molecula": "Darolutamide",
  "nome_comercial": "Nubeqa",
  "paises_alvo": ["BR"],
  "incluir_wo": true
}
```

**Response:**
```json
{
  "metadata": {...},
  "patent_discovery": {
    "summary": {...},
    "wo_patents": [...],
    "patents_by_country": {"BR": [...]}
  },
  "research_and_development": {
    "molecular": {...},
    "clinical_trials": [],
    "regulatory": {},
    "literature": []
  }
}
```

### Version

v29.1-COMPLETE (2025-12-28)

**Changes from v29.0:**
- Complete INPI parser (all fields)
- Intelligent merge EPO+INPI+Google
- No duplicates
- Complete links (documents, images, PDFs)
- R&D data structure
- 6-month cache system ready
- Source attribution
