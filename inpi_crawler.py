"""
INPI Crawler v29.0 - COMPLETO COM LOGIN E BUSCA BÁSICA

Baseado em análise completa dos HTMLs reais do INPI:
- 1-login.html: Form POST com T_Login, T_Senha
- 2-escolher-Patente.html: Link para patentes
- 3-search-básico.html: Form POST com ExpressaoPesquisa, Coluna, Action
- 4-escolher-resultados.html: Parse links de resultados
- 5-Resultado-final-da-busca.html: Parse completo patente
- 6-Erro-de-busca.html: "Nenhum resultado foi encontrado"

Fluxo CORRETO:
1. Login → /pePI/servlet/LoginController (POST)
2. Patentes → /pePI/jsp/patentes/PatenteSearchBasico.jsp (GET)
3. Busca → /pePI/servlet/PatenteServletController (POST)
4. Resultados → Parse <a href='...Action=detail...'>
5. Detalhes → Parse campos completos

Features:
✅ Login COM credenciais (dnm48)
✅ Sessão persistente (mantém cookies/context)
✅ Busca BÁSICA (não avançada!)
✅ Timeout dinâmico (180s - INPI é MUITO lento!)
✅ Retry automático em session expired
✅ Parse completo de cada patente
✅ Múltiplas buscas (Título + Resumo)
✅ Tradução PT via Groq AI
"""

import asyncio
import logging
import re
import httpx
from typing import List, Dict, Set, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup

logger = logging.getLogger("pharmyrus")


