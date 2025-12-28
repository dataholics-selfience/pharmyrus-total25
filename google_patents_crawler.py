"""
Google Patents Crawler Layer 2 - SEM PLAYWRIGHT (httpx only)
Busca agressiva usando httpx + parse HTML simples
"""
import asyncio
import re
import random
import httpx
from typing import List, Set, Dict


class GooglePatentsCrawler:
    """Crawler AGRESSIVO para descobrir TODAS WOs possíveis - SEM Playwright"""
    
    def __init__(self):
        self.found_wos = set()
        self.timeout = 30.0
    
    def _build_aggressive_search_terms(
        self,
        molecule: str,
        brand: str,
        dev_codes: List[str],
        cas: str
    ) -> List[str]:
        """
        Constrói TODAS as variações de busca imagináveis
        Baseado em: sais, cristais, formulações, síntese, uso terapêutico, enantiômeros
        """
        terms = []
        
        # 1. BÁSICO - Molecule + patent WO
        terms.append(f'"{molecule}" patent WO')
        terms.append(f'"{molecule}" WO site:patents.google.com')
        
        # 2. Brand name
        if brand:
            terms.append(f'"{brand}" patent WO')
            terms.append(f'"{brand}" WO site:patents.google.com')
        
        # 3. Dev codes (primeiros 5)
        for code in dev_codes[:5]:
            terms.append(f'"{code}" patent WO')
            terms.append(f'"{code}" site:patents.google.com')
        
        # 4. CAS number
        if cas:
            terms.append(f'"{cas}" patent WO')
        
        # 5. SAIS - variações químicas
        salt_suffixes = [
            "hydrochloride", "hydrobromide", "sulfate", "phosphate",
            "acetate", "citrate", "maleate", "tartrate", "mesylate",
            "sodium salt", "potassium salt", "calcium salt"
        ]
        for salt in salt_suffixes[:3]:  # Top 3
            terms.append(f'"{molecule} {salt}" WO')
        
        # 6. CRISTAIS - formas polimórficas
        crystal_terms = [
            f'"{molecule} crystalline" WO',
            f'"{molecule} polymorph" WO',
            f'"{molecule} crystal form" WO',
            f'"{molecule} amorphous" WO'
        ]
        terms.extend(crystal_terms[:2])
        
        # 7. FORMULAÇÃO - pharmaceutical composition
        formulation_terms = [
            f'"{molecule} pharmaceutical composition" WO',
            f'"{molecule} formulation" WO',
            f'"{molecule} tablet" WO',
            f'"{molecule} capsule" WO'
        ]
        terms.extend(formulation_terms[:2])
        
        # 8. SÍNTESE - process preparation
        synthesis_terms = [
            f'"{molecule} process preparation" WO',
            f'"{molecule} synthesis" WO',
            f'"{molecule} manufacturing" WO'
        ]
        terms.extend(synthesis_terms[:2])
        
        # 9. USO TERAPÊUTICO - therapeutic use
        therapeutic_terms = [
            f'"{molecule} cancer" WO',
            f'"{molecule} treatment" WO',
            f'"{molecule} therapy" WO',
            f'"{molecule} combination" WO'
        ]
        terms.extend(therapeutic_terms[:2])
        
        # 10. ENANTIÔMEROS - stereoisomers
        if molecule:
            terms.append(f'"(R)-{molecule}" WO')
            terms.append(f'"(S)-{molecule}" WO')
        
        return terms
    
    async def search_google_patents(
        self,
        molecule: str,
        brand: str,
        dev_codes: List[str],
        cas: str
    ) -> Set[str]:
        """
        Busca Google Patents usando httpx (SEM Playwright)
        
        Returns:
            Set de WO numbers descobertos
        """
        print(f"\n🔵 LAYER 2: Google Patents (AGGRESSIVE - httpx only)")
        print(f"   Molecule: {molecule}")
        
        # Construir termos de busca
        search_terms = self._build_aggressive_search_terms(molecule, brand, dev_codes, cas)
        print(f"   ✅ Generated {len(search_terms)} search terms")
        
        self.found_wos = set()
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            # Limitar a 20 searches para não explodir o tempo
            for i, term in enumerate(search_terms[:20]):
                print(f"   🔍 Google search {i+1}/20: {term[:60]}...")
                
                try:
                    # Buscar via Google (sem proxy por enquanto)
                    wos = await self._search_term(client, term)
                    
                    if wos:
                        self.found_wos.update(wos)
                        print(f"      ✅ Found {len(wos)} WOs (total: {len(self.found_wos)})")
                    else:
                        print(f"      ⚠️  No WOs found")
                
                except Exception as e:
                    print(f"      ❌ Error: {e}")
                
                # Rate limiting
                await asyncio.sleep(random.uniform(0.5, 1.5))
        
        print(f"   ✅ Google TOTAL: {len(self.found_wos)} unique WOs")
        return self.found_wos
    
    async def _search_term(self, client: httpx.AsyncClient, search_term: str) -> Set[str]:
        """
        Busca um termo e extrai WO numbers
        
        Usa Google Search direto (pode ser bloqueado - fallback para regex simples)
        """
        wos = set()
        
        try:
            # URL do Google Search
            url = "https://www.google.com/search"
            params = {
                "q": search_term,
                "num": 20  # 20 resultados
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"
            }
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                html = response.text
                
                # Extrair WO numbers do HTML
                # Padrão: WO2013084138, WO 2013084138, WO/2013/084138
                wo_patterns = [
                    r'WO\s*(\d{4})\s*(\d{6})',
                    r'WO/(\d{4})/(\d{6})',
                    r'WO(\d{4})(\d{6})'
                ]
                
                for pattern in wo_patterns:
                    matches = re.findall(pattern, html)
                    for match in matches:
                        wo_num = f"WO{match[0]}{match[1]}"
                        wos.add(wo_num)
            
            else:
                print(f"         ⚠️  Google returned {response.status_code}")
        
        except httpx.TimeoutException:
            print(f"         ⏱️  Timeout")
        
        except Exception as e:
            print(f"         ❌ Error: {e}")
        
        return wos
    
    async def enrich_patents_metadata(
        self,
        patents: List[Dict]
    ) -> List[Dict]:
        """
        Enriquece metadados de patentes via Google Patents
        
        Para patentes que NÃO têm abstract/title do EPO,
        tenta buscar no Google Patents (parse HTML)
        """
        print(f"\n📊 Enriching metadata for {len(patents)} patents...")
        
        enriched = 0
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for patent in patents:
                # Se já tem abstract E title, skip
                if patent.get("abstract") and patent.get("title"):
                    continue
                
                wo_num = patent.get("patent_number", "")
                if not wo_num or not wo_num.startswith("WO"):
                    continue
                
                try:
                    # Buscar no Google Patents
                    metadata = await self._get_google_patents_metadata(client, wo_num)
                    
                    if metadata:
                        # Enriquecer campos faltantes
                        if not patent.get("title") and metadata.get("title"):
                            patent["title"] = metadata["title"]
                            enriched += 1
                        
                        if not patent.get("abstract") and metadata.get("abstract"):
                            patent["abstract"] = metadata["abstract"]
                            enriched += 1
                        
                        if not patent.get("applicants") and metadata.get("applicants"):
                            patent["applicants"] = metadata["applicants"]
                        
                        if not patent.get("inventors") and metadata.get("inventors"):
                            patent["inventors"] = metadata["inventors"]
                    
                    await asyncio.sleep(0.3)
                
                except Exception as e:
                    print(f"   ❌ Error enriching {wo_num}: {e}")
        
        print(f"   ✅ Enriched {enriched} fields")
        return patents
    
    async def _get_google_patents_metadata(
        self,
        client: httpx.AsyncClient,
        wo_number: str
    ) -> Dict:
        """
        Busca metadata de uma patente WO no Google Patents
        """
        try:
            # URL do Google Patents
            url = f"https://patents.google.com/patent/{wo_number}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                html = response.text
                
                # Parse HTML (básico - pode melhorar)
                metadata = {}
                
                # Title
                title_match = re.search(r'<title>(.*?)</title>', html)
                if title_match:
                    metadata["title"] = title_match.group(1).split(" - ")[0].strip()
                
                # Abstract (primeira ocorrência de texto longo)
                abstract_match = re.search(r'<div[^>]*abstract[^>]*>(.*?)</div>', html, re.DOTALL)
                if abstract_match:
                    abstract_text = re.sub(r'<[^>]+>', '', abstract_match.group(1))
                    metadata["abstract"] = abstract_text.strip()[:500]  # Primeiros 500 chars
                
                return metadata
            
            return {}
        
        except Exception:
            return {}


# Singleton instance
google_crawler = GooglePatentsCrawler()
