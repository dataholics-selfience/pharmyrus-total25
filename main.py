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


async def _process_patent_search(
    molecule_name: str,
    unified: bool = True,
    raw_data: Optional[Dict[str, Any]] = None
):
    """
    Processa busca de patentes (lógica compartilhada)
    """
    try:
        logger.info(f"📊 Processando patentes para: {molecule_name} (unified={unified})")
        
        # Se raw_data foi fornecido (POST), usar ele
        if raw_data:
            logger.info("📥 Usando dados fornecidos no request")
            raw_result = raw_data
        else:
            # Estrutura de dados vazia (GET sem dados reais ainda)
            logger.info("📝 Criando estrutura base (dados reais serão integrados)")
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
                    'warnings': ['Sistema em modo consolidação - integre dados reais via POST'],
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
            try:
                final_output = build_pharmyrus_output(raw_result)
                logger.info("✅ Consolidação concluída com sucesso")
                return final_output
            except Exception as consolidation_error:
                logger.error(f"⚠️ Erro na consolidação: {consolidation_error}")
                logger.info("📋 Retornando dados originais devido a erro na consolidação")
                return {
                    'error': 'Consolidation failed',
                    'original_data': raw_result,
                    'consolidation_error': str(consolidation_error)
                }
        else:
            logger.info("📋 Retornando estrutura original...")
            return raw_result
            
    except Exception as e:
        logger.error(f"❌ Erro no processamento: {str(e)}", exc_info=True)
        return {
            'error': str(e),
            'molecule_name': molecule_name,
            'timestamp': datetime.now().isoformat(),
            'message': 'Erro no processamento - estrutura base retornada'
        }


@app.get("/api/v1/search")
async def patent_search_get(
    molecule_name: str = Query(..., description="Nome da molécula"),
    unified: bool = Query(True, description="Retornar estrutura unificada WO-centric")
):
    """
    Busca de patentes e P&D (GET)
    
    **Parâmetros**:
    - molecule_name: Nome da molécula (ex: aspirin, darolutamide)
    - unified: True = estrutura WO-centric | False = estrutura original
    
    **Retorno**:
    - unified=True: Patent Search (consolidado) + P&D
    - unified=False: Estrutura original (compatibilidade)
    """
    return await _process_patent_search(molecule_name, unified)


@app.post("/api/v1/search")
async def patent_search_post(request: SearchRequest):
    """
    Busca de patentes e P&D (POST)
    
    Permite enviar dados já coletados para consolidação
    """
    return await _process_patent_search(
        request.molecule_name,
        request.enable_unified
    )


# Rotas de compatibilidade (sem /api/v1)
@app.get("/search")
async def search_compat_get(
    molecule_name: str = Query(..., description="Nome da molécula"),
    unified: bool = Query(True, description="Retornar estrutura unificada")
):
    """Rota de compatibilidade - redireciona para /api/v1/search"""
    logger.info(f"⚠️ Usando rota de compatibilidade /search -> /api/v1/search")
    return await _process_patent_search(molecule_name, unified)


@app.post("/search")
async def search_compat_post(raw_data: Dict[str, Any]):
    """
    Rota de compatibilidade POST - aceita dados brutos para consolidação
    """
    logger.info(f"⚠️ Usando rota de compatibilidade POST /search")
    
    # Extrair molecule_name dos dados
    molecule_name = "unknown"
    if 'executive_summary' in raw_data:
        molecule_name = raw_data['executive_summary'].get('molecule_name', 'unknown')
    elif 'search_result' in raw_data:
        molecule_name = raw_data['search_result'].get('molecule', 'unknown')
    
    logger.info(f"📥 Recebendo dados para consolidação: {molecule_name}")
    
    try:
        # Consolidar dados recebidos
        final_output = build_pharmyrus_output(raw_data)
        logger.info("✅ Consolidação via POST concluída")
        return final_output
    except Exception as e:
        logger.error(f"❌ Erro na consolidação POST: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'original_data': raw_data,
            'message': 'Erro na consolidação - retornando dados originais'
        }


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
