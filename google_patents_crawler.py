"""
Google Patents Crawler v28.13 - HTTPX SIMPLES (RESTAURADO - FUNCIONAVA!)

Versão restaurada que FUNCIONAVA perfeitamente
Busca simples via httpx sem complexidade
"""

import httpx
import asyncio
import logging
import re
from typing import List, Set, Dict, Optional

logger = logging.getLogger("pharmyrus")


class GooglePatentsCrawler:
    """Crawler Google Patents usando HTTP simples"""
    
    def __init__(self):
        self.timeout = 30.0
    
    def _build_search_terms(
        self,
        molecule: str,
        brand: Optional[str],
        dev_codes: List[str],
        cas: Optional[str]
    ) -> List[str]:
        """Constrói termos de busca"""
        
        terms = []
        
        # 1. Molécula principal
        if molecule:
            terms.append(f'"{molecule}" patent')
            terms.append(f'"{molecule}" WO')
        
        # 2. Brand
        if brand:
            terms.append(f'"{brand}" patent')
            terms.append(f'"{brand}" WO')
        
        # 3. Dev codes (primeiros 3)
        for code in dev_codes[:3]:
            if code:
                terms.append(f'"{code}" patent')
        
        # 4. CAS
        if cas:
            terms.append(f'"{cas}" patent')
        
        # 5. Variações (salt forms)
        if molecule:
            terms.append(f'"{molecule} hydrochloride"')
            terms.append(f'"{molecule} crystalline"')
        
        return terms
    
    async def search_google_patents(
        self,
        molecule: str,
        brand: Optional[str],
        dev_codes: List[str],
        cas: Optional[str]
    ) -> Set[str]:
        """
        Busca WO patents no Google via HTTP simples
        
        Returns:
            Set de WO numbers encontrados
        """
        logger.info(f"🔍 Google Patents: Searching for {molecule}...")
        
        search_terms = self._build_search_terms(
            molecule=molecule,
            brand=brand,
            dev_codes=dev_codes,
            cas=cas
        )
        
        logger.info(f"   📋 {len(search_terms)} search terms generated")
        
        all_wos = set()
        
        # Executar buscas
        for i, term in enumerate(search_terms[:10]):  # Limitar a 10
            logger.info(f"   🔍 Search {i+1}/10: {term[:40]}...")
            
            try:
                wos = await self._search_google(term)
                if wos:
                    all_wos.update(wos)
                    logger.info(f"      ✅ Found {len(wos)} WOs")
                
                await asyncio.sleep(1.0)  # Rate limiting
            
            except Exception as e:
                logger.warning(f"      ❌ Error: {e}")
                continue
        
        logger.info(f"   ✅ Google TOTAL: {len(all_wos)} unique WOs")
        
        return all_wos
    
    async def _search_google(self, query: str) -> Set[str]:
        """Busca via Google e extrai WO numbers"""
        
        try:
            url = "https://www.google.com/search"
            params = {
                "q": f"{query} site:patents.google.com",
                "num": 20
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                return set()
            
            html = response.text
            
            # Extrair WO numbers do HTML
            # Padrões:
            # 1. WO2011051540
            # 2. WO/2011/051540
            # 3. WO 2011051540
            
            wos = set()
            
            # Padrão 1: WO seguido de números
            pattern1 = re.findall(r'WO\s*(\d{4})\s*(\d{6})', html)
            for match in pattern1:
                wo = f"WO{match[0]}{match[1]}"
                wos.add(wo)
            
            # Padrão 2: WO com /
            pattern2 = re.findall(r'WO[/\-](\d{4})[/\-](\d{6})', html)
            for match in pattern2:
                wo = f"WO{match[0]}{match[1]}"
                wos.add(wo)
            
            return wos
        
        except Exception as e:
            logger.warning(f"         Google search error: {e}")
            return set()
    
    async def enrich_patents_metadata(
        self,
        patents: List[Dict],
        molecule: str
    ) -> List[Dict]:
        """Placeholder - não usado"""
        return patents


# Singleton instance
google_crawler = GooglePatentsCrawler()
