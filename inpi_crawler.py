"""
INPI Crawler v28.8 - HTTP DIRETO (SEM PLAYWRIGHT, SEM API EXTERNA)

Faz requisições HTTP diretas para:
https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchAvancado.jsp

FLUXO:
1. POST para busca avançada com palavra-chave no campo "(54) Título"
2. Parse HTML da lista de resultados (extrai números BR)
3. GET detalhe de cada BR individual
4. Parse HTML do detalhe (extrai todos os campos)
"""

import httpx
import asyncio
import logging
import re
from typing import List, Dict, Optional
from html import unescape

logger = logging.getLogger("pharmyrus")


class INPICrawler:
    """Crawler INPI usando HTTP direto"""
    
    def __init__(self):
        self.base_url = "https://busca.inpi.gov.br/pePI"
        self.search_url = f"{self.base_url}/jsp/patentes/PatenteSearchAvancado.jsp"
        self.timeout = 30.0
        
    async def search_inpi(
        self,
        molecule: str,
        brand: Optional[str],
        dev_codes: List[str],
        known_wos: List[str],
        groq_api_key: Optional[str] = None
    ) -> List[Dict]:
        """
        Busca patentes BR no INPI usando HTTP direto
        
        Args:
            molecule: Nome da molécula (ex: Darolutamide)
            brand: Nome comercial (ex: Nubeqa)
            dev_codes: Códigos de desenvolvimento (ex: ODM-201)
            known_wos: WOs conhecidos para contexto
            groq_api_key: API key do Groq (para tradução PT)
        
        Returns:
            Lista de patentes BR encontradas
        """
        logger.info("🇧🇷 Layer 3 INPI: Starting HTTP direct search for {}...".format(molecule))
        logger.info(f"   📊 Input: brand={brand}, dev_codes={len(dev_codes)}, known_wos={len(known_wos)}")
        
        # Step 1: Traduzir molécula para português
        logger.info("🔄 Step 1/4: Translating molecule name to Portuguese...")
        molecule_pt = await self._translate_to_portuguese(molecule, groq_api_key)
        
        # Step 2: Traduzir brand
        logger.info("🔄 Step 2/4: Translating brand...")
        brand_pt = await self._translate_to_portuguese(brand, groq_api_key) if brand else None
        
        # Step 3: Construir termos de busca
        logger.info("🔄 Step 3/4: Building search terms...")
        search_terms = self._build_search_terms(
            molecule=molecule,
            molecule_pt=molecule_pt,
            brand=brand,
            brand_pt=brand_pt,
            dev_codes=dev_codes,
            known_wos=known_wos
        )
        
        logger.info(f"   ✅ Generated {len(search_terms)} search terms")
        logger.info(f"   📋 First 10 terms: {search_terms[:10]}")
        
        # Step 4: Executar buscas HTTP no INPI
        logger.info(f"🔄 Step 4/4: Executing {min(len(search_terms), 20)} INPI HTTP searches...")
        
        all_patents = []
        seen_patent_numbers = set()
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            # Limitar a 20 searches
            for i, term in enumerate(search_terms[:20]):
                logger.info(f"   🔍 INPI search {i+1}/20: '{term}'")
                
                try:
                    # Buscar lista de resultados
                    br_numbers = await self._search_inpi_list(client, term)
                    
                    if br_numbers:
                        logger.info(f"      ✅ Found {len(br_numbers)} BR numbers for '{term}'")
                        
                        # Para cada BR, buscar detalhes
                        for br_num in br_numbers[:5]:  # Limitar a 5 BRs por termo
                            if br_num not in seen_patent_numbers:
                                patent_detail = await self._get_patent_detail(client, br_num)
                                
                                if patent_detail:
                                    seen_patent_numbers.add(br_num)
                                    all_patents.append(patent_detail)
                                    logger.info(f"         ✅ BR: {br_num}")
                                
                                await asyncio.sleep(0.3)  # Rate limiting
                    else:
                        logger.info(f"      ⚠️  No results for '{term}'")
                
                except Exception as e:
                    logger.warning(f"      ❌ Error searching '{term}': {e}")
                
                await asyncio.sleep(0.5)
        
        logger.info(f"🎯 INPI FINAL: Found {len(all_patents)} unique BR patents")
        
        return all_patents
    
    async def _search_inpi_list(self, client: httpx.AsyncClient, keyword: str) -> List[str]:
        """
        Busca lista de BRs no INPI usando palavra-chave
        
        Envia POST para PatenteSearchAvancado.jsp com campo "(54) Título"
        Retorna lista de números BR encontrados
        """
        try:
            # Dados do formulário de busca avançada
            form_data = {
                "action": "Avancado",
                "radTipo": "0",  # Patente
                "keyword": keyword,
                "searchField": "titulo",  # Campo (54) Título
                "opcao": "1"
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            logger.info(f"      → POST {self.search_url}")
            logger.info(f"      → Keyword: '{keyword}' in field 'titulo'")
            
            response = await client.post(
                self.search_url,
                data=form_data,
                headers=headers
            )
            
            if response.status_code == 200:
                html = response.text
                
                # Parse HTML para extrair números BR
                # Padrão: BR 11 2024 016586 8 A2 ou BR112024016586
                br_numbers = re.findall(r'BR\s*\d{2}\s*\d{4}\s*\d{6}\s*\d\s*[A-Z]\d', html)
                
                # Limpar espaços
                br_numbers = [br.replace(" ", "") for br in br_numbers]
                
                # Remover duplicatas mantendo ordem
                seen = set()
                unique_brs = []
                for br in br_numbers:
                    if br not in seen:
                        seen.add(br)
                        unique_brs.append(br)
                
                return unique_brs[:10]  # Limitar a 10 BRs por busca
            
            else:
                logger.warning(f"      ⚠️  INPI returned {response.status_code}")
                return []
        
        except httpx.TimeoutException:
            logger.warning(f"      ⏱️  Timeout searching INPI")
            return []
        
        except Exception as e:
            logger.warning(f"      ❌ Error in INPI search: {e}")
            return []
    
    async def _get_patent_detail(self, client: httpx.AsyncClient, br_number: str) -> Optional[Dict]:
        """
        Busca detalhes completos de uma patente BR
        
        Acessa página de detalhe e extrai todos os campos
        """
        try:
            # URL de detalhe
            detail_url = f"{self.base_url}/servlet/PatenteServletController"
            params = {
                "Action": "detail",
                "CodPedido": br_number
            }
            
            logger.info(f"         → GET detail for {br_number}")
            
            response = await client.get(detail_url, params=params)
            
            if response.status_code == 200:
                html = response.text
                
                # Parse HTML
                patent = self._parse_patent_detail_html(br_number, html)
                return patent
            
            else:
                logger.warning(f"         ⚠️  Detail returned {response.status_code}")
                return None
        
        except Exception as e:
            logger.warning(f"         ❌ Error getting detail: {e}")
            return None
    
    def _parse_patent_detail_html(self, br_number: str, html: str) -> Dict:
        """Parse HTML da página de detalhe da patente"""
        
        # Padrões de regex para extrair campos
        title_match = re.search(r'<div id="tituloContext"[^>]*>(.*?)</div>', html, re.DOTALL)
        abstract_match = re.search(r'<div id="resumoContext"[^>]*>(.*?)</div>', html, re.DOTALL)
        
        # Depositante/Titular
        applicants_match = re.findall(r'Nome do Depositante:</font>.*?<font[^>]*>(.*?)</font>', html, re.DOTALL)
        
        # Inventor
        inventors_match = re.findall(r'Nome do Inventor:</font>.*?<font[^>]*>(.*?)</font>', html, re.DOTALL)
        
        # Data de depósito
        filing_date_match = re.search(r'Data.*?dep[oó]sito:</font>.*?(\d{2}/\d{2}/\d{4})', html)
        
        # Limpar textos
        title = self._clean_html_text(title_match.group(1)) if title_match else ""
        abstract = self._clean_html_text(abstract_match.group(1)) if abstract_match else ""
        
        applicants = [self._clean_html_text(app) for app in applicants_match if app.strip()]
        inventors = [self._clean_html_text(inv) for inv in inventors_match if inv.strip()]
        
        filing_date = filing_date_match.group(1) if filing_date_match else ""
        
        # Construir objeto de patente
        patent = {
            "patent_number": br_number,
            "country": "BR",
            "title": title,
            "title_original": title,
            "abstract": abstract,
            "abstract_original": abstract,
            "applicants": applicants[:10],
            "inventors": inventors[:10],
            "ipc_codes": [],
            "publication_date": "",
            "filing_date": filing_date,
            "priority_date": "",
            "kind": "A2",
            "link_espacenet": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{br_number}",
            "link_national": f"{self.base_url}/servlet/PatenteServletController?Action=detail&CodPedido={br_number}",
            "country_name": "Brazil",
            "source": "inpi_http_direct"
        }
        
        return patent
    
    def _clean_html_text(self, text: str) -> str:
        """Remove tags HTML e limpa texto"""
        # Remove tags HTML
        text = re.sub(r'<[^>]+>', '', text)
        # Decodifica entidades HTML
        text = unescape(text)
        # Remove espaços extras
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    async def _translate_to_portuguese(self, text: Optional[str], groq_api_key: Optional[str]) -> str:
        """Traduz texto para português usando Groq AI"""
        if not text:
            return ""
        
        logger.info(f"🔄 Grok translation attempt: {text}")
        
        if not groq_api_key:
            logger.warning(f"⚠️  GROQ_API_KEY not found in env, using original name: {text}")
            logger.info(f"   ✅ Translation result: {text} → {text}")
            return text
        
        try:
            from groq import Groq
            
            client = Groq(api_key=groq_api_key)
            
            prompt = f"""Traduza APENAS o nome da seguinte molécula/medicamento para português brasileiro.
Retorne SOMENTE o nome traduzido, sem explicações.

Nome em inglês: {text}

Exemplos:
- Darolutamide → Darolutamida
- Abiraterone → Abiraterona
- Enzalutamide → Enzalutamida

Nome em português:"""
            
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50,
                stream=False
            )
            
            translated = response.choices[0].message.content.strip()
            translated = translated.replace("→", "").replace("-", "").strip()
            
            logger.info(f"   ✅ Grok translated: {text} → {translated}")
            logger.info(f"   ✅ Translation result: {text} → {translated}")
            
            return translated
        
        except ImportError:
            logger.warning(f"   ⚠️  groq library not installed, using original: {text}")
            logger.info(f"   ✅ Translation result: {text} → {text}")
            return text
        
        except Exception as e:
            logger.warning(f"   ⚠️  Grok translation failed: {e}, using original: {text}")
            logger.info(f"   ✅ Translation result: {text} → {text}")
            return text
    
    def _build_search_terms(
        self,
        molecule: str,
        molecule_pt: str,
        brand: Optional[str],
        brand_pt: Optional[str],
        dev_codes: List[str],
        known_wos: List[str]
    ) -> List[str]:
        """Constrói lista de termos de busca INPI"""
        terms = []
        
        # 1. Molécula (EN + PT)
        if molecule:
            terms.append(molecule)
        if molecule_pt and molecule_pt != molecule:
            terms.append(molecule_pt)
        
        # 2. Brand (EN + PT)
        if brand:
            terms.append(brand)
        if brand_pt and brand_pt != brand:
            terms.append(brand_pt)
        
        # 3. Dev codes (primeiros 5)
        logger.info(f"   📝 Adding {min(len(dev_codes), 5)} dev codes to search")
        for code in dev_codes[:5]:
            if code and code not in terms:
                terms.append(code)
        
        return terms


# Singleton instance
inpi_crawler = INPICrawler()