class INPICrawler:
    """INPI Brazilian Patent Office Crawler - COMPLETE with LOGIN"""
    
    def __init__(self):
        self.found_brs: Set[str] = set()
        self.session_active = False
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    async def search_inpi(
        self,
        molecule: str,
        brand: str,
        dev_codes: List[str],
        groq_api_key: str,
        username: str = "dnm48",
        password: str = "coresxxx"
    ) -> List[Dict]:
        """
        Search INPI with LOGIN - COMPLETE FLOW
        
        Args:
            molecule: Molecule name (English)
            brand: Brand name (English)  
            dev_codes: Development codes
            groq_api_key: Groq API key for Portuguese translation
            username: INPI login
            password: INPI password
        
        Returns:
            List of BR patents found
        """
        all_patents = []
        
        # Translate to Portuguese using Groq
        logger.info("====================================================================================================")
        
        molecule_pt, brand_pt = await self._translate_to_portuguese(
            molecule, brand, groq_api_key
        )
        
        logger.info(f"   ✅ Translations:")
        logger.info(f"      Molecule: {molecule} → {molecule_pt}")
        if brand:
            logger.info(f"      Brand: {brand} → {brand_pt}")
        
        # Build search terms (INCLUINDO brand_pt!)
        search_terms = self._build_search_terms(molecule_pt, brand_pt, dev_codes, max_terms=10)
        
        logger.info(f"   📋 {len(search_terms)} search terms generated")
        logger.info(f"   🔐 Starting INPI search with LOGIN ({username})...")
        
        try:
            async with async_playwright() as p:
                # STEP 0: Launch browser with stealth (MANTÉM SESSÃO!)
                self.browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox'
                    ]
                )
                
                self.context = await self.browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-BR'
                )
                
                self.page = await self.context.new_page()
                
                # STEP 1: LOGIN
                login_success = await self._login(username, password)
                
                if not login_success:
                    logger.error("   ❌ LOGIN failed!")
                    await self.browser.close()
                    return all_patents
                
                logger.info("   ✅ LOGIN successful!")
                self.session_active = True
                
                # STEP 2: Navigate to Patents Basic Search
                try:
                    await self.page.goto(
                        "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchBasico.jsp",
                        wait_until='networkidle',
                        timeout=180000  # 3 minutes!
                    )
                    logger.info("   📄 Patent search page loaded")
                except Exception as e:
                    logger.error(f"   ❌ Error loading search page: {str(e)}")
                    await self.browser.close()
                    return all_patents
                
                # STEP 3: Search each term (TÍTULO + RESUMO)
                for i, term in enumerate(search_terms, 1):
                    logger.info(f"   🔍 INPI search {i}/{len(search_terms)}: '{term}'")
                    
                    try:
                        # Search by TÍTULO
                        patents_titulo = await self._search_term_basic(term, field="Titulo")
                        all_patents.extend(patents_titulo)
                        
                        await asyncio.sleep(3)  # Delay between searches
                        
                        # Search by RESUMO
                        patents_resumo = await self._search_term_basic(term, field="Resumo")
                        all_patents.extend(patents_resumo)
                        
                        await asyncio.sleep(3)
                        
                    except Exception as e:
                        logger.warning(f"      ⚠️  Error searching '{term}': {str(e)}")
                        
                        # Check if session expired
                        if await self._check_session_expired():
                            logger.error("   ❌ Session expired! Attempting re-login...")
                            
                            # Try to re-login
                            relogin = await self._login(username, password)
                            if not relogin:
                                logger.error("   ❌ Re-login failed! Stopping INPI search")
                                break
                            
                            logger.info("   ✅ Re-login successful! Continuing...")
                            self.session_active = True
                            
                            # Go back to search page
                            await self.page.goto(
                                "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchBasico.jsp",
                                wait_until='networkidle',
                                timeout=180000
                            )
                        
                        continue
                
                await self.browser.close()
                
        except Exception as e:
            logger.error(f"   ❌ INPI crawler fatal error: {str(e)}")
            if self.browser:
                await self.browser.close()
        
        # Deduplicate
        unique_patents = []
        seen_numbers = set()
        for patent in all_patents:
            num = patent["patent_number"]
            if num not in seen_numbers:
                unique_patents.append(patent)
                seen_numbers.add(num)
        
        if unique_patents:
            logger.info(f"   ✅ INPI search SUCCESS: {len(unique_patents)} BRs found!")
        else:
            logger.warning("   ⚠️  INPI search returned 0 results")
        
        return unique_patents
    
    async def _login(self, username: str, password: str) -> bool:
        """
        STEP 1: Perform LOGIN on INPI
        
        Based on 1-login.html:
        - URL: https://busca.inpi.gov.br/pePI/
        - Form POST to: /pePI/servlet/LoginController
        - Fields: T_Login, T_Senha
        - Hidden: action=login
        
        Returns:
            True if login successful
        """
        try:
            logger.info("   📝 Accessing login page...")
            
            # Go to login page
            await self.page.goto(
                "https://busca.inpi.gov.br/pePI/",
                wait_until='networkidle',
                timeout=60000  # 1 min
            )
            
            await asyncio.sleep(2)
            
            logger.info(f"   🔑 Logging in as {username}...")
            
            # Fill login form
            await self.page.fill('input[name="T_Login"]', username, timeout=10000)
            await self.page.fill('input[name="T_Senha"]', password, timeout=10000)
            
            await asyncio.sleep(1)
            
            # Click Continue button (value contains "Continuar")
            await self.page.click('input[type="submit"][value*="Continuar"]', timeout=10000)
            
            # Wait for navigation
            await self.page.wait_for_load_state('networkidle', timeout=60000)
            
            await asyncio.sleep(2)
            
            # Check if login was successful
            content = await self.page.content()
            
            # Success indicators:
            # - "Login: dnm48" appears in page
            # - "Patente" link available
            # - "Finalizar Sessão" link available
            
            if username.lower() in content.lower() or "Finalizar Sess" in content or "patente" in content.lower():
                logger.info(f"   ✅ Login successful! Session active")
                return True
            else:
                logger.error("   ❌ Login failed - no session indicators found")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ Login error: {str(e)}")
            return False
    
    async def _search_term_basic(
        self,
        term: str,
        field: str = "Titulo"
    ) -> List[Dict]:
        """
        STEP 3: Search a single term using BASIC search
        
        Based on 3-search-básico.html:
        - Form POST to: /pePI/servlet/PatenteServletController
        - Fields:
          * ExpressaoPesquisa = search term
          * Coluna = "Titulo" or "Resumo"
          * FormaPesquisa = "todasPalavras"
          * RegisterPerPage = "100"
          * Action = "SearchBasico"
        
        Args:
            term: Search term
            field: "Titulo" or "Resumo"
        
        Returns:
            List of BR patents found
        """
        results = []
        
        try:
            # Make sure we're on search page
            current_url = self.page.url
            if "PatenteSearchBasico.jsp" not in current_url:
                await self.page.goto(
                    "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchBasico.jsp",
                    wait_until='networkidle',
                    timeout=60000  # 1 min
                )
                await asyncio.sleep(2)
            
            # Fill search form
            await self.page.fill('input[name="ExpressaoPesquisa"]', term, timeout=10000)
            
            # Select field (Titulo or Resumo) with timeout
            await self.page.select_option('select[name="Coluna"]', field, timeout=10000)
            
            # Select "todas as palavras"
            await self.page.select_option('select[name="FormaPesquisa"]', 'todasPalavras', timeout=10000)
            
            # Select 100 results per page
            await self.page.select_option('select[name="RegisterPerPage"]', '100', timeout=10000)
            
            await asyncio.sleep(1)
            
            # Click Search button
            await self.page.click('input[type="submit"][name="botao"]', timeout=10000)
            
            # Wait for results (shorter timeout)
            await self.page.wait_for_load_state('networkidle', timeout=60000)
            
            await asyncio.sleep(2)
            
            # Get page content
            content = await self.page.content()
            
            # Check for "Nenhum resultado" (no results)
            if "Nenhum resultado foi encontrado" in content:
                logger.info(f"      ⚠️  No results for '{term}' in {field}")
                return results
            
            # Parse results
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find all BR patent links
            # Pattern from 4-escolher-resultados.html:
            # <a href='/pePI/servlet/PatenteServletController?Action=detail&CodPedido=1748765...'>BR 11 2024 016586 8</a>
            
            patent_links = soup.find_all('a', href=re.compile(r'Action=detail'))
            
            if patent_links:
                logger.info(f"      ✅ Found {len(patent_links)} result(s) for '{term}' in {field}")
            
            # First pass: collect all BR numbers and their detail URLs
            br_details_to_fetch = []
            for link in patent_links:
                try:
                    br_text = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Extract BR number: "BR 11 2024 016586 8" -> "BR112024016586"
                    br_clean = re.sub(r'\s+', '', br_text)
                    match = re.search(r'(BR[A-Z]*\d+)', br_clean)
                    
                    if match:
                        br_number = match.group(1)
                        if br_number not in self.found_brs:
                            self.found_brs.add(br_number)
                            
                            # Build full URL
                            if href.startswith('/'):
                                detail_url = f"https://busca.inpi.gov.br{href}"
                            else:
                                detail_url = href
                            
                            br_details_to_fetch.append({
                                'br_number': br_number,
                                'url': detail_url
                            })
                except Exception as e:
                    logger.warning(f"      ⚠️  Error parsing link: {e}")
                    continue
            
            # Second pass: fetch details for each BR
            for item in br_details_to_fetch:
                br_number = item['br_number']
                detail_url = item['url']
                
                try:
                    logger.info(f"         → {br_number} - Fetching details...")
                    
                    # Navigate to detail page
                    await self.page.goto(detail_url, wait_until='networkidle', timeout=60000)
                    await asyncio.sleep(2)
                    
                    # Parse complete details
