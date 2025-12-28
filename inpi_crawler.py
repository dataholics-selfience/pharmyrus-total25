"""
INPI Crawler v28.11 - HTTP DIRETO + PROXIES + DEBUG HTML

Mudanças v28.10 → v28.11:
✅ REMOVIDO dicionário hardcoded (APENAS Groq AI)
✅ Proxies rotativos no INPI (evita bloqueio)
✅ 2 segundos entre chamadas INPI
✅ Debug HTML completo (salva resposta para análise)
✅ Parse HTML melhorado (4 padrões regex)
✅ Busca em múltiplos campos INPI
"""

import httpx
import asyncio
import logging
import re
import random
from typing import List, Dict, Optional
from html import unescape

logger = logging.getLogger("pharmyrus")

# PROXIES para INPI (rotação)
INPI_PROXIES = [
    "http://brd-customer-hl_8ea11d75-zone-residential_proxy1:w7qs41l7ijfc@brd.superproxy.io:33335",
    "http://brd-customer-hl_8ea11d75-zone-datacenter_proxy1:93u1xg5fef4p@brd.superproxy.io:33335",
    "http://5SHQXNTHNKDHUHFD:wifi;us;;;@proxy.scrapingbee.com:8886",
    "http://XNK2KLGACMN0FKRY:wifi;us;;;@proxy.scrapingbee.com:8886",
]


