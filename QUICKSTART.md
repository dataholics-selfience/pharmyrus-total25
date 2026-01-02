# ⚡ Pharmyrus v31.0 - Quick Start

## 3 Passos para Deploy

### 1️⃣ Extrair Projeto (10 segundos)

```bash
tar -xzf pharmyrus-v31-complete.tar.gz
cd pharmyrus-v31-complete
```

### 2️⃣ Git & GitHub (1 minuto)

```bash
# Init Git
git init
git add .
git commit -m "Pharmyrus v31.0 - Production ready"

# Criar repo no GitHub
# Vá em: https://github.com/new
# Nome: pharmyrus-v31
# Depois:
git remote add origin https://github.com/SEU_USERNAME/pharmyrus-v31.git
git branch -M main
git push -u origin main
```

### 3️⃣ Deploy Railway (2 minutos)

**Opção A - Dashboard:**
1. Acesse https://railway.app/dashboard
2. Click "New Project"
3. "Deploy from GitHub repo"
4. Selecione `pharmyrus-v31`
5. Aguarde deploy (~2 min)

**Opção B - CLI:**
```bash
railway login
railway init
railway up
```

---

## ✅ Testar

```bash
# Health check
curl https://seu-app.railway.app/health

# Busca de patentes (estrutura unificada)
curl "https://seu-app.railway.app/api/v1/search?molecule_name=aspirin"

# Estatísticas
curl https://seu-app.railway.app/api/v1/stats
```

---

## 📊 Output Esperado

### Health Check
```json
{
  "status": "healthy",
  "version": "31.0",
  "features": [
    "WO-Centric Patent Search",
    "P&D Intelligence",
    "Patent Consolidation"
  ]
}
```

### Patent Search
```json
{
  "metadata": {...},
  "executive_summary": {...},
  "patent_search": {
    "consolidated_patents": [
      {
        "wo_number": "WO...",
        "national_patents": {
          "BR": [...],
          "US": [...]
        }
      }
    ]
  },
  "research_and_development": {...}
}
```

---

## 🎯 Endpoints Principais

| Endpoint | Descrição |
|----------|-----------|
| `GET /health` | Health check |
| `GET /api/v1/search` | Busca de patentes |
| `POST /api/v1/consolidate` | Consolidar resultado |
| `GET /api/v1/stats` | Estatísticas |
| `GET /docs` | Documentação interativa |

---

## 🐛 Troubleshooting

### Build falha
```bash
# Verificar Dockerfile
cat Dockerfile

# Verificar requirements.txt
cat requirements.txt
```

### Endpoint 404
```bash
# Verificar logs
railway logs

# Health check local
curl http://localhost:8000/health
```

### Import Error
```bash
# Verificar estrutura
ls -la

# Deve ter:
# - main.py
# - patent_consolidator.py
# - output_builder.py
```

---

## 📚 Mais Informações

- README completo: `README.md`
- Documentação da estrutura: Veja outputs de exemplo
- API docs: `https://seu-app.railway.app/docs`