# Correção para o método _parse_patent_details no inpi_crawler.py
# Substituir o método existente por esta versão corrigida

def _parse_patent_details(self, html: str) -> Dict[str, Any]:
        """
        Parse detailed patent information from INPI result page
        
        Args:
            html: HTML content of patent details page
            
        Returns:
            Dictionary with parsed patent fields
        """
        soup = BeautifulSoup(html, 'html.parser')
        data = {}
        
        try:
            # Parse basic fields with safe navigation
            rows = soup.find_all('tr')
            field_count = 0
            
            for row in rows:
                try:
                    # Find alert spans (field codes like (21), (22), etc.)
                    alert = row.find('font', class_='alerta')
                    if not alert:
                        continue
                    
                    field_code = alert.get_text(strip=True)
                    
                    # Get the value cell (next td after the label)
                    cells = row.find_all('td')
                    if len(cells) < 2:
                        continue
                    
                    value_cell = cells[1]
                    value = value_cell.get_text(strip=True)
                    
                    # Clean and store based on field code
                    if '(21)' in field_code:
                        # Application number
                        data['application_number'] = value
                        field_count += 1
                        
                    elif '(22)' in field_code:
                        # Filing date
                        data['filing_date'] = value
                        field_count += 1
                        
                    elif '(43)' in field_code:
                        # Publication date
                        data['publication_date'] = value
                        field_count += 1
                        
                    elif '(47)' in field_code:
                        # Grant date
                        data['grant_date'] = value if value != '-' else None
                        field_count += 1
                        
                    elif '(51)' in field_code:
                        # IPC classification
                        ipc_links = value_cell.find_all('a', class_='normal')
                        if ipc_links:
                            data['ipc_classification'] = [link.get_text(strip=True) for link in ipc_links]
                        else:
                            data['ipc_classification'] = [value] if value else []
                        field_count += 1
                        
                    elif '(54)' in field_code:
                        # Title
                        title_div = value_cell.find('div', id='tituloContext')
                        if title_div:
                            data['title'] = title_div.get_text(strip=True)
                        else:
                            data['title'] = value
                        field_count += 1
                        
                    elif '(57)' in field_code:
                        # Abstract
                        abstract_div = value_cell.find('div', id='resumoContext')
                        if abstract_div:
                            data['abstract'] = abstract_div.get_text(strip=True)
                        else:
                            data['abstract'] = value
                        field_count += 1
                        
                    elif '(71)' in field_code:
                        # Applicant
                        data['applicant'] = value
                        field_count += 1
                        
                    elif '(72)' in field_code:
                        # Inventors - split by '/'
                        inventors = [inv.strip() for inv in value.split('/') if inv.strip()]
                        data['inventors'] = inventors
                        field_count += 1
                        
                    elif '(74)' in field_code:
                        # Agent
                        data['agent'] = value
                        field_count += 1
                        
                    elif '(30)' in field_code:
                        # Priority data - parse table
                        priority_table = value_cell.find('table')
                        if priority_table:
                            priority_data = []
                            priority_rows = priority_table.find_all('tr')[1:]  # Skip header
                            for prow in priority_rows:
                                pcells = prow.find_all('td')
                                if len(pcells) >= 3:
                                    priority_data.append({
                                        'country': pcells[0].get_text(strip=True),
                                        'number': pcells[1].get_text(strip=True),
                                        'date': pcells[2].get_text(strip=True)
                                    })
                            if priority_data:
                                data['priority'] = priority_data
                                field_count += 1
                        
                    elif '(85)' in field_code:
                        # National phase date
                        data['national_phase_date'] = value
                        field_count += 1
                        
                    elif '(86)' in field_code:
                        # PCT data
                        pct_text = value_cell.get_text(strip=True)
                        data['pct'] = pct_text
                        field_count += 1
                        
                    elif '(87)' in field_code:
                        # WO publication
                        wo_text = value_cell.get_text(strip=True)
                        data['wo_publication'] = wo_text
                        field_count += 1
                        
                except Exception as e:
                    self.logger.debug(f"Error parsing row: {e}")
                    continue
            
            # Parse publications (despachos)
            try:
                publications = []
                pub_tables = soup.find_all('table', width='100%')
                
                for table in pub_tables:
                    # Check if this is the publications table
                    header = table.find('th', string=lambda x: x and 'Despacho' in str(x))
                    if not header:
                        continue
                    
                    pub_rows = table.find_all('tr')
                    for prow in pub_rows:
                        if prow.get('bgcolor') in ['white', '#E0E0E0']:
                            try:
                                cells = prow.find_all('td')
                                if len(cells) >= 3:
                                    rpi = cells[0].get_text(strip=True)
                                    date = cells[1].get_text(strip=True)
                                    
                                    # Dispatch code
                                    code_cell = cells[2]
                                    code_link = code_cell.find('a')
                                    code = code_link.get_text(strip=True) if code_link else code_cell.get_text(strip=True)
                                    
                                    if rpi and date and code:
                                        publications.append({
                                            'rpi': rpi,
                                            'date': date,
                                            'code': code
                                        })
                            except Exception as e:
                                self.logger.debug(f"Error parsing publication row: {e}")
                                continue
                
                if publications:
                    data['publications'] = publications
                    field_count += 1
                    
            except Exception as e:
                self.logger.debug(f"Error parsing publications section: {e}")
            
            # Parse petitions
            try:
                petitions = []
                pet_tables = soup.find_all('table', width='780px')
                
                for table in pet_tables:
                    # Check if this is the petitions table
                    header = table.find('th', string=lambda x: x and 'Serviço' in str(x))
                    if not header:
                        continue
                    
                    pet_rows = table.find_all('tr')
                    for prow in pet_rows:
                        if prow.get('bgcolor') in ['white', '#E0E0E0']:
                            try:
                                cells = prow.find_all('td')
                                if len(cells) >= 4:
                                    service = cells[0].get_text(strip=True)
                                    protocol = cells[2].get_text(strip=True)
                                    date = cells[3].get_text(strip=True)
                                    
                                    if service and protocol and date:
                                        petitions.append({
                                            'service': service,
                                            'protocol': protocol,
                                            'date': date
                                        })
                            except Exception as e:
                                self.logger.debug(f"Error parsing petition row: {e}")
                                continue
                
                if petitions:
                    data['petitions'] = petitions
                    field_count += 1
                    
            except Exception as e:
                self.logger.debug(f"Error parsing petitions section: {e}")
            
            # Parse annuities
            try:
                annuities = []
                ann_section = soup.find('label', string=lambda x: x and 'Anuidades' in str(x))
                
                if ann_section:
                    # Find annuity table
                    parent = ann_section.find_parent('div', class_='accordion-item')
                    if parent:
                        ann_table = parent.find('table')
                        if ann_table:
                            headers = ann_table.find_all('th')
                            for header in headers:
                                try:
                                    header_text = header.get_text(strip=True)
                                    if 'Anuidade' in header_text:
                                        # Extract annuity number
                                        num_match = header_text.split('ª')[0].strip() if 'ª' in header_text else None
                                        if not num_match:
                                            continue
                                        
                                        # Check for status icon
                                        status = 'unknown'
                                        status_img = header.find('img')
                                        if status_img:
                                            alt_text = status_img.get('alt', '')
                                            if 'Averbada' in alt_text or 'OK' in alt_text:
                                                status = 'paid'
                                            elif 'não Averbada' in alt_text or 'não ok' in alt_text or 'não contém' in alt_text:
                                                status = 'unpaid'
                                        
                                        annuities.append({
                                            'number': num_match,
                                            'status': status
                                        })
                                except Exception as e:
                                    self.logger.debug(f"Error parsing annuity: {e}")
                                    continue
                
                if annuities:
                    data['annuities'] = annuities
                    field_count += 1
                    
            except Exception as e:
                self.logger.debug(f"Error parsing annuities section: {e}")
            
            # Check for documents
            try:
                doc_imgs = soup.find_all('img', {'class': 'salvaDocumento'})
                if doc_imgs:
                    data['has_documents'] = True
                    field_count += 1
            except Exception as e:
                self.logger.debug(f"Error checking documents: {e}")
            
            self.logger.info(f"            ✅ Parsed {field_count} fields")
            
        except Exception as e:
            self.logger.error(f"Error in _parse_patent_details: {e}")
            self.logger.debug(f"HTML snippet: {html[:500]}")
        
        return data
    
    async def _check_session_expired(self) -> bool:
        """
        Check if INPI session has expired
        
        Returns:
            True if session expired (redirected to login)
        """
        try:
            current_url = self.page.url
            content = await self.page.content()
            
            # Session expired if:
            # - URL contains "login"
            # - Content has login form
            
            if "login" in current_url.lower() or "T_Login" in content:
                return True
            
            return False
            
        except:
            return False
    
    async def _parse_patent_details(self, br_number: str) -> Dict:
        """
        Parse COMPLETE patent details from INPI detail page
        Extracts ALL 18+ fields based on real INPI HTML structure
        
        Fields extracted:
        - (21) Patent Number
        - (22) Filing Date  
        - (43) Publication Date
        - (47) Grant Date
        - (30) Priority Data (multiple)
        - (51) IPC Codes
        - (54) Title
        - (57) Abstract
        - (71) Applicants
        - (72) Inventors
        - (74) Attorney
        - (85) National Phase Date
        - (86) PCT Number & Date
        - (87) WO Number & Date
        - Anuidades (fee schedule)
        - Despachos (RPI publications)
        - Documents & PDF links
        """
        try:
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            details = {
                'patent_number': br_number,
                'country': 'BR',
                'title': None,
                'title_original': None,
                'abstract': None,
                'applicants': [],
                'inventors': [],
                'ipc_codes': [],
                'publication_date': None,
                'filing_date': None,
                'grant_date': None,
                'priority_data': [],
                'pct_number': None,
                'pct_date': None,
                'wo_number': None,
                'wo_date': None,
                'national_phase_date': None,
                'attorney': None,
                'anuidades': [],
                'despachos': [],
                'documents': [],
                'pdf_links': [],
                'link_national': self.page.url
            }
            
            # Helper function to parse BR dates DD/MM/YYYY → YYYY-MM-DD
            def parse_br_date(date_str):
                if not date_str or date_str.strip() in ['-', '']:
                    return None
                match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_str)
                if match:
                    day, month, year = match.groups()
                    return f"{year}-{month}-{day}"
                return None
            
            # (22) Filing Date - Data do Depósito
            filing_tag = soup.find('font', class_='normal', string=re.compile(r'Data do Depósito:'))
            if filing_tag:
                tr = filing_tag.find_parent('tr')
                if tr:
                    tds = tr.find_all('td')
                    if len(tds) >= 2:
                        date_text = tds[1].get_text(strip=True)
                        details['filing_date'] = parse_br_date(date_text)
            
            # (43) Publication Date - Data da Publicação
            pub_tag = soup.find('font', class_='normal', string=re.compile(r'Data da Publicação:'))
            if pub_tag:
                tr = pub_tag.find_parent('tr')
                if tr:
                    tds = tr.find_all('td')
                    if len(tds) >= 2:
                        date_text = tds[1].get_text(strip=True)
                        details['publication_date'] = parse_br_date(date_text)
            
            # (47) Grant Date - Data da Concessão
            grant_tag = soup.find('font', class_='normal', string=re.compile(r'Data da Concessão:'))
            if grant_tag:
                tr = grant_tag.find_parent('tr')
                if tr:
                    tds = tr.find_all('td')
                    if len(tds) >= 2:
                        date_text = tds[1].get_text(strip=True)
                        if date_text and date_text != '-':
                            details['grant_date'] = parse_br_date(date_text)
            
            # (30) Priority Data - Find priority table
            priority_section = soup.find('font', class_='alerta', string=re.compile(r'\(30\)'))
            if priority_section:
                # Find next table after (30)
                current = priority_section
                for _ in range(10):  # Search up to 10 siblings
                    current = current.find_next_sibling()
                    if current and current.name == 'table':
                        rows = current.find_all('tr')[1:]  # Skip header
                        for row in rows:
                            cols = row.find_all('td')
                            if len(cols) >= 3:
                                country = cols[0].get_text(strip=True)
                                number = cols[1].get_text(strip=True)
                                date = cols[2].get_text(strip=True)
                                if country and number:
                                    details['priority_data'].append({
                                        'country': country,
                                        'number': number,
                                        'date': parse_br_date(date)
                                    })
                        break
            
            # (51) IPC Classification
            ipc_tag = soup.find('font', class_='alerta', string=re.compile(r'\(51\)'))
            if ipc_tag:
                tr = ipc_tag.find_parent('tr')
                if tr:
                    # Get all text and split by semicolon/newline
                    ipc_text = tr.get_text()
                    for code in re.split(r'[;\n]', ipc_text):
                        code = code.strip()
                        # Filter out non-IPC text
                        if code and not code.startswith('(') and not 'Classificação' in code:
                            # Match IPC pattern: letter + numbers
                            if re.match(r'[A-H]\d', code):
                                details['ipc_codes'].append(code)
            
            # (54) Title - Título
            title_tag = soup.find('font', class_='alerta', string=re.compile(r'\(54\)'))
            if title_tag:
                tr = title_tag.find_parent('tr')
                if tr:
                    # Try div first (modern INPI)
                    title_div = tr.find('div', id='tituloContext')
                    if title_div:
                        title_text = title_div.get_text(strip=True)
                    else:
                        # Fallback: next td after (54)
                        tds = tr.find_all('td')
                        if len(tds) >= 2:
                            title_text = tds[1].get_text(strip=True)
                        else:
                            title_text = tr.get_text(strip=True).replace('(54)', '').replace('Título:', '').strip()
                    
                    if title_text:
                        details['title'] = title_text
                        details['title_original'] = title_text
            
            # (57) Abstract - Resumo
            abstract_tag = soup.find('font', class_='alerta', string=re.compile(r'\(57\)'))
            if abstract_tag:
                tr = abstract_tag.find_parent('tr')
                if tr:
                    # Try div first (modern INPI)
                    abstract_div = tr.find('div', id='resumoContext')
                    if abstract_div:
                        abstract_text = abstract_div.get_text(strip=True)
                    else:
                        # Fallback: next td after (57)
                        tds = tr.find_all('td')
                        if len(tds) >= 2:
                            abstract_text = tds[1].get_text(strip=True)
                        else:
                            abstract_text = tr.get_text(strip=True).replace('(57)', '').replace('Resumo:', '').strip()
                    
                    if abstract_text:
                        details['abstract'] = abstract_text
            
            # (71) Applicants - Nome do Depositante
            applicant_tag = soup.find('font', class_='alerta', string=re.compile(r'\(71\)'))
            if applicant_tag:
                tr = applicant_tag.find_parent('tr')
                if tr:
                    applicant_text = tr.get_text(strip=True)
                    applicant_text = applicant_text.replace('(71)', '').replace('Nome do Depositante:', '').strip()
                    # Split by / for multiple applicants
                    if applicant_text:
                        details['applicants'] = [a.strip() for a in applicant_text.split('/') if a.strip()]
            
            # (72) Inventors - Nome do Inventor
            inventor_tag = soup.find('font', class_='alerta', string=re.compile(r'\(72\)'))
            if inventor_tag:
                tr = inventor_tag.find_parent('tr')
                if tr:
                    inventor_text = tr.get_text(strip=True)
                    inventor_text = inventor_text.replace('(72)', '').replace('Nome do Inventor:', '').strip()
                    # Split by / for multiple inventors
                    if inventor_text:
                        details['inventors'] = [i.strip() for i in inventor_text.split('/') if i.strip()]
            
            # (74) Attorney - Nome do Procurador
            attorney_tag = soup.find('font', class_='alerta', string=re.compile(r'\(74\)'))
            if attorney_tag:
                tr = attorney_tag.find_parent('tr')
                if tr:
                    attorney_text = tr.get_text(strip=True)
                    details['attorney'] = attorney_text.replace('(74)', '').replace('Nome do Procurador:', '').strip()
            
            # (85) National Phase Entry Date
            phase_tag = soup.find('font', class_='alerta', string=re.compile(r'\(85\)'))
            if phase_tag:
                tr = phase_tag.find_parent('tr')
                if tr:
                    phase_text = tr.get_text(strip=True)
                    date_match = re.search(r'(\d{2}/\d{2}/\d{4})', phase_text)
                    if date_match:
                        details['national_phase_date'] = parse_br_date(date_match.group(1))
            
            # (86) PCT Number and Date
            pct_tag = soup.find('font', class_='alerta', string=re.compile(r'\(86\)'))
            if pct_tag:
                tr = pct_tag.find_parent('tr')
                if tr:
                    pct_text = tr.get_text(strip=True)
                    # Extract PCT number (e.g., EP2023054766)
                    pct_match = re.search(r'([A-Z]{2}\d{10,})', pct_text)
                    if pct_match:
                        details['pct_number'] = pct_match.group(1)
                    # Extract date
                    date_match = re.search(r'Data[:\s]*(\d{2}/\d{2}/\d{4})', pct_text)
                    if date_match:
                        details['pct_date'] = parse_br_date(date_match.group(1))
            
            # (87) WO Number and Date
            wo_tag = soup.find('font', class_='alerta', string=re.compile(r'\(87\)'))
            if wo_tag:
                tr = wo_tag.find_parent('tr')
                if tr:
                    wo_text = tr.get_text(strip=True)
                    # Extract WO number (e.g., 2023/161458)
                    wo_match = re.search(r'(\d{4})/(\d{6})', wo_text)
                    if wo_match:
                        details['wo_number'] = f"WO{wo_match.group(1)}{wo_match.group(2)}"
                    # Extract date
                    date_match = re.search(r'Data[:\s]*(\d{2}/\d{2}/\d{4})', wo_text)
                    if date_match:
                        details['wo_date'] = parse_br_date(date_match.group(1))
            
            # Anuidades (Fee Schedule) - Find table with "Ordinário" and "Extraordinário"
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        fee_type = cells[0].get_text(strip=True)
                        if fee_type in ['Ordinário', 'Extraordinário']:
                            # Get date range from next cells
                            dates = []
                            for cell in cells[1:]:
                                date_text = cell.get_text(strip=True)
                                if date_text and '/' in date_text:
                                    dates.append(date_text)
                            if dates:
                                details['anuidades'].append({
                                    'type': fee_type,
                                    'dates': ' - '.join(dates)
                                })
            
            # Despachos (Publications in RPI) - Find table with RPI numbers
            pub_table = soup.find('div', id='accordionPublicacoes')
            if pub_table:
                rows = pub_table.find_all('tr', class_='normal')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        rpi = cells[0].get_text(strip=True)
                        rpi_date = cells[1].get_text(strip=True)
                        despacho_code = cells[2].get_text(strip=True)
                        
                        # Check for PDF link
                        pdf_link = None
                        if len(cells) > 3:
                            img = cells[3].find('img')
                            if img:
                                pdf_link = f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={br_number}&RPI={rpi}"
                        
                        details['despachos'].append({
                            'rpi': rpi,
                            'rpi_date': parse_br_date(rpi_date),
                            'despacho_code': despacho_code,
                            'pdf_link': pdf_link
                        })
            
            # PDF Links from Document Section
            doc_section = soup.find('div', class_='scroll-content')
            if doc_section:
                images = doc_section.find_all('img')
                for img in images:
                    img_id = img.get('id', '')
                    label = img.find_next('label')
                    if label:
                        rpi_text = label.get_text(strip=True)
                        pdf_url = f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={br_number}"
                        details['pdf_links'].append({
                            'rpi': rpi_text,
                            'document_id': img_id,
                            'pdf_url': pdf_url
                        })
            
            # Count extracted fields
            fields_count = sum([
                1 if details['title'] else 0,
                1 if details['abstract'] else 0,
                1 if details['filing_date'] else 0,
                1 if details['publication_date'] else 0,
                1 if details['applicants'] else 0,
                1 if details['inventors'] else 0,
                1 if details['ipc_codes'] else 0,
                1 if details['priority_data'] else 0,
                1 if details['pct_number'] else 0,
                1 if details['wo_number'] else 0,
                1 if details['attorney'] else 0,
                1 if details['anuidades'] else 0,
                1 if details['despachos'] else 0,
                1 if details['pdf_links'] else 0,
            ])
            
            logger.info(f"         ✅ Extracted {fields_count} fields for {br_number}")
            return details
            
        except Exception as e:
            logger.error(f"         ❌ Error parsing details for {br_number}: {e}")
            import traceback
            traceback.print_exc()
            return {'patent_number': br_number, 'country': 'BR'}
    
    async def search_by_numbers(self, br_numbers: List[str], username: str = "dnm48", password: str = "coresxxx") -> List[Dict]:
        """
        Search INPI by patent numbers to get complete details
        Used to enrich BR patents found via EPO
        """
        if not br_numbers:
            return []
        
        logger.info(f"🔍 INPI: Searching {len(br_numbers)} BRs by number")
        all_patents = []
        
        try:
            async with async_playwright() as p:
                self.browser = await p.chromium.launch(headless=True)
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
                
                # Login
                login_ok = await self._login(username, password)
                if not login_ok:
                    logger.error("❌ Login failed for number search")
                    return []
                
                # Search each BR by number - DIRECT URL approach
                for i, br_number in enumerate(br_numbers, 1):
                    try:
                        logger.info(f"   📄 {i}/{len(br_numbers)}: {br_number}")
                        
                        # DIRECT URL to patent details (skip search form!)
                        # Extract process code from BR number (remove BR prefix and format)
                        process_code = br_number.replace("BR", "").replace("BR", "")
                        
                        # Try direct detail URL first
                        detail_url = f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={process_code}"
                        
                        try:
                            await self.page.goto(detail_url, wait_until='networkidle', timeout=30000)
                            await asyncio.sleep(2)
                            
                            content = await self.page.content()
                            
                            # Check if we got the detail page
                            if "(21)" in content or "Título" in content:
                                # Success! Parse details
                                details = await self._parse_patent_details(br_number)
                                if details and details.get('patent_number'):
                                    details['source'] = 'INPI'
                                    all_patents.append(details)
                                    logger.info(f"      ✅ Direct URL worked!")
                                    await asyncio.sleep(1)
                                    continue
                        except Exception as e:
                            logger.warning(f"      ⚠️  Direct URL failed: {e}")
                        
                        # Fallback: Use search form (but with timeout!)
                        try:
                            await self.page.goto(
                                "https://busca.inpi.gov.br/pePI/jsp/patentes/PatenteSearchBasico.jsp",
                                wait_until='networkidle',
                                timeout=30000
                            )
                            await asyncio.sleep(1)
                            
                            # Fill and submit
                            await self.page.fill('input[name="ExpressaoPesquisa"]', br_number)
                            
                            # Try to select Numero option (with timeout)
                            try:
                                await self.page.select_option('select[name="Coluna"]', 'Numero', timeout=5000)
                            except:
                                # If Numero fails, try Titulo as fallback
                                try:
                                    await self.page.select_option('select[name="Coluna"]', 'Titulo', timeout=5000)
                                except:
                                    logger.warning(f"      ⚠️  Could not select search field, skipping {br_number}")
                                    continue
                            
                            await self.page.click('input[type="submit"][name="botao"]')
                            await self.page.wait_for_load_state('networkidle', timeout=30000)
                            await asyncio.sleep(2)
                            
                            content = await self.page.content()
                            
                            # If results found, click first one
                            if "Action=detail" in content:
                                soup = BeautifulSoup(content, 'html.parser')
                                first_link = soup.find('a', href=re.compile(r'Action=detail'))
                                if first_link:
                                    await self.page.click(f'a[href*="Action=detail"]', timeout=10000)
                                    await self.page.wait_for_load_state('networkidle', timeout=30000)
                                    await asyncio.sleep(2)
                                    
                                    # Parse details
                                    details = await self._parse_patent_details(br_number)
                                    if details and details.get('patent_number'):
                                        details['source'] = 'INPI'
                                        all_patents.append(details)
                        
                        except Exception as e:
                            logger.error(f"      ❌ Search form failed: {e}")
                        
                        await asyncio.sleep(2)  # Rate limit
                        
                    except Exception as e:
                        logger.error(f"      ❌ Error for {br_number}: {e}")
                        continue
                
                await self.browser.close()
                
        except Exception as e:
            logger.error(f"❌ Error in number search: {e}")
        
        logger.info(f"✅ INPI: Got details for {len(all_patents)}/{len(br_numbers)} BRs")
        return all_patents
    
    def _build_search_terms(
        self,
        molecule: str,
        brand: str,
        dev_codes: List[str],
        max_terms: int = 8
    ) -> List[str]:
        """
        Build search terms from molecule, brand, dev codes
        
        Args:
            molecule: Molecule name (in Portuguese!)
            brand: Brand name (in Portuguese!)
            dev_codes: Development codes
            max_terms: Maximum number of terms
        
        Returns:
            List of search terms
        """
        terms = set()
        
        # Add molecule and brand
        if molecule:
            terms.add(molecule.strip())
        
        if brand and brand != molecule:
            terms.add(brand.strip())
        
        # Add dev codes (limit to avoid too many searches)
        for code in dev_codes[:6]:  # Max 6 dev codes
            if code and len(code) > 2:  # Only meaningful codes
                terms.add(code.strip())
        
        # Convert to list and limit
        terms_list = list(terms)[:max_terms]
        
        return terms_list
    
    async def _translate_to_portuguese(
        self,
        molecule: str,
        brand: str,
        groq_api_key: str
    ) -> tuple:
        """
        Translate molecule and brand to Portuguese using Groq AI
        
        Args:
            molecule: Molecule name in English
            brand: Brand name in English
            groq_api_key: Groq API key
        
        Returns:
            (molecule_pt, brand_pt) tuple
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Translate molecule
                molecule_pt = await self._groq_translate(client, molecule, groq_api_key)
                
                # Translate brand if different
                if brand and brand.lower() != molecule.lower():
                    brand_pt = await self._groq_translate(client, brand, groq_api_key, is_brand=True)
                else:
                    brand_pt = molecule_pt
                
                return molecule_pt, brand_pt
                
        except Exception as e:
            logger.warning(f"   ⚠️  Translation error: {str(e)}, using original names")
            return molecule, brand
    
    async def _groq_translate(
        self,
        client: httpx.AsyncClient,
        text: str,
        groq_api_key: str,
        is_brand: bool = False
    ) -> str:
        """
        Translate text to Portuguese using Groq
        
        Args:
            client: HTTP client
            text: Text to translate
            groq_api_key: Groq API key
            is_brand: True if translating brand name (uses different prompt)
        
        Returns:
            Translated text in Portuguese
        """
        try:
            if is_brand:
                # Para marcas: buscar nome brasileiro ou manter original
                system_prompt = "You are a pharmaceutical expert. If this brand name has a Brazilian/Portuguese version, return it. Otherwise, return the ORIGINAL name unchanged. Return ONLY the name, nothing else."
                user_prompt = f"What is the Brazilian/Portuguese brand name for: {text}\nIf there is no Brazilian version, return exactly: {text}"
            else:
                # Para moléculas: traduzir normalmente
                system_prompt = "You are a pharmaceutical translator. Translate drug molecule names to Portuguese (scientific names). Return ONLY the translated name, nothing else."
                user_prompt = f"Translate this pharmaceutical molecule name to Portuguese: {text}"
            
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 50
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                translation = data["choices"][0]["message"]["content"].strip()
                
                # Remove quotes if present
                translation = translation.strip('"').strip("'")
                
                return translation
            else:
                logger.warning(f"   ⚠️  Groq API error: {response.status_code}")
                return text
                
        except Exception as e:
            logger.warning(f"   ⚠️  Groq translation error: {str(e)}")
            return text


# Singleton instance
inpi_crawler = INPICrawler()
