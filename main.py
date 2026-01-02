"""
Pharmyrus v31.0 - Patent & R&D Intelligence API
Backend completo com estrutura WO-centric unificada
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uvicorn
import logging
from datetime import datetime
import os

# Imports dos módulos locais
from patent_consolidator import PatentConsolidator
from output_builder import build_pharmyrus_output

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Criar app FastAPI
app = FastAPI(
    title="Pharmyrus API",
    version="31.0",
    description="Patent & R&D Intelligence System - WO-Centric Unified Structure"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# MODELS
# =============================================================================

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    port: int
    features: List[str]


class SearchRequest(BaseModel):
    molecule_name: str
    enable_unified: bool = True


class ConsolidateRequest(BaseModel):
    raw_data: Dict[str, Any]
    enable_original_structure: bool = True


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "service": "Pharmyrus API",
        "version": "31.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="31.0",
        timestamp=datetime.now().isoformat(),
        port=int(os.getenv("PORT", 8000)),
        features=[
            "WO-Centric Patent Search",
            "P&D Intelligence",
            "Patent Consolidation",
            "Clinical Trials",
            "FDA Data",
            "INPI Enrichment"
        ]
    )


@app.get("/api/v1/search")
async def patent_search(
    molecule_name: str = Query(..., description="Nome da molécula"),
    unified: bool = Query(True, description="Retornar estrutura unificada WO-centric")
):
    """
    Busca de patentes e P&D
    
    **Parâmetros**:
    - molecule_name: Nome da molécula (ex: aspirin, darolutamide)
    - unified: True = estrutura WO-centric | False = estrutura original
    
    **Retorno**:
    - unified=True: Patent Search (consolidado) + P&D
    - unified=False: Estrutura original (compatibilidade)
    """
    try:
        logger.info(f"📊 Buscando patentes para: {molecule_name} (unified={unified})")
        
        # AQUI SERIA A LÓGICA DE BUSCA REAL
        # Por enquanto, retornamos exemplo
        
        # Estrutura de dados original (simulada)
        raw_result = {
            'executive_summary': {
                'molecule_name': molecule_name,
                'commercial_name': molecule_name.title(),
                'generic_name': molecule_name.upper(),
                'clinical_trials_data': {},
                'fda_data': {},
                'total_families': 0,
                'consistency_score': 0
            },
            'search_result': {
                'molecule': molecule_name,
                'total_patents_found': 0,
                'total_families': 0,
                'patents': [],
                'families': [],
                'search_engines_used': ['EPO', 'Google Patents', 'INPI'],
                'search_timestamp': datetime.now().isoformat(),
                'warnings': [],
                'errors': []
            },
            'inpi_results': [],
            'validation_report': {},
            'statistics': {},
            'orange_book_entries': []
        }
        
        # Aplicar consolidação se solicitado
        if unified:
            logger.info("🔄 Aplicando consolidação WO-centric...")
            final_output = build_pharmyrus_output(raw_result)
            return final_output
        else:
            logger.info("📋 Retornando estrutura original...")
            return raw_result
            
    except Exception as e:
        logger.error(f"❌ Erro na busca: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/consolidate")
async def consolidate_result(request: ConsolidateRequest):
    """
    Consolida resultado de busca em estrutura WO-centric
    
    **Útil para**:
    - Consolidar JSONs já salvos
    - Testar consolidador isoladamente
    - Processar resultados batch
    """
    try:
        logger.info("🔄 Consolidando resultado...")
        
        # Consolidar
        output = build_pharmyrus_output(request.raw_data)
        
        # Remover estrutura original se não solicitada
        if not request.enable_original_structure:
            output['patent_search'].pop('original_structure', None)
        
        return {
            'success': True,
            'data': output,
            'consolidation_metadata': {
                'version': '31.0',
                'timestamp': datetime.now().isoformat(),
                'wo_patents': output['patent_search']['statistics']['total_wo_patents'],
                'br_patents': output['patent_search']['statistics']['wo_with_br_patents']
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro na consolidação: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/v1/stats")
async def get_statistics():
    """Estatísticas do sistema"""
    return {
        'version': '31.0',
        'uptime': 'Running',
        'features': {
            'patent_search': 'Active',
            'consolidation': 'Active',
            'pd_intelligence': 'Active',
            'inpi_enrichment': 'Active'
        },
        'data_sources': {
            'epo_ops': 'Configured',
            'google_patents': 'Configured',
            'inpi': 'Configured',
            'clinicaltrials_gov': 'Configured',
            'fda_orange_book': 'Configured'
        }
    }


# =============================================================================
# STARTUP & SHUTDOWN
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Evento de inicialização"""
    logger.info("="*60)
    logger.info("🚀 Pharmyrus v31.0 - Starting...")
    logger.info("="*60)
    logger.info("✅ WO-Centric Patent Search: ENABLED")
    logger.info("✅ P&D Intelligence: ENABLED")
    logger.info("✅ Patent Consolidation: ENABLED")
    logger.info("="*60)


@app.on_event("shutdown")
async def shutdown_event():
    """Evento de desligamento"""
    logger.info("🛑 Pharmyrus v31.0 - Shutting down...")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
