"""INPI Crawler v29.1 - Parse COMPLETO de todos os campos"""

import asyncio
import logging
import httpx
import os
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

INPI_USERNAME = "dnm48"
INPI_PASSWORD = os.getenv("INPI_PASSWORD", "senha123")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


class INPICrawler:
    def __init__(self):
        self.base_url = "https://busca.inpi.gov.br/pePI"
        self.session = None
        
    async def translate_to_portuguese(self, terms: List[str]) -> List[str]:
        """Traduz termos para português via Groq"""
        if not GROQ_API_KEY:
            return terms
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{
                            "role": "user",
                            "content": f"Translate these pharmaceutical terms to Portuguese. Return ONLY the Portuguese terms, one per line, no explanations:\n" + "\n".join(terms)
                        }],
                        "temperature": 0.1
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    translated = result["choices"][0]["message"]["content"].strip().split('\n')
                    return [t.strip() for t in translated if t.strip()]
        except Exception as e:
            logger.error(f"Translation error: {e}")
        
        return terms
    
    async def login(self) -> httpx.AsyncClient:
        """Login no INPI"""
        logger.info("🔐 Fazendo login no INPI...")
        
        client = httpx.AsyncClient(timeout=180.0, follow_redirects=True)
        
        response = await client.get(f"{self.base_url}/")
        
        login_data = {
            "j_username": INPI_USERNAME,
            "j_password": INPI_PASSWORD
        }
        
        response = await client.post(
            f"{self.base_url}/j_security_check",
            data=login_data
        )
        
        if response.status_code == 200:
            logger.info("✅ Login INPI realizado!")
            return client
        else:
            raise Exception(f"Login falhou: {response.status_code}")
    
    async def search_by_term(self, term: str, field: str, client: httpx.AsyncClient) -> List[Dict]:
        """Busca por termo"""
        logger.info(f"🔍 INPI: {term} em {field}")
        
        form_data = {
            "TipoBusca": "1",
            "Pesquisar": "Pesquisar"
        }
        
        if field == "Titulo":
            form_data["Titulo"] = term
        elif field == "Resumo":
            form_data["Resumo"] = term
        elif field == "NumPedido":
            form_data["NumPedido"] = term
        
        try:
            response = await client.post(
                f"{self.base_url}/servlet/PatenteServletController",
                data=form_data
            )
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results_table = soup.find('table', class_='table1')
            
            if not results_table:
                return []
            
            patents = []
            rows = results_table.find_all('tr')[1:]
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    patent_number = cols[0].get_text(strip=True)
                    detail_link = cols[0].find('a')
                    if detail_link:
                        patents.append({
                            "patent_number": patent_number,
                            "search_term": term,
                            "search_field": field,
                            "detail_url": detail_link.get('href', '')
                        })
            
            logger.info(f"✅ {len(patents)} resultados")
            return patents
            
        except Exception as e:
            logger.error(f"Erro busca INPI: {e}")
            return []
    
    def parse_inpi_html(self, html: str, patent_number: str) -> Dict:
        """Parse HTML INPI"""
        soup = BeautifulSoup(html, 'html.parser')
        patent = {}
        
        try:
            # (54) Title
            title_tag = soup.find('font', class_='alerta', string='(54)')
            if title_tag:
                title_text = title_tag.find_parent('tr').get_text(strip=True)
                patent['title'] = title_text.replace('(54)', '').replace('Título:', '').strip()
            
            # (57) Abstract
            abstract_tag = soup.find('font', class_='alerta', string='(57)')
            if abstract_tag:
                abstract_text = abstract_tag.find_parent('tr').get_text(strip=True)
                patent['abstract'] = abstract_text.replace('(57)', '').replace('Resumo:', '').strip()
            
            # (71) Applicants
            applicant_tag = soup.find('font', class_='alerta', string='(71)')
            if applicant_tag:
                applicant_text = applicant_tag.find_parent('tr').get_text(strip=True)
                applicant_text = applicant_text.replace('(71)', '').replace('Nome do Depositante:', '').strip()
                patent['applicants'] = [applicant_text] if applicant_text else []
            
            # (72) Inventors
            inventor_tag = soup.find('font', class_='alerta', string='(72)')
            if inventor_tag:
                inventor_text = inventor_tag.find_parent('tr').get_text(strip=True)
                inventor_text = inventor_text.replace('(72)', '').replace('Nome do Inventor:', '').strip()
                patent['inventors'] = [inv.strip() for inv in inventor_text.split('/') if inv.strip()]
            
            # (74) Attorney
            attorney_tag = soup.find('font', class_='alerta', string='(74)')
            if attorney_tag:
                attorney_text = attorney_tag.find_parent('tr').get_text(strip=True)
                patent['attorney'] = attorney_text.replace('(74)', '').replace('Nome do Procurador:', '').strip()
            
            # (85) National Phase
            phase_tag = soup.find('font', class_='alerta', string='(85)')
            if phase_tag:
                phase_text = phase_tag.find_parent('tr').get_text(strip=True)
                patent['national_phase_date'] = phase_text.replace('(85)', '').replace('Início da Fase Nacional:', '').strip()
            
            # (86) PCT
            pct_tag = soup.find('font', class_='alerta', string='(86)')
            if pct_tag:
                pct_text = pct_tag.find_parent('tr').get_text(strip=True)
                pct_text = pct_text.replace('(86)', '').replace('PCT', '').strip()
                if 'Número:' in pct_text:
                    parts = pct_text.split('Data:')
                    if len(parts) == 2:
                        patent['pct_number'] = parts[0].replace('Número:', '').strip()
                        patent['pct_date'] = parts[1].strip()
            
            # (87) WO
            wo_tag = soup.find('font', class_='alerta', string='(87)')
            if wo_tag:
                wo_text = wo_tag.find_parent('tr').get_text(strip=True)
                wo_text = wo_text.replace('(87)', '').replace('W.O.', '').strip()
                if 'Número:' in wo_text:
                    parts = wo_text.split('Data:')
                    if len(parts) == 2:
                        patent['wo_number'] = parts[0].replace('Número:', '').strip()
                        patent['wo_date'] = parts[1].strip()
            
            # (51) IPC
            ipc_tag = soup.find('font', class_='alerta', string='(51)')
            if ipc_tag:
                parent = ipc_tag.find_parent('tr')
                ipc_links = parent.find_all('a', class_='normal')
                patent['ipc_codes'] = [link.get_text(strip=True).replace(';', '').strip() for link in ipc_links if link.get_text(strip=True)]
            
            # Documents
            patent['documents'] = []
            for table in soup.find_all('table'):
                header = table.find('th')
                if header and 'Documentos' in header.get_text():
                    rows = table.find_all('tr')[1:]
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 2:
                            link = cols[1].find('a')
                            if link:
                                doc_url = link.get('href', '')
                                patent['documents'].append({
                                    "type": cols[0].get_text(strip=True),
                                    "url": f"https://busca.inpi.gov.br{doc_url}" if doc_url.startswith('/') else doc_url,
                                    "title": link.get_text(strip=True)
                                })
            
            # Despachos
            patent['despachos'] = []
            for table in soup.find_all('table'):
                header = table.find('th')
                if header and 'Despachos' in header.get_text():
                    rows = table.find_all('tr')[1:]
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 3:
                            patent['despachos'].append({
                                "date": cols[0].get_text(strip=True),
                                "code": cols[1].get_text(strip=True),
                                "description": cols[2].get_text(strip=True)
                            })
            
        except Exception as e:
            logger.error(f"Parse error {patent_number}: {e}")
        
        return patent
    
    async def get_patent_details(self, patent_number: str, detail_url: str, client: httpx.AsyncClient) -> Dict:
        """Obtém detalhes"""
        logger.info(f"📄 Detalhes {patent_number}")
        
        try:
            full_url = f"{self.base_url}{detail_url}"
            response = await client.get(full_url)
            
            if response.status_code != 200:
                return {"patent_number": patent_number}
            
            patent_data = self.parse_inpi_html(response.text, patent_number)
            patent_data["patent_number"] = patent_number
            patent_data["link_national"] = full_url
            
            return patent_data
            
        except Exception as e:
            logger.error(f"Erro detalhes {patent_number}: {e}")
            return {"patent_number": patent_number}
    
    async def search_patents(self, molecule_name: str, synonyms: List[str] = None) -> List[Dict]:
        """Busca patentes no INPI"""
        all_patents = []
        client = await self.login()
        
        try:
            search_terms = [molecule_name]
            if synonyms:
                search_terms.extend(synonyms[:5])
            
            pt_terms = await self.translate_to_portuguese(search_terms)
            all_terms = list(set(search_terms + pt_terms))
            
            logger.info(f"🔍 Termos INPI: {all_terms}")
            
            for term in all_terms:
                results = await self.search_by_term(term, "Titulo", client)
                all_patents.extend(results)
                await asyncio.sleep(1)
                
                results = await self.search_by_term(term, "Resumo", client)
                all_patents.extend(results)
                await asyncio.sleep(1)
            
            unique_patents = {}
            for p in all_patents:
                pn = p["patent_number"]
                if pn not in unique_patents:
                    unique_patents[pn] = p
            
            all_patents = list(unique_patents.values())
            
            detailed_patents = []
            for i, patent in enumerate(all_patents, 1):
                logger.info(f"📄 {i}/{len(all_patents)}: {patent['patent_number']}")
                
                details = await self.get_patent_details(
                    patent["patent_number"],
                    patent["detail_url"],
                    client
                )
                
                details["search_term"] = patent["search_term"]
                details["search_field"] = patent["search_field"]
                details["source"] = "INPI"
                details["country"] = "BR"
                
                detailed_patents.append(details)
                await asyncio.sleep(2)
            
            return detailed_patents
            
        finally:
            await client.aclose()
    
    async def search_by_numbers(self, patent_numbers: List[str]) -> List[Dict]:
        """Busca por números"""
        logger.info(f"🔍 Buscando {len(patent_numbers)} BRs no INPI")
        
        client = await self.login()
        detailed_patents = []
        
        try:
            for i, number in enumerate(patent_numbers, 1):
                logger.info(f"📄 {i}/{len(patent_numbers)}: {number}")
                
                results = await self.search_by_term(number, "NumPedido", client)
                
                if results:
                    details = await self.get_patent_details(
                        results[0]["patent_number"],
                        results[0]["detail_url"],
                        client
                    )
                    
                    details["source"] = "INPI"
                    details["country"] = "BR"
                    detailed_patents.append(details)
                
                await asyncio.sleep(2)
            
            return detailed_patents
            
        finally:
            await client.aclose()


inpi_crawler = INPICrawler()
