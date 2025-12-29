"""
INPI (Brazil) Patent Crawler
Searches and retrieves patent data from Brazilian patent office
"""

import logging
import time
import os
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class INPICrawler:
    """Crawler for INPI Brazilian patent database"""
    
    def __init__(self):
        self.base_url = "https://busca.inpi.gov.br/pePI"
        self.session = self._create_session()
        self.logger = logger
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.inpi_password = os.getenv('INPI_PASSWORD', '')
        
    def _create_session(self) -> requests.Session:
        """Create requests session with retries"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def translate_to_portuguese(self, text: str) -> Optional[str]:
        """
        Translate text to Portuguese using Groq API
        
        Args:
            text: Text to translate
            
        Returns:
            Translated text or None if translation fails
        """
        if not self.groq_api_key:
            self.logger.debug("No GROQ_API_KEY, skipping translation")
            return None
            
        try:
            import httpx
            
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a translator. Translate the given pharmaceutical/chemical term to Brazilian Portuguese. Return ONLY the translation, nothing else."
                        },
                        {
                            "role": "user",
                            "content": f"Translate to Portuguese: {text}"
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 50
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                translation = result['choices'][0]['message']['content'].strip()
                self.logger.info(f"   ✅ Translations:")
                self.logger.info(f"      Molecule: {text} → {translation}")
                return translation
            else:
                self.logger.debug(f"Translation API error: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.debug(f"Translation failed: {e}")
            return None
    
    def _login(self) -> bool:
        """
        Login to INPI system
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            # Get login page
            login_url = f"{self.base_url}/jsp/Login.jsp"
            response = self.session.get(login_url, timeout=30)
            
            if response.status_code != 200:
                self.logger.warning(f"Failed to load login page: {response.status_code}")
                return False
            
            # Submit login form
            login_data = {
                'login': 'PUBLICO',
                'senha': self.inpi_password,
                'action': 'login'
            }
            
            response = self.session.post(
                f"{self.base_url}/servlet/LoginController",
                data=login_data,
                timeout=30
            )
            
            if 'Base_pesquisa.jsp' in response.url or response.status_code == 200:
                self.logger.info("   ✅ INPI login successful")
                return True
            else:
                self.logger.warning("   ⚠️  INPI login may have failed")
                return True  # Continue anyway
                
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False
    
    def search(self, query: str, field: str = 'Titulo') -> List[Dict[str, Any]]:
        """
        Search INPI database
        
        Args:
            query: Search query
            field: Search field (Titulo, Resumo, etc.)
            
        Returns:
            List of patent result dictionaries
        """
        try:
            # Login first
            if not self._login():
                self.logger.warning("   ⚠️  Proceeding without login")
            
            # Navigate to search page
            search_url = f"{self.base_url}/jsp/patentes/PatenteSearchBasico.jsp"
            response = self.session.get(search_url, timeout=30)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to load search page: {response.status_code}")
                return []
            
            self.logger.info("   📄 Patent search page loaded")
            
            # Submit search
            search_data = {
                'Pesquisa': query,
                'RadionButton': field,
                'action': 'Pesquisar'
            }
            
            response = self.session.post(
                f"{self.base_url}/servlet/PatenteServletController",
                data=search_data,
                timeout=30
            )
            
            if response.status_code != 200:
                self.logger.error(f"Search failed: {response.status_code}")
                return []
            
            # Parse results
            results = self._parse_search_results(response.text)
            
            if results:
                self.logger.info(f"      ✅ Found {len(results)} result(s) for '{query}' in {field}")
            else:
                self.logger.info(f"      ⚠️  No results for '{query}' in {field}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return []
    
    def _parse_search_results(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse search results page
        
        Args:
            html: HTML content of search results
            
        Returns:
            List of result dictionaries with patent numbers
        """
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        try:
            # Find all result rows
            rows = soup.find_all('tr')
            
            for row in rows:
                # Look for patent numbers (marked with class 'marcador')
                patent_num_elem = row.find('font', class_='marcador')
                if patent_num_elem:
                    patent_num = patent_num_elem.get_text(strip=True)
                    
                    # Clean patent number
                    patent_num = patent_num.replace(' ', '')
                    
                    results.append({
                        'patent_number': patent_num,
                        'source': 'INPI'
                    })
            
        except Exception as e:
            self.logger.error(f"Error parsing search results: {e}")
        
        return results
    
    def get_patent_details(self, patent_number: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a patent
        
        Args:
            patent_number: Patent number to retrieve
            
        Returns:
            Dictionary with patent details or None
        """
        try:
            self.logger.info(f"         → {patent_number} - Fetching details...")
            
            # Request patent details
            details_url = f"{self.base_url}/servlet/PatenteServletController"
            data = {
                'Action': 'detail',
                'CodPedido': patent_number,
                'QueryParameter': patent_number
            }
            
            response = self.session.post(details_url, data=data, timeout=30)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to fetch details: {response.status_code}")
                return None
            
            # Parse details
            details = self._parse_patent_details(response.text)
            
            if details:
                details['patent_number'] = patent_number
                details['source'] = 'INPI'
                details['country'] = 'BR'
            
            return details
            
        except Exception as e:
            self.logger.error(f"         ❌ Error parsing details for {patent_number}: {e}")
            return None
    
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
    
    def search_molecule(self, molecule_name: str, synonyms: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search for patents related to a molecule
        
        Args:
            molecule_name: Main molecule name
            synonyms: List of alternative names/synonyms
            
        Returns:
            List of patent dictionaries
        """
        all_results = []
        search_terms = [molecule_name]
        
        # Translate main name
        pt_name = self.translate_to_portuguese(molecule_name)
        if pt_name and pt_name.lower() != molecule_name.lower():
            search_terms.append(pt_name)
        
        # Add synonyms
        if synonyms:
            search_terms.extend(synonyms[:5])  # Limit to 5 synonyms
        
        # Search in both Title and Abstract
        search_count = 0
        for i, term in enumerate(search_terms[:8], 1):  # Max 8 searches
            search_count += 1
            self.logger.info(f"   🔍 INPI search {i}/{min(len(search_terms), 8)}: '{term}'")
            
            # Search in title
            results = self.search(term, field='Titulo')
            
            # Get details for each result
            for result in results[:5]:  # Limit to 5 results per search
                patent_num = result.get('patent_number')
                if patent_num:
                    details = self.get_patent_details(patent_num)
                    if details:
                        all_results.append(details)
            
            # Search in abstract
            results = self.search(term, field='Resumo')
            
            # Get details for each result
            for result in results[:3]:  # Limit to 3 from abstract
                patent_num = result.get('patent_number')
                if patent_num:
                    # Check if not already added
                    if not any(p.get('patent_number') == patent_num for p in all_results):
                        details = self.get_patent_details(patent_num)
                        if details:
                            all_results.append(details)
            
            # Rate limiting
            time.sleep(1)
        
        return all_results


# Create singleton instance
inpi_crawler = INPICrawler()
