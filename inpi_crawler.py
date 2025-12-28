"""
INPI Crawler v28.14 - Playwright (MESMA TÉCNICA QUE GOOGLE!)

Busca patentes BR no INPI usando Playwright
Baseado nas instruções do usuário:
- URL: https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchAvancado.jsp
- Campo: "(54) Título:"
- Busca pública SEM login primeiro
- Fallback para login (dnm48) se necessário
"""

import asyncio
import re
import logging
from typing import List, Dict, Set
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger("pharmyrus")

# Credenciais INPI (fallback se busca pública falhar)
INPI_LOGIN = "dnm48"
INPI_PASSWORD = "cores***"  # Você deve fornecer senha completa


class INPICrawler:
    """Crawler INPI usando Playwright (mesma técnica que Google)"""
    
    def __init__(self):
        self.found_brs = set()
    
    async def search_inpi(
        self,
        molecule: str,
        brand: str,
        dev_codes: List[str],
        groq_api_key: str = None
    ) -> List[Dict]:
        """
        Busca patentes BR no INPI
        
        Returns:
            Lista de patentes BR encontradas
        """
        logger.info("🇧🇷 LAYER 3: INPI Brazilian Patent Office")
        logger.info("=" * 100)
        
        # 1. Traduzir para português via Groq
        molecule_pt = await self._translate_to_portuguese(molecule, groq_api_key)
        brand_pt = await self._translate_to_portuguese(brand, groq_api_key) if brand else None
        
        logger.info(f"   ✅ Translations:")
        logger.info(f"      Molecule: {molecule} → {molecule_pt}")
        if brand_pt:
            logger.info(f"      Brand: {brand} → {brand_pt}")
        
        # 2. Construir termos de busca
        search_terms = self._build_search_terms(molecule_pt, brand_pt, dev_codes)
        logger.info(f"   📋 {len(search_terms)} search terms generated")
        
        # 3. Executar buscas no INPI
        all_patents = []
        
        try:
            # TENTAR BUSCA PÚBLICA PRIMEIRO (SEM LOGIN)
            logger.info(f"   🔓 Trying PUBLIC search (no login)...")
            patents = await self._search_inpi_public(search_terms)
            
            if patents:
                logger.info(f"   ✅ PUBLIC search SUCCESS: {len(patents)} BRs found!")
                all_patents = patents
            else:
                # FALLBACK: LOGIN
                logger.info(f"   ⚠️  PUBLIC search returned 0 results")
                logger.info(f"   🔐 Trying LOGIN search (dnm48)...")
                patents = await self._search_inpi_with_login(search_terms)
                
                if patents:
                    logger.info(f"   ✅ LOGIN search SUCCESS: {len(patents)} BRs found!")
                    all_patents = patents
                else:
                    logger.warning(f"   ❌ Both PUBLIC and LOGIN searches returned 0 results")
        
        except Exception as e:
            logger.error(f"   ❌ INPI search failed: {e}")
        
        logger.info(f"🎯 INPI FINAL: {len(all_patents)} BR patents found")
        logger.info("=" * 100)
        
        return all_patents
    
    async def _translate_to_portuguese(self, text: str, groq_api_key: str) -> str:
        """Traduz texto para português via Groq AI"""
        if not text or not groq_api_key:
            return text
        
        try:
            import httpx
            
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a translator. Translate pharmaceutical terms from English to Brazilian Portuguese. Return ONLY the translation, nothing else."
                    },
                    {
                        "role": "user",
                        "content": f"Translate to Portuguese: {text}"
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 50
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                translation = result["choices"][0]["message"]["content"].strip()
                return translation
            else:
                logger.warning(f"      Groq translation failed, using original: {text}")
                return text
        
        except Exception as e:
            logger.warning(f"      Groq translation error: {e}, using original: {text}")
            return text
    
    def _build_search_terms(
        self,
        molecule_pt: str,
        brand_pt: str,
        dev_codes: List[str]
    ) -> List[str]:
        """Constrói termos de busca para INPI"""
        
        terms = []
        
        # 1. Molécula em português
        if molecule_pt:
            terms.append(molecule_pt)
        
        # 2. Brand em português
        if brand_pt:
            terms.append(brand_pt)
        
        # 3. Dev codes (primeiros 5)
        for code in dev_codes[:5]:
            if code:
                terms.append(code)
        
        return terms[:15]  # Limitar a 15 termos
    
    async def _search_inpi_public(self, search_terms: List[str]) -> List[Dict]:
        """Busca pública no INPI (SEM login)"""
        
        all_patents = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                for i, term in enumerate(search_terms):
                    logger.info(f"   🔍 INPI search {i+1}/{len(search_terms)}: '{term}'")
                    
                    try:
                        # URL INPI busca avançada
                        url = "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchAvancado.jsp"
                        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                        
                        await asyncio.sleep(3)
                        
                        # Preencher campo "(54) Título:" (MAIÚSCULO!)
                        await page.fill('input[name="Titulo"]', term)
                        
                        # Clicar em "Pesquisar"
                        await page.click('input[type="submit"][value="Pesquisar"]')
                        
                        await asyncio.sleep(3)
                        
                        # Extrair BR numbers do resultado
                        content = await page.content()
                        
                        # Regex para BR numbers: BR112024016586, BRPI0610634, etc
                        # Aceita formato com espaços: "BR 11 2024 016586 8"
                        br_matches = re.findall(r'BR\s*[A-Z]*\s*\d[\d\s]{10,15}', content)
                        
                        if br_matches:
                            logger.info(f"      ✅ Found {len(br_matches)} BR numbers")
                            
                            for br in br_matches:
                                # Remover espaços: "BR 11 2024 016586 8" → "BR112024016586"
                                br_clean = br.replace(" ", "")
                                
                                if br_clean not in self.found_brs:
                                    self.found_brs.add(br_clean)
                                    all_patents.append({
                                        "patent_number": br_clean,
                                        "country": "BR",
                                        "source": "INPI",
                                        "search_term": term
                                    })
                                    logger.info(f"         → {br_clean}")
                        else:
                            logger.info(f"      ⚠️  No results for '{term}'")
                        
                        await asyncio.sleep(3)  # INPI é lento, dar tempo!
                    
                    except PlaywrightTimeout:
                        logger.warning(f"      ⏱️  Timeout for '{term}'")
                        continue
                    except Exception as e:
                        logger.warning(f"      ❌ Error for '{term}': {e}")
                        continue
                
                await browser.close()
        
        except Exception as e:
            logger.error(f"   ❌ INPI public search failed: {e}")
        
        return all_patents
    
    async def _search_inpi_with_login(self, search_terms: List[str]) -> List[Dict]:
        """Busca no INPI COM login (dnm48)"""
        
        logger.info(f"   🔐 LOGIN INPI not implemented yet")
        logger.info(f"   💡 If needed, implement login flow with credentials:")
        logger.info(f"      Username: {INPI_LOGIN}")
        logger.info(f"      Password: {INPI_PASSWORD}")
        
        # TODO: Implementar login se necessário
        return []


# Singleton
inpi_crawler = INPICrawler()
