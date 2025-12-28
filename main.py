"""Pharmyrus v29.1 COMPLETE - EPO + Google + INPI + Merge + Family + P&D"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import base64
import asyncio
import re
import json
from datetime import datetime, timedelta
import logging

from google_patents_crawler import google_crawler
from inpi_crawler import inpi_crawler
from merge_logic import merge_patents, add_family_data_to_wos

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus")

EPO_KEY = "G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X"
EPO_SECRET = "zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAPMFLuVUfiEuAqpdbz"

app = FastAPI(title="Pharmyrus v29.1-COMPLETE", version="29.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class SearchRequest(BaseModel):
    nome_molecula: str
    nome_comercial: Optional[str] = None
    paises_alvo: List[str] = ["BR"]
    incluir_wo: bool = True

def format_date(date_str: str) -> str:
    if not date_str or len(date_str) != 8:
        return date_str
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

# ============= EPO LAYER =============

async def get_epo_token(client: httpx.AsyncClient) -> str:
    creds = f"{EPO_KEY}:{EPO_SECRET}"
    b64_creds = base64.b64encode(creds.encode()).decode()
    
    response = await client.post(
        "https://ops.epo.org/3.2/auth/accesstoken",
        headers={"Authorization": f"Basic {b64_creds}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials"},
        timeout=30.0
    )
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="EPO auth failed")
    
    return response.json()["access_token"]


async def get_pubchem_data(client: httpx.AsyncClient, molecule: str) -> Dict:
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
            
            return {"dev_codes": dev_codes[:10], "cas": cas, "synonyms": synonyms[:20]}
    except Exception as e:
        logger.warning(f"PubChem error: {e}")
    
    return {"dev_codes": [], "cas": None, "synonyms": []}


def build_search_queries(molecule: str, brand: str, dev_codes: List[str], cas: str = None) -> List[str]:
    queries = []
    
    queries.append(f'txt="{molecule}"')
    queries.append(f'ti="{molecule}"')
    queries.append(f'ab="{molecule}"')
    
    if brand:
        queries.append(f'txt="{brand}"')
        queries.append(f'ti="{brand}"')
    
    for code in dev_codes[:5]:
        queries.append(f'txt="{code}"')
        code_no_hyphen = code.replace("-", "")
        if code_no_hyphen != code:
            queries.append(f'txt="{code_no_hyphen}"')
    
    if cas:
        queries.append(f'txt="{cas}"')
    
    return queries


async def search_epo(client: httpx.AsyncClient, token: str, query: str) -> List[str]:
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
        logger.debug(f"Search error: {e}")
    
    return list(wos)


async def get_family_brs(client: httpx.AsyncClient, token: str, wo_number: str) -> List[Dict]:
    try:
        response = await client.get(
            f"https://ops.epo.org/3.2/rest-services/family/publication/docdb/{wo_number}/biblio",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30.0
        )
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        family_members = data.get("ops:world-patent-data", {}).get("ops:patent-family", {}).get("ops:family-member", [])
        
        if not isinstance(family_members, list):
            family_members = [family_members]
        
        br_patents = []
        for member in family_members:
            pub_ref = member.get("publication-reference", {}).get("document-id", {})
            if isinstance(pub_ref, list):
                pub_ref = pub_ref[0]
            
            country = pub_ref.get("country", {}).get("$", "")
            number = pub_ref.get("doc-number", {}).get("$", "")
            kind = pub_ref.get("kind", {}).get("$", "")
            date = pub_ref.get("date", {}).get("$", "")
            
            if country == "BR" and number:
                br_patents.append({
                    "patent_number": f"BR{number}",
                    "country": "BR",
                    "kind": kind,
                    "publication_date": format_date(date) if date else None,
                    "wo_primary": wo_number,
                    "source": "EPO",
                    "link_espacenet": f"https://worldwide.espacenet.com/patent/search?q=pn%3DBR{number}"
                })
        
        return br_patents
        
    except Exception as e:
        logger.error(f"Family error for {wo_number}: {e}")
        return []


async def run_epo_search(molecule: str, brand: str = None):
    async with httpx.AsyncClient() as client:
        token = await get_epo_token(client)
        pubchem = await get_pubchem_data(client, molecule)
        
        queries = build_search_queries(molecule, brand, pubchem["dev_codes"], pubchem.get("cas"))
        
        all_wos = set()
        for query in queries[:20]:
            wos = await search_epo(client, token, query)
            all_wos.update(wos)
            await asyncio.sleep(0.5)
        
        logger.info(f"✅ EPO: {len(all_wos)} WOs")
        
        # Get BR patents from families
        all_brs = []
        for wo in list(all_wos)[:100]:
            brs = await get_family_brs(client, token, wo)
            all_brs.extend(brs)
            await asyncio.sleep(0.3)
        
        logger.info(f"✅ EPO Families: {len(all_brs)} BRs")
        
        return {
            "wos": list(all_wos),
            "brs": all_brs,
            "token": token,
            "pubchem": pubchem
        }


# ============= MAIN SEARCH =============

@app.post("/search")
async def search_patents(request: SearchRequest):
    start_time = datetime.now()
    molecule = request.nome_molecula
    brand = request.nome_comercial
    
    logger.info(f"🚀 Starting search: {molecule}")
    
    # 1. EPO Search
    logger.info("📡 Layer 1: EPO OPS API")
    epo_results = await run_epo_search(molecule, brand)
    
    # 2. Google Patents Search
    logger.info("🌐 Layer 2: Google Patents")
    try:
        google_wos = await google_crawler.search_patents(molecule, epo_results["pubchem"]["synonyms"][:5])
        logger.info(f"✅ Google: {len(google_wos)} NEW WOs")
    except Exception as e:
        logger.error(f"Google error: {e}")
        google_wos = []
    
    # 3. INPI Search
    logger.info("🇧🇷 Layer 3: INPI Brazil")
    try:
        inpi_brs = await inpi_crawler.search_patents(molecule, epo_results["pubchem"]["synonyms"][:5])
        logger.info(f"✅ INPI: {len(inpi_brs)} BRs direct search")
    except Exception as e:
        logger.error(f"INPI error: {e}")
        inpi_brs = []
    
    # 4. INPI by number (get details for EPO BRs)
    logger.info("🔍 Layer 3b: INPI details for EPO BRs")
    br_numbers = [br["patent_number"] for br in epo_results["brs"]]
    try:
        inpi_details = await inpi_crawler.search_by_numbers(br_numbers[:30])
        logger.info(f"✅ INPI Details: {len(inpi_details)} BRs enriched")
    except Exception as e:
        logger.error(f"INPI details error: {e}")
        inpi_details = []
    
    # 5. Merge BR patents
    logger.info("🔀 Merging BR patents")
    all_inpi = inpi_brs + inpi_details
    merged_brs = merge_patents(epo_results["brs"], all_inpi)
    
    # 6. Prepare WO list
    all_wos_unique = list(set(epo_results["wos"] + google_wos))
    
    # Build result
    elapsed = (datetime.now() - start_time).total_seconds()
    
    result = {
        "metadata": {
            "search_id": f"{molecule}_{int(datetime.now().timestamp())}",
            "molecule_name": molecule,
            "brand_name": brand,
            "search_date": datetime.now().isoformat(),
            "cache_expiry_date": (datetime.now() + timedelta(days=180)).isoformat(),
            "target_countries": request.paises_alvo,
            "elapsed_seconds": elapsed,
            "version": "Pharmyrus v29.1-COMPLETE",
            "sources_used": {
                "epo_ops": True,
                "google_patents": True,
                "inpi": True,
                "pubchem": True
            }
        },
        "patent_discovery": {
            "summary": {
                "total_wo_patents": len(all_wos_unique),
                "total_br_patents": len(merged_brs),
                "epo_wos": len(epo_results["wos"]),
                "google_wos": len(google_wos),
                "epo_brs": len(epo_results["brs"]),
                "inpi_direct_brs": len(inpi_brs),
                "inpi_enriched_brs": len(inpi_details),
                "merged_brs": len(merged_brs)
            },
            "wo_patents": [{"wo_number": wo, "source": "EPO/Google"} for wo in all_wos_unique],
            "patents_by_country": {
                "BR": merged_brs
            }
        },
        "research_and_development": {
            "molecular": {
                "pubchem_synonyms": epo_results["pubchem"]["synonyms"],
                "development_codes": epo_results["pubchem"]["dev_codes"],
                "cas_number": epo_results["pubchem"].get("cas"),
                "source": "PubChem"
            },
            "clinical_trials": [],
            "regulatory": {},
            "literature": []
        }
    }
    
    logger.info(f"✅ Search complete in {elapsed:.1f}s")
    logger.info(f"📊 Results: {len(all_wos_unique)} WOs, {len(merged_brs)} BRs")
    
    return result


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "29.1-COMPLETE"}


@app.get("/")
async def root():
    return {
        "service": "Pharmyrus v29.1-COMPLETE",
        "description": "3-Layer Patent Search + Merge + P&D",
        "layers": ["EPO OPS", "Google Patents", "INPI Brazil"],
        "features": ["Intelligent Merge", "Family Expansion", "R&D Data"],
        "endpoints": {
            "/search": "POST - Main search endpoint",
            "/health": "GET - Health check"
        }
    }
