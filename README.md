# 🧬 Pharmyrus v31.0

**Patent & R&D Intelligence System with WO-Centric Unified Structure**

Sistema completo de inteligência de patentes farmacêuticas e P&D, com estrutura unificada WO-centric que consolida patentes internacionais e nacionais.

---

## 🎯 Características

### ✅ Patent Search (WO-Centric Unified)
- Consolidação automática de WOs e patentes nacionais
- Patent cliff calculado por família
- Suporte a múltiplas jurisdições (BR, US, EP, JP, CN, etc)
- Zero perda de dados

### ✅ P&D Intelligence
- Clinical Trials (ClinicalTrials.gov)
- FDA Data & Orange Book
- Market Intelligence
- Regulatory Data

### ✅ Data Sources
- **EPO OPS API**: Patentes europeias
- **Google Patents**: Busca global
- **INPI Brasil**: Enriquecimento de dados BR
- **ClinicalTrials.gov**: Trials clínicos
- **FDA**: Orange Book, exclusividades

---

## 🚀 Deploy Rápido

### Opção 1: Railway (Recomendado)

```bash
# 1. Extrair projeto
tar -xzf pharmyrus-v31-complete.tar.gz
cd pharmyrus-v31-complete

# 2. Git init
git init
git add .
git commit -m "Pharmyrus v31.0 - Initial deploy"

# 3. Criar repo no GitHub
gh repo create pharmyrus-v31 --private --source=. --push

# 4. Deploy no Railway
# Dashboard → New Project → Deploy from GitHub → pharmyrus-v31
```

### Opção 2: Railway CLI

```bash
railway login
railway init
railway up
```

### Opção 3: Docker Local

```bash
docker build -t pharmyrus:v31 .
docker run -p 8000:8000 pharmyrus:v31
```

---

## 📡 Endpoints

### Health Check
```bash
GET /health
```

### Patent Search (Estrutura Unificada)
```bash
GET /api/v1/search?molecule_name=aspirin&unified=true

# Retorna:
{
  "metadata": {...},
  "executive_summary": {...},
  "patent_search": {
    "consolidated_patents": [...]  # WO-centric
  },
  "research_and_development": {...}
}
```

### Patent Search (Estrutura Original)
```bash
GET /api/v1/search?molecule_name=aspirin&unified=false

# Retorna estrutura original para compatibilidade
```

### Consolidar Resultado
```bash
POST /api/v1/consolidate
Body: {
  "raw_data": {...},
  "enable_original_structure": true
}
```

### Estatísticas
```bash
GET /api/v1/stats
```

---

## 📊 Estrutura de Output

### Patent Search (WO-Centric)
```json
{
  "patent_search": {
    "consolidated_patents": [
      {
        "wo_number": "WO2015183882",
        "wo_data": {...},
        "national_patents": {
          "BR": [{...}],
          "US": [{...}]
        },
        "patent_cliff_impact": {
          "earliest_expiration": "2035-05-27",
          "years_until_expiration": 9.39
        },
        "statistics": {...}
      }
    ],
    "patent_cliff": {...},
    "statistics": {...}
  }
}
```

### P&D Intelligence
```json
{
  "research_and_development": {
    "clinical_trials": {...},
    "fda_data": {...},
    "orange_book": [...],
    "market_intelligence": {...}
  }
}
```

---

## 🧪 Teste Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar servidor
python main.py

# Testar
curl http://localhost:8000/health
curl "http://localhost:8000/api/v1/search?molecule_name=aspirin"
```

---

## 📁 Estrutura do Projeto

```
pharmyrus-v31-complete/
├── main.py                      # FastAPI app
├── patent_consolidator.py       # Consolidador WO-centric
├── output_builder.py            # Builder de output final
├── Dockerfile                   # Docker image
├── requirements.txt             # Dependências Python
├── railway.json                 # Config Railway
├── .gitignore                   # Git ignore
└── README.md                    # Este arquivo
```

---

## 🔧 Configuração

### Variáveis de Ambiente (Opcional)

```bash
PORT=8000                    # Porta do servidor (Railway define automaticamente)
LOG_LEVEL=INFO              # Nível de logging
```

---

## 📈 Próximas Features

- [ ] Integração com DrugBank
- [ ] Integração com PubMed
- [ ] Market Size Analysis
- [ ] Competitive Landscape
- [ ] Cache Redis
- [ ] Rate Limiting
- [ ] API Keys

---

## 📝 Versão

**v31.0** - WO-Centric Unified Structure with P&D Intelligence

---

## 📧 Suporte

Para questões e suporte, consulte a documentação completa em `/docs` após deploy.

---

## 📄 Licença

Proprietary - Todos os direitos reservados
