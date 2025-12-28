"""Merge inteligente EPO + INPI + Google Patents"""

import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def merge_patents(epo_patents: List[Dict], inpi_patents: List[Dict], google_patents: List[Dict] = None) -> List[Dict]:
    """
    Merge inteligente de patentes BR de múltiplas fontes
    
    Remove duplicatas e combina dados complementares
    """
    merged = {}
    
    # Process EPO patents
    for patent in epo_patents:
        pn = patent.get("patent_number", "")
        if pn:
            merged[pn] = {
                **patent,
                "sources": ["EPO"],
                "link_espacenet": patent.get("link_espacenet"),
                "applicants": patent.get("applicants", []),
                "inventors": patent.get("inventors", []),
                "ipc_codes": patent.get("ipc_codes", []),
                "documents": [],
                "despachos": []
            }
    
    # Process INPI patents (richer data)
    for patent in inpi_patents:
        pn = patent.get("patent_number", "")
        if not pn:
            continue
        
        if pn in merged:
            # Merge with existing EPO data
            existing = merged[pn]
            
            # Add INPI to sources
            if "INPI" not in existing["sources"]:
                existing["sources"].append("INPI")
            
            # Merge fields (INPI takes priority for some fields)
            existing["title"] = patent.get("title") or existing.get("title")
            existing["abstract"] = patent.get("abstract") or existing.get("abstract")
            existing["attorney"] = patent.get("attorney")  # INPI exclusive
            existing["national_phase_date"] = patent.get("national_phase_date")  # INPI exclusive
            existing["link_national"] = patent.get("link_national")
            
            # Merge lists
            if patent.get("applicants"):
                existing["applicants"] = list(set(existing.get("applicants", []) + patent["applicants"]))
            if patent.get("inventors"):
                existing["inventors"] = list(set(existing.get("inventors", []) + patent["inventors"]))
            if patent.get("ipc_codes"):
                existing["ipc_codes"] = list(set(existing.get("ipc_codes", []) + patent["ipc_codes"]))
            
            # INPI-exclusive data
            existing["documents"] = patent.get("documents", [])
            existing["despachos"] = patent.get("despachos", [])
            existing["pct_number"] = patent.get("pct_number") or existing.get("pct_number")
            existing["pct_date"] = patent.get("pct_date") or existing.get("pct_date")
            existing["wo_number"] = patent.get("wo_number") or existing.get("wo_number")
            existing["wo_date"] = patent.get("wo_date") or existing.get("wo_date")
            
        else:
            # New patent from INPI only
            merged[pn] = {
                **patent,
                "sources": ["INPI"],
                "applicants": patent.get("applicants", []),
                "inventors": patent.get("inventors", []),
                "ipc_codes": patent.get("ipc_codes", []),
                "documents": patent.get("documents", []),
                "despachos": patent.get("despachos", [])
            }
    
    # Process Google Patents (if provided)
    if google_patents:
        for patent in google_patents:
            pn = patent.get("patent_number", "")
            if not pn:
                continue
            
            if pn in merged:
                if "Google Patents" not in merged[pn]["sources"]:
                    merged[pn]["sources"].append("Google Patents")
                merged[pn]["link_google_patents"] = patent.get("link_google_patents")
            else:
                merged[pn] = {
                    **patent,
                    "sources": ["Google Patents"],
                    "applicants": patent.get("applicants", []),
                    "inventors": patent.get("inventors", []),
                    "ipc_codes": patent.get("ipc_codes", []),
                    "documents": [],
                    "despachos": []
                }
    
    # Convert to list
    result = list(merged.values())
    
    logger.info(f"✅ Merged {len(result)} unique BR patents from {len(epo_patents)} EPO + {len(inpi_patents)} INPI")
    
    return result


def add_family_data_to_wos(wo_patents: List[Dict], epo_client, epo_token: str) -> List[Dict]:
    """
    Adiciona dados de família completa aos WOs
    
    Para cada WO, busca todos os países da família (US, EP, CN, JP, etc)
    """
    enriched_wos = []
    
    for wo in wo_patents:
        wo_number = wo.get("wo_number", "")
        if not wo_number:
            enriched_wos.append(wo)
            continue
        
        try:
            # Get family from EPO
            import httpx
            import asyncio
            
            async def get_family():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = {"Authorization": f"Bearer {epo_token}"}
                    family_url = f"https://ops.epo.org/3.2/rest-services/family/publication/docdb/{wo_number}/biblio"
                    
                    response = await client.get(family_url, headers=headers)
                    if response.status_code == 200:
                        return response.json()
                return None
            
            family_data = asyncio.run(get_family())
            
            if family_data:
                # Parse family members
                family_members = []
                
                # Extract from EPO family structure
                ops_data = family_data.get("ops:world-patent-data", {})
                family_info = ops_data.get("ops:patent-family", {})
                members = family_info.get("ops:family-member", [])
                
                if not isinstance(members, list):
                    members = [members]
                
                for member in members:
                    pub_ref = member.get("publication-reference", {}).get("document-id", {})
                    if isinstance(pub_ref, list):
                        pub_ref = pub_ref[0]
                    
                    country = pub_ref.get("country", {}).get("$", "")
                    number = pub_ref.get("doc-number", {}).get("$", "")
                    
                    if country and number:
                        family_members.append({
                            "country": country,
                            "country_code": country,
                            "patent_number": f"{country}{number}",
                            "link_espacenet": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{country}{number}"
                        })
                
                wo["family_members"] = family_members
                wo["family_size"] = len(family_members)
                
                logger.info(f"✅ WO {wo_number}: {len(family_members)} family members")
            
        except Exception as e:
            logger.error(f"Error getting family for {wo_number}: {e}")
        
        enriched_wos.append(wo)
    
    return enriched_wos
