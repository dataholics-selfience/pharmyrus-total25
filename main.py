"""
Pharmyrus v28.9 - ZERO PLAYWRIGHT (httpx only!)
Layer 1: EPO OPS (HTTP direto)
Layer 2: Google Patents (httpx + regex - NO PLAYWRIGHT!)  
Layer 3: INPI Brazilian (httpx direto - 3X RUNS!)

🔥 NEW v28.9 - ZERO PLAYWRIGHT:
✅ google_patents_crawler.py REESCRITO - apenas httpx
✅ inpi_crawler.py - apenas httpx
✅ SEM Playwright em NENHUM arquivo
✅ Build ultra-rápido (~1 min)
✅ Container pequeno (~200MB)
✅ INPI 3x runs mantidos
✅ Tradução PT via Groq mantida
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import httpx
import base64
import asyncio
import re
import json
from datetime import datetime
import logging
import os  # GROQ_API_KEY

# Import Google Crawler Layer 2
from google_patents_crawler import google_crawler

# Import INPI Crawler Layer 3
from inpi_crawler import inpi_crawler

# Logging PERSISTENTE (arquivo + console)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s:%(name)s:%(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/pharmyrus.log', mode='a')  # PERSISTE logs mesmo após crash
    ]
)
logger = logging.getLogger("pharmyrus")
logger.info("=" * 80)
logger.info(f"📝 Pharmyrus v28.9 NO-PLAYWRIGHT - Logs persistentes em /tmp/pharmyrus.log")
logger.info("=" * 80)

# EPO Credentials (MESMAS QUE FUNCIONAM)
EPO_KEY = "G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X"
EPO_SECRET = "zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAPMFLuVUfiEuAqpdbz"


def format_date(date_str: str) -> str:
    """Formata data de YYYYMMDD para YYYY-MM-DD"""
    if not date_str or len(date_str) != 8:
        return date_str
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except:
        return date_str

# Country codes supported
COUNTRY_CODES = {
    "BR": "Brazil", "US": "United States", "EP": "European Patent",
    "CN": "China", "JP": "Japan", "KR": "South Korea", "IN": "India",
    "MX": "Mexico", "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
    "PE": "Peru", "CA": "Canada", "AU": "Australia", "RU": "Russia", "ZA": "South Africa"
}

app = FastAPI(
    title="Pharmyrus v28.0",
    description="Three-Layer Patent Search: EPO OPS (FULL) + Google Patents (AGGRESSIVE) + INPI Brazilian (DIRECT SEARCH)",
    version="28.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    nome_molecula: str
    nome_comercial: Optional[str] = None
    paises_alvo: List[str] = Field(default=["BR"])
    incluir_wo: bool = True
    max_results: int = 100


# ============= INPI HELPER FUNCTION (FORCED EXECUTION) =============

async def execute_inpi_search(
    run_number: int,
    run_label: str,
    molecule: str,
    brand: str,
    dev_codes: List[str],
    known_wos: List[str],
    groq_api_key: str
) -> List[Dict]:
    """
    FORÇA execução do INPI com logs massivos
    
    Args:
        run_number: Número da execução (1, 2, 3)
        run_label: Label da execução (ex: "After EPO")
        molecule: Nome da molécula
        brand: Nome comercial
        dev_codes: Códigos de desenvolvimento
        known_wos: WOs conhecidos para mapear BRs
        groq_api_key: Chave API do Groq
    
    Returns:
        Lista de patentes BR encontradas
    """
    logger.info("=" * 100)
    logger.info(f"🇧🇷 INPI RUN #{run_number}: {run_label}")
    logger.info("=" * 100)
    logger.info(f"   📊 Input: molecule={molecule}, brand={brand}")
    logger.info(f"   📊 Dev codes: {len(dev_codes)} codes = {dev_codes[:5]}...")
    logger.info(f"   📊 Known WOs for mapping: {len(known_wos)} WOs (using top 20)")
    logger.info(f"   📊 Groq API key present: {bool(groq_api_key)}")
    logger.info("")
    
    inpi_results = []
    
    try:
        logger.info(f"   🔄 FORCING INPI execution...")
        logger.info(f"   🔄 Calling inpi_crawler.search_inpi...")
        
        # FORÇA execução do INPI
        inpi_results = await inpi_crawler.search_inpi(
            molecule=molecule,
            brand=brand,
            dev_codes=dev_codes,
            known_wos=sorted(list(known_wos))[:20],  # Top 20 WOs
            groq_api_key=groq_api_key
        )
        
        logger.info(f"   ✅ INPI RUN #{run_number} completed successfully!")
        logger.info(f"   ✅ Found {len(inpi_results)} BR patents")
        
        if inpi_results:
            logger.info(f"   📋 Sample results:")
            for i, patent in enumerate(inpi_results[:3]):
                logger.info(f"      BR #{i+1}: {patent.get('patent_number', 'N/A')}")
        else:
            logger.info(f"   ⚠️  No BR patents found in this run")
        
    except ImportError as e:
        logger.error(f"   ❌ INPI RUN #{run_number} FAILED - Import Error!")
        logger.error(f"   ❌ Error: {e}")
        logger.error(f"   ❌ Check if inpi_crawler module is available")
        
    except AttributeError as e:
        logger.error(f"   ❌ INPI RUN #{run_number} FAILED - Attribute Error!")
        logger.error(f"   ❌ Error: {e}")
        logger.error(f"   ❌ Check if inpi_crawler.search_inpi exists")
        
    except Exception as e:
        logger.error(f"   ❌ INPI RUN #{run_number} FAILED - Unexpected Error!")
        logger.error(f"   ❌ Error type: {type(e).__name__}")
        logger.error(f"   ❌ Error message: {str(e)}")
        import traceback
        logger.error(f"   ❌ Traceback:\n{traceback.format_exc()}")
    
    logger.info("=" * 100)
    logger.info("")
    
    return inpi_results


# ============= LAYER 1: EPO (CÓDIGO COMPLETO v26) =============

async def get_epo_token(client: httpx.AsyncClient) -> str:
    """Obtém token de acesso EPO"""
    creds = f"{EPO_KEY}:{EPO_SECRET}"
    b64_creds = base64.b64encode(creds.encode()).decode()
    
    response = await client.post(
        "https://ops.epo.org/3.2/auth/accesstoken",
        headers={
            "Authorization": f"Basic {b64_creds}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={"grant_type": "client_credentials"},
        timeout=30.0
    )
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="EPO authentication failed")
    
    return response.json()["access_token"]


async def get_patent_abstract(client: httpx.AsyncClient, token: str, patent_number: str) -> Optional[str]:
    """Busca abstract de uma patente via EPO API"""
    try:
        # Tentar formato docdb (ex: BR112017021636)
        response = await client.get(
            f"https://ops.epo.org/3.2/rest-services/published-data/publication/docdb/{patent_number}/abstract",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15.0
        )
        
        if response.status_code == 200:
            data = response.json()
            abstracts = data.get("ops:world-patent-data", {}).get("exchange-documents", {}).get("exchange-document", {}).get("abstract", [])
            
            if isinstance(abstracts, dict):
                abstracts = [abstracts]
            
            # Procurar abstract em inglês primeiro
            for abs_item in abstracts:
                if abs_item.get("@lang") == "en":
                    p_elem = abs_item.get("p", {})
                    if isinstance(p_elem, dict):
                        return p_elem.get("$")
                    elif isinstance(p_elem, str):
                        return p_elem
            
            # Se não tem inglês, pegar qualquer idioma
            if abstracts and len(abstracts) > 0:
                p_elem = abstracts[0].get("p", {})
                if isinstance(p_elem, dict):
                    return p_elem.get("$")
                elif isinstance(p_elem, str):
                    return p_elem
        
        return None
    except Exception as e:
        logger.debug(f"Error fetching abstract for {patent_number}: {e}")
        return None


async def get_pubchem_data(client: httpx.AsyncClient, molecule: str) -> Dict:
    """Obtém dados do PubChem (dev codes, CAS, sinônimos)"""
    try:
        response = await client.get(
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{molecule}/synonyms/JSON",
            timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            synonyms = data.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])
            
            dev_codes = []
            cas = None
            
            for syn in synonyms[:100]:
                if re.match(r'^[A-Z]{2,5}-?\d{3,7}[A-Z]?$', syn, re.I) and len(syn) < 20:
                    if syn not in dev_codes:
                        dev_codes.append(syn)
                if re.match(r'^\d{2,7}-\d{2}-\d$', syn) and not cas:
                    cas = syn
            
            return {
                "dev_codes": dev_codes[:10],
                "cas": cas,
                "synonyms": synonyms[:20]
            }
    except Exception as e:
        logger.warning(f"PubChem error: {e}")
    
    return {"dev_codes": [], "cas": None, "synonyms": []}


def build_search_queries(molecule: str, brand: str, dev_codes: List[str], cas: str = None) -> List[str]:
    """Constrói queries EXPANDIDAS para busca EPO - VERSÃO COMPLETA v26"""
    queries = []
    
    # 1. Nome da molécula (múltiplas variações)
    queries.append(f'txt="{molecule}"')
    queries.append(f'ti="{molecule}"')
    queries.append(f'ab="{molecule}"')
    
    # 2. Nome comercial
    if brand:
        queries.append(f'txt="{brand}"')
        queries.append(f'ti="{brand}"')
    
    # 3. Dev codes (expandido para 5)
    for code in dev_codes[:5]:
        queries.append(f'txt="{code}"')
        code_no_hyphen = code.replace("-", "")
        if code_no_hyphen != code:
            queries.append(f'txt="{code_no_hyphen}"')
    
    # 4. CAS number
    if cas:
        queries.append(f'txt="{cas}"')
    
    # 5. Applicants conhecidos + keywords terapêuticas (CRÍTICO!)
    applicants = ["Orion", "Bayer", "AstraZeneca", "Pfizer", "Novartis", "Roche", "Merck", "Johnson", "Bristol-Myers"]
    keywords = ["androgen", "receptor", "crystalline", "pharmaceutical", "process", "formulation", 
                "prostate", "cancer", "inhibitor", "modulating", "antagonist"]
    
    for app in applicants[:5]:
        for kw in keywords[:4]:
            queries.append(f'pa="{app}" and ti="{kw}"')
    
    # 6. Queries específicas para classes terapêuticas
    queries.append('txt="nonsteroidal antiandrogen"')
    queries.append('txt="androgen receptor antagonist"')
    queries.append('txt="nmCRPC"')
    queries.append('txt="non-metastatic" and txt="castration-resistant"')
    queries.append('ti="androgen receptor" and ti="inhibitor"')
    
    return queries


async def search_epo(client: httpx.AsyncClient, token: str, query: str) -> List[str]:
    """Executa busca no EPO e retorna lista de WOs"""
    wos = set()
    
    try:
        response = await client.get(
            "https://ops.epo.org/3.2/rest-services/published-data/search",
            params={"q": query, "Range": "1-100"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            pub_refs = data.get("ops:world-patent-data", {}).get("ops:biblio-search", {}).get("ops:search-result", {}).get("ops:publication-reference", [])
            
            if not isinstance(pub_refs, list):
                pub_refs = [pub_refs] if pub_refs else []
            
            for ref in pub_refs:
                doc_id = ref.get("document-id", {})
                if isinstance(doc_id, list):
                    doc_id = doc_id[0] if doc_id else {}
                
                if doc_id.get("@document-id-type") == "docdb":
                    country = doc_id.get("country", {}).get("$", "")
                    number = doc_id.get("doc-number", {}).get("$", "")
                    if country == "WO" and number:
                        wos.add(f"WO{number}")
        
    except Exception as e:
        logger.debug(f"Search error for query '{query}': {e}")
    
    return list(wos)


async def search_citations(client: httpx.AsyncClient, token: str, wo_number: str) -> List[str]:
    """Busca patentes que citam um WO específico - CRÍTICO!"""
    wos = set()
    
    try:
        query = f'ct="{wo_number}"'
        response = await client.get(
            "https://ops.epo.org/3.2/rest-services/published-data/search",
            params={"q": query, "Range": "1-100"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            pub_refs = data.get("ops:world-patent-data", {}).get("ops:biblio-search", {}).get("ops:search-result", {}).get("ops:publication-reference", [])
            
            if not isinstance(pub_refs, list):
                pub_refs = [pub_refs] if pub_refs else []
            
            for ref in pub_refs:
                doc_id = ref.get("document-id", {})
                if isinstance(doc_id, list):
                    doc_id = doc_id[0] if doc_id else {}
                
                if doc_id.get("@document-id-type") == "docdb":
                    country = doc_id.get("country", {}).get("$", "")
                    number = doc_id.get("doc-number", {}).get("$", "")
                    if country == "WO" and number:
                        wos.add(f"WO{number}")
    
    except Exception as e:
        logger.debug(f"Citation search error for {wo_number}: {e}")
    
    return list(wos)


async def search_related_wos(client: httpx.AsyncClient, token: str, found_wos: List[str]) -> List[str]:
    """Busca WOs relacionados via prioridades - CRÍTICO!"""
    additional_wos = set()
    
    for wo in found_wos[:10]:
        try:
            response = await client.get(
                f"https://ops.epo.org/3.2/rest-services/family/publication/docdb/{wo}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                family = data.get("ops:world-patent-data", {}).get("ops:patent-family", {})
                
                members = family.get("ops:family-member", [])
                if not isinstance(members, list):
                    members = [members]
                
                for m in members:
                    prio = m.get("priority-claim", [])
                    if not isinstance(prio, list):
                        prio = [prio] if prio else []
                    
                    for p in prio:
                        doc_id = p.get("document-id", {})
                        if isinstance(doc_id, list):
                            doc_id = doc_id[0] if doc_id else {}
                        country = doc_id.get("country", {}).get("$", "")
                        number = doc_id.get("doc-number", {}).get("$", "")
                        if country == "WO" and number:
                            wo_num = f"WO{number}"
                            if wo_num not in found_wos:
                                additional_wos.add(wo_num)
            
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.debug(f"Error searching related WOs for {wo}: {e}")
    
    return list(additional_wos)


async def get_family_patents(client: httpx.AsyncClient, token: str, wo_number: str, 
                            target_countries: List[str]) -> Dict[str, List[Dict]]:
    """Extrai patentes da família de um WO para países alvo"""
    patents = {cc: [] for cc in target_countries}
    
    try:
        response = await client.get(
            f"https://ops.epo.org/3.2/rest-services/family/publication/docdb/{wo_number}/biblio",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30.0
        )
        
        if response.status_code == 413:
            response = await client.get(
                f"https://ops.epo.org/3.2/rest-services/family/publication/docdb/{wo_number}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=30.0
            )
        
        if response.status_code != 200:
            return patents
        
        data = response.json()
        family = data.get("ops:world-patent-data", {}).get("ops:patent-family", {})
        
        members = family.get("ops:family-member", [])
        if not isinstance(members, list):
            members = [members]
        
        for member in members:
            pub_ref = member.get("publication-reference", {})
            doc_ids = pub_ref.get("document-id", [])
            
            if isinstance(doc_ids, dict):
                doc_ids = [doc_ids]
            
            # Processar TODOS os doc_ids do tipo docdb (pode ter múltiplos BRs)
            docdb_entries = [d for d in doc_ids if d.get("@document-id-type") == "docdb"]
            
            for doc_id in docdb_entries:
                country = doc_id.get("country", {}).get("$", "")
                number = doc_id.get("doc-number", {}).get("$", "")
                kind = doc_id.get("kind", {}).get("$", "")
                
                if country in target_countries and number:
                    patent_num = f"{country}{number}"
                    
                    bib = member.get("exchange-document", {}).get("bibliographic-data", {}) if "exchange-document" in member else {}
                    
                    # TITLE (EN + Original)
                    titles = bib.get("invention-title", [])
                    if isinstance(titles, dict):
                        titles = [titles]
                    title_en = None
                    title_orig = None
                    for t in titles:
                        if t.get("@lang") == "en":
                            title_en = t.get("$")
                        elif not title_orig:  # Pegar primeiro não-EN como original
                            title_orig = t.get("$")
                    
                    # Se não tem EN mas tem original, usar original
                    if not title_en and title_orig:
                        title_en = title_orig
                    
                    # ABSTRACT - Múltiplos fallbacks
                    abstract_text = None
                    abstracts = bib.get("abstract", {})
                    if abstracts:
                        if isinstance(abstracts, list):
                            # Lista de abstracts em múltiplos idiomas
                            for abs_item in abstracts:
                                if isinstance(abs_item, dict):
                                    # Preferir EN
                                    if abs_item.get("@lang") == "en":
                                        p_elem = abs_item.get("p", {})
                                        if isinstance(p_elem, dict):
                                            abstract_text = p_elem.get("$")
                                        elif isinstance(p_elem, str):
                                            abstract_text = p_elem
                                        elif isinstance(p_elem, list):
                                            # Concatenar múltiplos parágrafos
                                            paras = []
                                            for para in p_elem:
                                                if isinstance(para, dict):
                                                    paras.append(para.get("$", ""))
                                                elif isinstance(para, str):
                                                    paras.append(para)
                                            abstract_text = " ".join(paras)
                                        break
                            # Se não achou EN, pegar primeiro disponível
                            if not abstract_text and abstracts:
                                first_abs = abstracts[0]
                                if isinstance(first_abs, dict):
                                    p_elem = first_abs.get("p", {})
                                    if isinstance(p_elem, dict):
                                        abstract_text = p_elem.get("$")
                                    elif isinstance(p_elem, str):
                                        abstract_text = p_elem
                                    elif isinstance(p_elem, list):
                                        paras = []
                                        for para in p_elem:
                                            if isinstance(para, dict):
                                                paras.append(para.get("$", ""))
                                            elif isinstance(para, str):
                                                paras.append(para)
                                        abstract_text = " ".join(paras)
                        elif isinstance(abstracts, dict):
                            # Single abstract
                            p_elem = abstracts.get("p", {})
                            if isinstance(p_elem, dict):
                                abstract_text = p_elem.get("$")
                            elif isinstance(p_elem, str):
                                abstract_text = p_elem
                            elif isinstance(p_elem, list):
                                # Múltiplos parágrafos
                                paras = []
                                for para in p_elem:
                                    if isinstance(para, dict):
                                        paras.append(para.get("$", ""))
                                    elif isinstance(para, str):
                                        paras.append(para)
                                abstract_text = " ".join(paras)
                    
                    # APPLICANTS
                    applicants = []
                    parties = bib.get("parties", {}).get("applicants", {}).get("applicant", [])
                    if isinstance(parties, dict):
                        parties = [parties]
                    for p in parties[:10]:  # Aumentar limite para 10
                        name = p.get("applicant-name", {})
                        if isinstance(name, dict):
                            name_text = name.get("name", {}).get("$")
                            if name_text:
                                applicants.append(name_text)
                    
                    # INVENTORS
                    inventors = []
                    inv_list = bib.get("parties", {}).get("inventors", {}).get("inventor", [])
                    if isinstance(inv_list, dict):
                        inv_list = [inv_list]
                    for inv in inv_list[:10]:
                        inv_name = inv.get("inventor-name", {})
                        if isinstance(inv_name, dict):
                            name_text = inv_name.get("name", {}).get("$")
                            if name_text:
                                inventors.append(name_text)
                    
                    # IPC CODES - Múltiplos fallbacks
                    ipc_codes = []
                    
                    # Tentar classifications-ipcr primeiro (formato moderno)
                    classifications = bib.get("classifications-ipcr", {}).get("classification-ipcr", [])
                    
                    if not classifications:
                        # Fallback 1: classification-ipc (formato antigo)
                        classifications = bib.get("classification-ipc", [])
                    
                    if not classifications:
                        # Fallback 2: patent-classifications
                        patent_class = bib.get("patent-classifications", {})
                        if isinstance(patent_class, dict):
                            classifications = patent_class.get("classification-ipc", [])
                            if not classifications:
                                classifications = patent_class.get("classification-ipcr", [])
                    
                    if isinstance(classifications, dict):
                        classifications = [classifications]
                    
                    for cls in classifications[:10]:
                        if not isinstance(cls, dict):
                            continue
                            
                        # Montar código IPC: section + class + subclass + main-group + subgroup
                        # Tentar com "$" primeiro (formato comum)
                        section = ""
                        ipc_class = ""
                        subclass = ""
                        main_group = ""
                        subgroup = ""
                        
                        # Formato 1: {"section": {"$": "A"}}
                        if isinstance(cls.get("section"), dict):
                            section = cls.get("section", {}).get("$", "")
                            ipc_class = cls.get("class", {}).get("$", "")
                            subclass = cls.get("subclass", {}).get("$", "")
                            main_group = cls.get("main-group", {}).get("$", "")
                            subgroup = cls.get("subgroup", {}).get("$", "")
                        # Formato 2: {"section": "A"}
                        elif isinstance(cls.get("section"), str):
                            section = cls.get("section", "")
                            ipc_class = cls.get("class", "")
                            subclass = cls.get("subclass", "")
                            main_group = cls.get("main-group", "")
                            subgroup = cls.get("subgroup", "")
                        # Formato 3: Texto completo em "text"
                        elif "text" in cls:
                            ipc_text = cls.get("text", "")
                            if isinstance(ipc_text, dict):
                                ipc_text = ipc_text.get("$", "")
                            if ipc_text and len(ipc_text) >= 4:
                                ipc_codes.append(ipc_text.strip())
                                continue
                        
                        if section:
                            ipc_code = f"{section}{ipc_class}{subclass}{main_group}/{subgroup}"
                            ipc_code = ipc_code.strip()
                            if ipc_code and ipc_code not in ipc_codes:
                                ipc_codes.append(ipc_code)
                    
                    # DATES
                    pub_date = doc_id.get("date", {}).get("$", "")
                    
                    # Filing date - buscar em application-reference
                    filing_date = ""
                    app_ref = pub_ref.get("document-id", [])
                    if isinstance(app_ref, dict):
                        app_ref = [app_ref]
                    for app_doc in app_ref:
                        if app_doc.get("@document-id-type") == "docdb":
                            filing_date = app_doc.get("date", {}).get("$", "")
                            if filing_date:
                                break
                    
                    # Se não encontrou, tentar em outro lugar
                    if not filing_date:
                        app_ref_alt = member.get("application-reference", {}).get("document-id", [])
                        if isinstance(app_ref_alt, dict):
                            app_ref_alt = [app_ref_alt]
                        for app_doc in app_ref_alt:
                            if app_doc.get("@document-id-type") == "docdb":
                                filing_date = app_doc.get("date", {}).get("$", "")
                                if filing_date:
                                    break
                    
                    # Priority date - buscar em priority-claims
                    priority_date = None
                    priority_claims = member.get("priority-claim", [])
                    if isinstance(priority_claims, dict):
                        priority_claims = [priority_claims]
                    for pc in priority_claims:
                        pc_doc = pc.get("document-id", {})
                        if isinstance(pc_doc, dict):
                            priority_date = pc_doc.get("date", {}).get("$")
                            if priority_date:
                                break
                    
                    patent_data = {
                        "patent_number": patent_num,
                        "country": country,
                        "wo_primary": wo_number,
                        "title": title_en,
                        "title_original": title_orig,
                        "abstract": abstract_text,
                        "applicants": applicants,
                        "inventors": inventors,
                        "ipc_codes": ipc_codes,
                        "publication_date": format_date(pub_date),
                        "filing_date": format_date(filing_date),
                        "priority_date": format_date(priority_date) if priority_date else None,
                        "kind": kind,
                        "link_espacenet": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{patent_num}",
                        "link_national": f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={patent_num}" if country == "BR" else None,
                        "country_name": COUNTRY_CODES.get(country, country)
                    }
                    
                    patents[country].append(patent_data)
    
    except Exception as e:
        logger.debug(f"Error getting family for {wo_number}: {e}")
    
    return patents


async def enrich_br_metadata(client: httpx.AsyncClient, token: str, patent_data: Dict) -> Dict:
    """Enriquece metadata de um BR via endpoint individual /published-data/publication/docdb/{BR}/biblio"""
    br_number = patent_data["patent_number"]
    
    try:
        response = await client.get(
            f"https://ops.epo.org/3.2/rest-services/published-data/publication/docdb/{br_number}/biblio",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15.0
        )
        
        if response.status_code != 200:
            return patent_data
        
        data = response.json()
        bib = data.get("ops:world-patent-data", {}).get("exchange-documents", {}).get("exchange-document", {}).get("bibliographic-data", {})
        
        if not bib:
            return patent_data
        
        # ENRIQUECER TITLE se estiver vazio
        if not patent_data.get("title"):
            titles = bib.get("invention-title", [])
            if isinstance(titles, dict):
                titles = [titles]
            for t in titles:
                if t.get("@lang") == "en":
                    patent_data["title"] = t.get("$")
                    break
            if not patent_data.get("title") and titles:
                patent_data["title"] = titles[0].get("$")
        
        # ENRIQUECER ABSTRACT se estiver vazio - Parse robusto
        if not patent_data.get("abstract"):
            abstracts = bib.get("abstract", {})
            if abstracts:
                if isinstance(abstracts, list):
                    # Lista de abstracts em múltiplos idiomas
                    for abs_item in abstracts:
                        if isinstance(abs_item, dict):
                            # Preferir EN
                            if abs_item.get("@lang") == "en":
                                p_elem = abs_item.get("p", {})
                                if isinstance(p_elem, dict):
                                    patent_data["abstract"] = p_elem.get("$")
                                elif isinstance(p_elem, str):
                                    patent_data["abstract"] = p_elem
                                elif isinstance(p_elem, list):
                                    paras = []
                                    for para in p_elem:
                                        if isinstance(para, dict):
                                            paras.append(para.get("$", ""))
                                        elif isinstance(para, str):
                                            paras.append(para)
                                    patent_data["abstract"] = " ".join(paras)
                                break
                    # Se não achou EN, pegar primeiro disponível
                    if not patent_data.get("abstract") and abstracts:
                        first_abs = abstracts[0]
                        if isinstance(first_abs, dict):
                            p_elem = first_abs.get("p", {})
                            if isinstance(p_elem, dict):
                                patent_data["abstract"] = p_elem.get("$")
                            elif isinstance(p_elem, str):
                                patent_data["abstract"] = p_elem
                            elif isinstance(p_elem, list):
                                paras = []
                                for para in p_elem:
                                    if isinstance(para, dict):
                                        paras.append(para.get("$", ""))
                                    elif isinstance(para, str):
                                        paras.append(para)
                                patent_data["abstract"] = " ".join(paras)
                elif isinstance(abstracts, dict):
                    # Single abstract
                    p_elem = abstracts.get("p", {})
                    if isinstance(p_elem, dict):
                        patent_data["abstract"] = p_elem.get("$")
                    elif isinstance(p_elem, str):
                        patent_data["abstract"] = p_elem
                    elif isinstance(p_elem, list):
                        paras = []
                        for para in p_elem:
                            if isinstance(para, dict):
                                paras.append(para.get("$", ""))
                            elif isinstance(para, str):
                                paras.append(para)
                        patent_data["abstract"] = " ".join(paras)
        
        # ENRIQUECER APPLICANTS se estiver vazio
        if not patent_data.get("applicants"):
            parties = bib.get("parties", {}).get("applicants", {}).get("applicant", [])
            if isinstance(parties, dict):
                parties = [parties]
            applicants = []
            for p in parties[:10]:
                name = p.get("applicant-name", {})
                if isinstance(name, dict):
                    name_text = name.get("name", {}).get("$")
                    if name_text:
                        applicants.append(name_text)
            if applicants:
                patent_data["applicants"] = applicants
        
        # ENRIQUECER INVENTORS se estiver vazio
        if not patent_data.get("inventors"):
            inv_list = bib.get("parties", {}).get("inventors", {}).get("inventor", [])
            if isinstance(inv_list, dict):
                inv_list = [inv_list]
            inventors = []
            for inv in inv_list[:10]:
                inv_name = inv.get("inventor-name", {})
                if isinstance(inv_name, dict):
                    name_text = inv_name.get("name", {}).get("$")
                    if name_text:
                        inventors.append(name_text)
            if inventors:
                patent_data["inventors"] = inventors
        
        # ENRIQUECER IPC CODES se estiver vazio - Parse robusto
        if not patent_data.get("ipc_codes"):
            ipc_codes = []
            
            # Tentar classifications-ipcr primeiro
            classifications = bib.get("classifications-ipcr", {}).get("classification-ipcr", [])
            
            if not classifications:
                # Fallback 1: classification-ipc
                classifications = bib.get("classification-ipc", [])
            
            if not classifications:
                # Fallback 2: patent-classifications
                patent_class = bib.get("patent-classifications", {})
                if isinstance(patent_class, dict):
                    classifications = patent_class.get("classification-ipc", [])
                    if not classifications:
                        classifications = patent_class.get("classification-ipcr", [])
            
            if isinstance(classifications, dict):
                classifications = [classifications]
            
            for cls in classifications[:10]:
                if not isinstance(cls, dict):
                    continue
                
                section = ""
                ipc_class = ""
                subclass = ""
                main_group = ""
                subgroup = ""
                
                # Formato 1: {"section": {"$": "A"}}
                if isinstance(cls.get("section"), dict):
                    section = cls.get("section", {}).get("$", "")
                    ipc_class = cls.get("class", {}).get("$", "")
                    subclass = cls.get("subclass", {}).get("$", "")
                    main_group = cls.get("main-group", {}).get("$", "")
                    subgroup = cls.get("subgroup", {}).get("$", "")
                # Formato 2: {"section": "A"}
                elif isinstance(cls.get("section"), str):
                    section = cls.get("section", "")
                    ipc_class = cls.get("class", "")
                    subclass = cls.get("subclass", "")
                    main_group = cls.get("main-group", "")
                    subgroup = cls.get("subgroup", "")
                # Formato 3: Texto completo
                elif "text" in cls:
                    ipc_text = cls.get("text", "")
                    if isinstance(ipc_text, dict):
                        ipc_text = ipc_text.get("$", "")
                    if ipc_text and len(ipc_text) >= 4:
                        ipc_codes.append(ipc_text.strip())
                        continue
                
                if section:
                    ipc_code = f"{section}{ipc_class}{subclass}{main_group}/{subgroup}"
                    ipc_code = ipc_code.strip()
                    if ipc_code and ipc_code not in ipc_codes:
                        ipc_codes.append(ipc_code)
            
            if ipc_codes:
                patent_data["ipc_codes"] = ipc_codes
        
        await asyncio.sleep(0.1)  # Rate limiting
        
    except Exception as e:
        logger.debug(f"Error enriching {br_number}: {e}")
    
    return patent_data


async def enrich_from_google_patents(client: httpx.AsyncClient, patent_data: Dict) -> Dict:
    """Fallback: Enriquece metadata via Google Patents para campos ainda vazios"""
    br_number = patent_data["patent_number"]
    
    # Se já tem tudo, não precisa buscar
    if (patent_data.get("abstract") and 
        patent_data.get("applicants") and 
        patent_data.get("inventors") and 
        patent_data.get("ipc_codes")):
        return patent_data
    
    try:
        # Tentar versão EN primeiro, depois PT
        for lang in ['en', 'pt']:
            url = f"https://patents.google.com/patent/{br_number}/{lang}"
            response = await client.get(url, timeout=15.0, follow_redirects=True)
            
            if response.status_code != 200:
                continue
            
            html = response.text
            import re
            
            # Parse ABSTRACT se estiver vazio
            if not patent_data.get("abstract"):
                # Método 1: <div class="abstract">
                abstract_match = re.search(r'<div[^>]*class="abstract"[^>]*>(.*?)</div>', html, re.DOTALL)
                if not abstract_match:
                    # Método 2: <section itemprop="abstract"><div itemprop="content">
                    abstract_match = re.search(r'<section[^>]*itemprop="abstract"[^>]*>.*?<div[^>]*itemprop="content"[^>]*>(.*?)</div>', html, re.DOTALL)
                
                if abstract_match:
                    abstract_html = abstract_match.group(1)
                    # Extrair texto de dentro de tags <div class="abstract">
                    inner_abstract = re.search(r'<div[^>]*class="abstract"[^>]*>(.*?)</div>', abstract_html, re.DOTALL)
                    if inner_abstract:
                        abstract_html = inner_abstract.group(1)
                    
                    # Limpar HTML tags mas preservar conteúdo
                    abstract_text = re.sub(r'<[^>]+>', ' ', abstract_html)
                    # Decodificar entidades HTML
                    abstract_text = abstract_text.replace('&quot;', '"').replace('&#34;', '"')
                    abstract_text = abstract_text.replace('&lt;', '<').replace('&gt;', '>')
                    abstract_text = abstract_text.replace('&amp;', '&')
                    # Limpar whitespace excessivo
                    abstract_text = ' '.join(abstract_text.split())
                    # Limpar separador "---" comum em patents BR
                    abstract_text = re.sub(r'-{10,}.*', '', abstract_text).strip()
                    
                    if abstract_text and len(abstract_text) > 20:
                        patent_data["abstract"] = abstract_text[:3000]
                        logger.debug(f"   ✅ Abstract found for {br_number} ({len(abstract_text)} chars)")
                        break  # Achou, não precisa tentar outro idioma
            
            # Parse APPLICANTS se estiver vazio
            if not patent_data.get("applicants"):
                # Método 1: meta DC.contributor scheme="assignee"
                applicants = re.findall(r'<meta[^>]+name="DC\.contributor"[^>]+content="([^"]+)"[^>]+scheme="assignee"', html)
                if not applicants:
                    # Método 2: dd itemprop="assigneeName" ou "applicantName"
                    applicants = re.findall(r'<dd[^>]*itemprop="(?:assignee|applicant)Name"[^>]*>(.*?)</dd>', html, re.DOTALL)
                    applicants = [re.sub(r'<[^>]+>', '', a).strip() for a in applicants]
                
                if applicants:
                    clean_applicants = [a for a in applicants[:10] if a]
                    if clean_applicants:
                        patent_data["applicants"] = clean_applicants
                        logger.debug(f"   ✅ {len(clean_applicants)} applicants found for {br_number}")
            
            # Parse INVENTORS se estiver vazio
            if not patent_data.get("inventors"):
                # Método 1: meta DC.contributor scheme="inventor"
                inventors = re.findall(r'<meta[^>]+name="DC\.contributor"[^>]+content="([^"]+)"[^>]+scheme="inventor"', html)
                if not inventors:
                    # Método 2: dd itemprop="inventorName"
                    inventors = re.findall(r'<dd[^>]*itemprop="inventorName"[^>]*>(.*?)</dd>', html, re.DOTALL)
                    inventors = [re.sub(r'<[^>]+>', '', i).strip() for i in inventors]
                
                if inventors:
                    clean_inventors = [i for i in inventors[:10] if i]
                    if clean_inventors:
                        patent_data["inventors"] = clean_inventors
                        logger.debug(f"   ✅ {len(clean_inventors)} inventors found for {br_number}")
            
            # Parse IPC CODES se estiver vazio  
            if not patent_data.get("ipc_codes"):
                # Buscar em meta tags ou spans
                ipc_codes = re.findall(r'<span[^>]*itemprop="Classifi[^"]*cation"[^>]*>([^<]+)</span>', html)
                if ipc_codes:
                    clean_codes = []
                    for code in ipc_codes[:10]:
                        code = code.strip()
                        if code and len(code) >= 4:
                            clean_codes.append(code)
                    if clean_codes:
                        patent_data["ipc_codes"] = clean_codes
                        logger.debug(f"   ✅ {len(clean_codes)} IPC codes found for {br_number}")
            
            # Se encontrou pelo menos um campo, sucesso
            if (patent_data.get("abstract") or patent_data.get("applicants") or 
                patent_data.get("inventors") or patent_data.get("ipc_codes")):
                break
        
        await asyncio.sleep(0.3)  # Rate limiting Google
        
    except Exception as e:
        logger.debug(f"   ❌ Error fetching Google Patents for {br_number}: {e}")
    
    return patent_data


# ============= ENDPOINTS =============

@app.get("/")
async def root():
    return {
        "message": "Pharmyrus v27.4 - Robust Abstract & IPC Parse (PRODUCTION)", 
        "version": "28.0",
        "layers": ["EPO OPS (FULL v26 + METADATA)", "Google Patents (AGGRESSIVE)"],
        "metadata_fields": ["title", "abstract", "applicants", "inventors", "ipc_codes", "filing_date", "priority_date"],
        "features": ["Multiple BR per WO", "Individual BR enrichment", "Robust abstract/IPC parse"]
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "28.0"}


@app.get("/countries")
async def list_countries():
    return {"countries": COUNTRY_CODES}


@app.post("/search")
async def search_patents(request: SearchRequest):
    """
    Busca em 2 camadas COMPLETAS:
    1. EPO OPS (código COMPLETO v26 - citations, related, queries expandidas)
    2. Google Patents (crawler AGRESSIVO - todas variações)
    """
    
    start_time = datetime.now()
    
    molecule = request.nome_molecula.strip()
    brand = (request.nome_comercial or "").strip()
    target_countries = [c.upper() for c in request.paises_alvo if c.upper() in COUNTRY_CODES]
    
    if not target_countries:
        target_countries = ["BR"]
    
    logger.info(f"🚀 Search v27.5-FIXED started: {molecule} | Countries: {target_countries}")
    
    async with httpx.AsyncClient() as client:
        # ===== LAYER 1: EPO (CÓDIGO COMPLETO v26) =====
        logger.info("🔵 LAYER 1: EPO OPS (FULL)")
        
        token = await get_epo_token(client)
        pubchem = await get_pubchem_data(client, molecule)
        logger.info(f"   PubChem: {len(pubchem['dev_codes'])} dev codes, CAS: {pubchem['cas']}")
        
        # Queries COMPLETAS
        queries = build_search_queries(molecule, brand, pubchem["dev_codes"], pubchem["cas"])
        logger.info(f"   Executing {len(queries)} EPO queries...")
        
        epo_wos = set()
        for query in queries:
            wos = await search_epo(client, token, query)
            epo_wos.update(wos)
            await asyncio.sleep(0.2)
        
        logger.info(f"   ✅ EPO text search: {len(epo_wos)} WOs")
        
        # Buscar WOs relacionados via prioridades (CRÍTICO!)
        if epo_wos:
            related_wos = await search_related_wos(client, token, list(epo_wos)[:10])
            if related_wos:
                logger.info(f"   ✅ EPO priority search: {len(related_wos)} additional WOs")
                epo_wos.update(related_wos)
        
        # Buscar WOs via citações (CRÍTICO!)
        key_wos = list(epo_wos)[:5]
        citation_wos = set()
        for wo in key_wos:
            citing = await search_citations(client, token, wo)
            citation_wos.update(citing)
            await asyncio.sleep(0.2)
        
        if citation_wos:
            new_from_citations = citation_wos - epo_wos
            logger.info(f"   ✅ EPO citation search: {len(new_from_citations)} NEW WOs from citations")
            epo_wos.update(citation_wos)
        
        logger.info(f"   ✅ EPO TOTAL: {len(epo_wos)} WOs")
        
        # ===== INPI RUN #1: After EPO Discovery =====
        groq_api_key = os.getenv("GROQ_API_KEY", "")
        inpi_run1_results = await execute_inpi_search(
            run_number=1,
            run_label="After EPO Discovery",
            molecule=molecule,
            brand=brand,
            dev_codes=pubchem["dev_codes"],
            known_wos=list(epo_wos),
            groq_api_key=groq_api_key
        )
        
        # ===== LAYER 2: GOOGLE PATENTS (AGRESSIVO) =====
        logger.info("🟢 LAYER 2: Google Patents (AGGRESSIVE)")
        
        google_wos = await google_crawler.enrich_with_google(
            molecule=molecule,
            brand=brand,
            dev_codes=pubchem["dev_codes"],
            cas=pubchem["cas"],
            epo_wos=epo_wos
        )
        
        logger.info(f"   ✅ Google found: {len(google_wos)} NEW WOs")
        
        # Merge WOs
        all_wos = epo_wos | google_wos
        logger.info(f"   ✅ Total WOs (EPO + Google): {len(all_wos)}")
        
        # ===== INPI RUN #2: After Google Discovery =====
        inpi_run2_results = await execute_inpi_search(
            run_number=2,
            run_label="After Google Discovery (NEW WOs)",
            molecule=molecule,
            brand=brand,
            dev_codes=pubchem["dev_codes"],
            known_wos=list(google_wos),  # APENAS os novos WOs do Google!
            groq_api_key=groq_api_key
        )
        
        # ===== INPI RUN #3: After EPO Family Lookups (placeholder - will run later) =====
        # Esta execução será feita APÓS family lookups completar
        
        # Extrair patentes dos países alvo via EPO FAMILY LOOKUPS
        # LIMITE CRÍTICO: Apenas primeiros 100 WOs para evitar timeout!
        logger.info("📍 EPO Family Lookups: Processing first 100 WOs (TIMEOUT PROTECTION)")
        
        patents_by_country = {cc: [] for cc in target_countries}
        seen_patents = set()
        
        # LIMITE: Apenas 100 WOs para evitar timeout
        wos_to_process = sorted(all_wos)[:100]
        logger.info(f"   Limited to {len(wos_to_process)}/{len(all_wos)} WOs for family lookup")
        
        for i, wo in enumerate(wos_to_process):
            if i > 0 and i % 20 == 0:
                logger.info(f"   Processing WO {i}/{len(wos_to_process)}...")
            
            family_patents = await get_family_patents(client, token, wo, target_countries)
            
            for country, patents in family_patents.items():
                for p in patents:
                    pnum = p["patent_number"]
                    if pnum not in seen_patents:
                        seen_patents.add(pnum)
                        patents_by_country[country].append(p)
            
            await asyncio.sleep(0.3)
        
        all_patents = []
        for country, patents in patents_by_country.items():
            all_patents.extend(patents)
        
        # ENRIQUECER BRs com metadata incompleta via endpoint individual
        logger.info(f"   Enriching BRs with incomplete metadata...")
        br_patents = [p for p in all_patents if p["country"] == "BR"]
        incomplete_brs = [
            p for p in br_patents 
            if not p.get("title") or not p.get("abstract") or not p.get("applicants") or not p.get("inventors") or not p.get("ipc_codes")
        ]
        
        logger.info(f"   Found {len(incomplete_brs)} BRs with incomplete metadata")
        
        for i, patent in enumerate(incomplete_brs):
            enriched = await enrich_br_metadata(client, token, patent)
            # Update in-place
            patent.update(enriched)
            
            if (i + 1) % 10 == 0:
                logger.info(f"   Enriched {i + 1}/{len(incomplete_brs)} BRs...")
        
        logger.info(f"   ✅ BR enrichment complete")
        
        # FALLBACK: Google Patents para BRs com metadata ainda incompleta
        logger.info(f"🌐 Google Patents fallback for missing metadata...")
        still_incomplete = [
            p for p in br_patents 
            if not p.get("abstract") or not p.get("applicants") or not p.get("inventors") or not p.get("ipc_codes")
        ]
        
        if still_incomplete:
            logger.info(f"   Found {len(still_incomplete)} BRs still incomplete after EPO")
            for i, patent in enumerate(still_incomplete):
                enriched = await enrich_from_google_patents(client, patent)
                patent.update(enriched)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"   Google enriched {i + 1}/{len(still_incomplete)} BRs...")
            
            logger.info(f"   ✅ Google Patents fallback complete")
        else:
            logger.info(f"   ✅ All BRs complete from EPO, skipping Google fallback")
        
        logger.info(f"📊 Post-Family Summary: {len(all_wos)} WOs, {len(patents_by_country.get('BR', []))} BRs from EPO")
        
        # ===== INPI RUN #3: After EPO Family Lookups =====
        inpi_run3_results = await execute_inpi_search(
            run_number=3,
            run_label="After EPO Family Lookups",
            molecule=molecule,
            brand=brand,
            dev_codes=pubchem["dev_codes"],
            known_wos=list(all_wos),  # TODOS os WOs descobertos
            groq_api_key=groq_api_key
        )
        
        # ===== CONSOLIDATE ALL INPI RESULTS FROM 3 RUNS =====
        logger.info("=" * 100)
        logger.info("📊 CONSOLIDATING INPI RESULTS FROM ALL 3 RUNS")
        logger.info("=" * 100)
        logger.info(f"   RUN #1 (After EPO): {len(inpi_run1_results)} BRs")
        logger.info(f"   RUN #2 (After Google): {len(inpi_run2_results)} BRs")
        logger.info(f"   RUN #3 (After Family): {len(inpi_run3_results)} BRs")
        
        # Combinar todos os resultados INPI (removendo duplicatas)
        all_inpi_results = []
        seen_inpi_brs = set()
        
        for results_list in [inpi_run1_results, inpi_run2_results, inpi_run3_results]:
            for patent in results_list:
                br_num = patent.get("patent_number")
                if br_num and br_num not in seen_inpi_brs:
                    seen_inpi_brs.add(br_num)
                    all_inpi_results.append(patent)
        
        logger.info(f"   ✅ TOTAL UNIQUE BRs from INPI: {len(all_inpi_results)}")
        logger.info("=" * 100)
        logger.info("")
        
        # ===== MERGE INPI RESULTS WITH EPO PATENTS =====
        logger.info("🔗 Merging INPI results with EPO patents...")
        
        inpi_new_brs = 0
        inpi_enriched = 0
        
        for inpi_patent in all_inpi_results:
            br_num = inpi_patent.get("patent_number")
            if not br_num:
                continue
            
            # Check se BR já existe
            existing_br = next((p for p in patents_by_country["BR"] if p["patent_number"] == br_num), None)
            
            if existing_br:
                # Enriquecer BR existente com dados INPI (português)
                if inpi_patent.get("title") and not existing_br.get("title_pt"):
                    existing_br["title_pt"] = inpi_patent["title"]
                if inpi_patent.get("applicants") and not existing_br.get("applicants"):
                    existing_br["applicants"] = inpi_patent["applicants"]
                if inpi_patent.get("abstract") and not existing_br.get("abstract"):
                    existing_br["abstract"] = inpi_patent["abstract"]
                inpi_enriched += 1
            else:
                # Novo BR descoberto via INPI!
                new_br = {
                    "patent_number": br_num,
                    "country": "BR",
                    "title": inpi_patent.get("title", ""),
                    "title_pt": inpi_patent.get("title", ""),
                    "abstract": inpi_patent.get("abstract", ""),
                    "filing_date": inpi_patent.get("filing_date", ""),
                    "applicants": inpi_patent.get("applicants", []),
                    "source": "INPI",
                    "discovered_by": "Layer 3 INPI",
                    "link_espacenet": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{br_num}",
                    "link_national": f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={br_num}",
                    "country_name": "Brazil"
                }
                patents_by_country["BR"].append(new_br)
                inpi_new_brs += 1
                logger.info(f"   🆕 NEW BR from INPI: {br_num}")
        
        # Rebuild all_patents list
        all_patents = []
        for country, patents in patents_by_country.items():
            all_patents.extend(patents)
        
        logger.info(f"   ✅ INPI enriched {inpi_enriched} existing BRs, discovered {inpi_new_brs} NEW BRs")
        
        # Buscar abstracts para patentes que não têm
        logger.info(f"   Fetching abstracts for patents without abstract...")
        patents_without_abstract = [p for p in all_patents if p.get("abstract") is None]
        logger.info(f"   Found {len(patents_without_abstract)} patents without abstract")
        
        for i, patent in enumerate(patents_without_abstract[:20]):  # Limitar a 20 para não demorar muito
            abstract = await get_patent_abstract(client, token, patent["patent_number"])
            if abstract:
                patent["abstract"] = abstract
            await asyncio.sleep(0.2)
        
        logger.info(f"   ✅ Abstract enrichment complete")
        
        all_patents.sort(key=lambda x: x.get("publication_date", "") or "", reverse=True)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        return {
            "metadata": {
                "molecule": molecule,
                "brand_name": brand,
                "search_date": datetime.now().isoformat(),
                "target_countries": target_countries,
                "elapsed_seconds": round(elapsed, 2),
                "version": "Pharmyrus v28.9 (ZERO PLAYWRIGHT)",
                "sources": ["EPO OPS (FULL)", "Google Patents (AGGRESSIVE)", "INPI Brazilian (DIRECT)"]
            },
            "summary": {
                "total_wos": len(all_wos),
                "epo_wos": len(epo_wos),
                "google_wos": len(google_wos),
                "inpi_new_brs": inpi_new_brs,
                "inpi_enriched": inpi_brs_found,
                "total_patents": len(all_patents),
                "by_country": {c: len(patents_by_country.get(c, [])) for c in target_countries},
                "pubchem_dev_codes": pubchem["dev_codes"],
                "pubchem_cas": pubchem["cas"]
            },
            "wo_patents": sorted(list(all_wos)),
            "patents_by_country": patents_by_country,
            "all_patents": all_patents
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