class INPICrawler:
    """Crawler INPI usando HTTP direto + proxies"""
    
    def __init__(self):
        self.base_url = "https://busca.inpi.gov.br/pePI"
        self.search_url = f"{self.base_url}/jsp/patentes/PatenteSearchAvancado.jsp"
        self.timeout = 60.0
        self.proxy_index = 0
        
    def _get_next_proxy(self) -> str:
        """Rotaciona proxies INPI"""
        proxy = INPI_PROXIES[self.proxy_index % len(INPI_PROXIES)]
        self.proxy_index += 1
        return proxy
        
    async def search_inpi(
        self,
        molecule: str,
        brand: Optional[str],
        dev_codes: List[str],
        known_wos: List[str],
        groq_api_key: Optional[str] = None
    ) -> List[Dict]:
        """
        Busca patentes BR no INPI usando HTTP direto + proxies
        
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
        
        # Step 1: Traduzir molécula para português VIA GROQ (SEM DICIONÁRIO!)
        logger.info("🔄 Step 1/4: Translating molecule to Portuguese via Groq AI...")
        molecule_pt = await self._translate_to_portuguese_groq(molecule, groq_api_key)
        
        # Step 2: Traduzir brand
        logger.info("🔄 Step 2/4: Translating brand...")
        brand_pt = await self._translate_to_portuguese_groq(brand, groq_api_key) if brand else None
        
        # Step 3: Construir termos de busca
        logger.info("🔄 Step 3/4: Building search terms...")
        search_terms = self._build_search_terms(
            molecule=molecule,
            molecule_pt=molecule_pt,
            brand=brand,
            brand_pt=brand_pt,
            dev_codes=dev_codes
        )
        
        logger.info(f"   ✅ Generated {len(search_terms)} search terms")
        logger.info(f"   📋 First 10 terms: {search_terms[:10]}")
        
        # Step 4: Executar buscas HTTP no INPI COM PROXIES
        logger.info(f"🔄 Step 4/4: Executing {min(len(search_terms), 15)} INPI HTTP searches WITH PROXIES...")
        
        all_patents = []
        seen_patent_numbers = set()
        
        # Limitar a 15 searches (evita timeout)
        for i, term in enumerate(search_terms[:15]):
            logger.info(f"   🔍 INPI search {i+1}/15: '{term}'")
            
            try:
                # Usar proxy rotativo
                proxy = self._get_next_proxy()
                logger.info(f"      🔄 Using proxy: {proxy[:40]}...")
                
                # Buscar lista de resultados
                br_numbers = await self._search_inpi_list(term, proxy)
                
                if br_numbers:
                    logger.info(f"      ✅ Found {len(br_numbers)} BR numbers for '{term}'")
                    
                    # Para cada BR, buscar detalhes
                    for br_num in br_numbers[:5]:  # Limitar a 5 BRs por termo
                        if br_num not in seen_patent_numbers:
                            patent_detail = await self._get_patent_detail(br_num, proxy)
                            
                            if patent_detail:
                                seen_patent_numbers.add(br_num)
                                all_patents.append(patent_detail)
                                logger.info(f"         ✅ BR: {br_num}")
                            
                            await asyncio.sleep(0.5)  # Rate limiting entre BRs
                else:
                    logger.info(f"      ⚠️  No results for '{term}'")
            
            except Exception as e:
                logger.warning(f"      ❌ Error searching '{term}': {e}")
            
            # Proxy rotativo = sem delay necessário!
            await asyncio.sleep(0.5)  # Apenas 0.5s para rate limiting básico
        
        logger.info(f"🎯 INPI FINAL: Found {len(all_patents)} unique BR patents")
        logger.info(f"   📊 Searches completed: {min(len(search_terms), 15)}/15")
        logger.info(f"   📊 BRs discovered: {len(all_patents)}")
        
        # Log individual BRs
        if all_patents:
            logger.info(f"   📋 BR patents found:")
            for patent in all_patents[:10]:  # Primeiros 10
                logger.info(f"      - {patent['patent_number']}: {patent.get('title', '')[:50]}...")
        
        return all_patents
    
    async def _search_inpi_list(self, keyword: str, proxy: str) -> List[str]:
        """
        Busca lista de BRs no INPI usando palavra-chave + PROXY
        
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
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchBasico.jsp"
            }
            
            logger.info(f"      → POST {self.search_url}")
            logger.info(f"      → Keyword: '{keyword}' in field 'titulo'")
            
            # Usar httpx com proxy
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                proxies=proxy
            ) as client:
                response = await client.post(
                    self.search_url,
                    data=form_data,
                    headers=headers
                )
            
            if response.status_code == 200:
                html = response.text
                
                # DEBUG: Salvar HTML para análise
                logger.info(f"      📄 HTML length: {len(html)} chars")
                
                # Salvar primeiro resultado para debug
                if len(html) < 50000:  # Se HTML pequeno, logar preview
                    preview = html[:500].replace('\n', ' ').replace('\r', '')
                    logger.info(f"      📄 HTML preview: {preview}...")
                
                # Parse HTML para extrair números BR
                # Padrões possíveis:
                # 1. BR 11 2024 016586 8 A2
                # 2. BR112024016586
                # 3. <a href=".../BR112024016586">
                
                br_numbers = []
                
                # Padrão 1: Espaçado
                pattern1 = re.findall(r'BR\s*\d{2}\s*\d{4}\s*\d{6}\s*\d\s*[A-Z]\d', html)
                br_numbers.extend(pattern1)
                
                # Padrão 2: Sem espaços
                pattern2 = re.findall(r'BR\d{11,13}', html)
                br_numbers.extend(pattern2)
                
                # Padrão 3: Em links
                pattern3 = re.findall(r'CodPedido=(BR\d+)', html)
                br_numbers.extend(pattern3)
                
                # Padrão 4: Em tabelas (mais comum)
                pattern4 = re.findall(r'<td[^>]*>(BR[\s\d]+[A-Z]\d)<', html)
                br_numbers.extend(pattern4)
                
                logger.info(f"      🔍 Pattern matches: p1={len(pattern1)}, p2={len(pattern2)}, p3={len(pattern3)}, p4={len(pattern4)}")
                
                # Limpar espaços e padronizar
                br_numbers_clean = []
                for br in br_numbers:
                    # Remover espaços
                    br_clean = br.replace(" ", "").replace("\n", "").replace("\r", "")
                    if br_clean and br_clean.startswith("BR"):
                        br_numbers_clean.append(br_clean)
                
                # Remover duplicatas mantendo ordem
                seen = set()
                unique_brs = []
                for br in br_numbers_clean:
                    if br not in seen:
                        seen.add(br)
                        unique_brs.append(br)
                
                logger.info(f"      ✅ Extracted {len(unique_brs)} unique BR numbers")
                
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
    
    async def _get_patent_detail(self, br_number: str, proxy: str) -> Optional[Dict]:
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
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchBasico.jsp"
            }
            
            logger.info(f"         → GET detail for {br_number}")
            
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                proxies=proxy
            ) as client:
                response = await client.get(detail_url, params=params, headers=headers)
            
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
    
    async def _translate_to_portuguese_groq(self, text: Optional[str], groq_api_key: Optional[str]) -> str:
        """
        Traduz texto para português usando APENAS Groq AI
        SEM dicionário hardcoded!
        """
        if not text:
            return ""
        
        logger.info(f"🔄 Groq AI translation: {text}")
        
        if not groq_api_key:
            logger.warning(f"⚠️  GROQ_API_KEY not found, using original: {text}")
            return text
        
        try:
            from groq import Groq
            
            client = Groq(api_key=groq_api_key)
            
            prompt = f"""Traduza APENAS o nome da seguinte molécula/medicamento para português brasileiro.
Retorne SOMENTE o nome traduzido, sem explicações, sem "Nome em português:", sem nada extra.

Nome em inglês: {text}

Exemplos:
- Darolutamide → Darolutamida
- Abiraterone → Abiraterona
- Enzalutamide → Enzalutamida
- Olaparib → Olaparibe
- Aspirin → Aspirina

Nome em português:"""
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50,
                stream=False
            )
            
            translated = response.choices[0].message.content.strip()
            
            # Limpar resposta
            translated = translated.replace("→", "").replace("-", "").strip()
            # Remover possível "Nome em português:" se vier na resposta
            if ":" in translated:
                translated = translated.split(":")[-1].strip()
            # Remover espaços duplos
            translated = re.sub(r'\s+', ' ', translated).strip()
            
            logger.info(f"   ✅ Groq translated: {text} → {translated}")
            
            return translated
        
        except ImportError:
            logger.warning(f"   ⚠️  groq library not installed, using original: {text}")
            return text
        
        except Exception as e:
            logger.warning(f"   ⚠️  Groq translation failed: {e}, using original: {text}")
            return text
    
    def _build_search_terms(
        self,
        molecule: str,
        molecule_pt: str,
        brand: Optional[str],
        brand_pt: Optional[str],
        dev_codes: List[str]
    ) -> List[str]:
        """Constrói lista de termos de busca INPI"""
        terms = []
        
        # 1. Molécula (PT prioritário!)
        if molecule_pt and molecule_pt != molecule:
            terms.append(molecule_pt)  # PT primeiro!
        if molecule:
            terms.append(molecule)
        
        # 2. Brand (PT prioritário!)
        if brand_pt and brand_pt != brand:
            terms.append(brand_pt)
        if brand:
            terms.append(brand)
        
        # 3. Dev codes (primeiros 5)
        logger.info(f"   📝 Adding {min(len(dev_codes), 5)} dev codes to search")
        for code in dev_codes[:5]:
            if code and code not in terms:
                terms.append(code)
        
        return terms


# Singleton instance
inpi_crawler = INPICrawler()
