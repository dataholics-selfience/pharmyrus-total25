"""
Patent Consolidation Module - Pharmyrus v31.0
Unifica estrutura WO-centric sem perder dados
"""

import json
from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict


class PatentConsolidator:
    """
    Consolida resultados de busca de patentes em estrutura WO-centric
    
    Entrada: JSON do Patent Search (formato atual)
    Saída: JSON unificado com WOs como objetos principais
    """
    
    def __init__(self):
        self.version = "v31.0-UNIFIED-v2"
    
    def consolidate(self, search_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consolida dados de patentes em estrutura unificada
        
        Args:
            search_result: JSON com resultados de busca
            
        Returns:
            JSON consolidado com estrutura WO-centric
        """
        # Extrair dados base
        search_data = search_result.get('search_result', {})
        all_patents = search_data.get('patents', [])
        families = search_data.get('families', [])
        
        # 1. Extrair todos os WOs únicos
        wo_patents = self._extract_wo_patents(search_data, all_patents, families)
        
        # 2. Mapear patentes nacionais aos WOs
        nationals_by_wo = self._map_nationals_to_wo(all_patents)
        
        # 3. Consolidar estruturas
        consolidated_patents = []
        wo_without_nationals = []
        
        for wo_number, wo_data in wo_patents.items():
            nationals = nationals_by_wo.get(wo_number, [])
            
            if nationals:
                # WO com patentes nacionais
                entry = self._consolidate_patent_entry(wo_number, wo_data, nationals)
                consolidated_patents.append(entry)
            else:
                # WO sem patentes nacionais
                wo_without_nationals.append({
                    'wo_number': wo_number,
                    'wo_data': wo_data
                })
        
        # Patentes nacionais sem WO
        patents_without_wo = []
        no_wo_nationals = nationals_by_wo.get('NO_WO', [])
        for nat in no_wo_nationals:
            patents_without_wo.append({
                'jurisdiction': nat['jurisdiction'],
                'patent_data': nat['patent_data']
            })
        
        # 4. Calcular estatísticas e patent cliff
        statistics, patent_cliff_summary = self._calculate_stats(
            wo_patents, consolidated_patents, all_patents
        )
        
        # 5. Estrutura final
        output = {
            'metadata': {
                'molecule_name': search_data.get('molecule', 'Unknown'),
                'search_timestamp': search_data.get('search_timestamp'),
                'version': self.version,
                'generated_at': datetime.now().isoformat(),
                'total_wo_patents': statistics['total_wo_patents'],
                'total_national_patents': sum(
                    entry['statistics']['total_national_patents'] 
                    for entry in consolidated_patents
                ),
                'consolidation_enabled': True
            },
            
            'patent_cliff_summary': patent_cliff_summary,
            
            'consolidated_patents': sorted(
                consolidated_patents,
                key=lambda x: x['patent_cliff_impact']['earliest_expiration'] or '9999-12-31'
            ),
            
            'wo_patents_without_nationals': sorted(
                wo_without_nationals,
                key=lambda x: x['wo_number']
            ),
            
            'patents_without_wo': patents_without_wo,
            
            'statistics': statistics,
            
            # MANTER ESTRUTURA ORIGINAL PARA COMPATIBILIDADE
            'original_structure': {
                'search_result': search_data,
                'inpi_results': search_result.get('inpi_results', {}),
                'validation_report': search_result.get('validation_report', {}),
                'orange_book_entries': search_result.get('orange_book_entries', [])
            }
        }
        
        return output
    
    def _extract_wo_patents(self, search_data: Dict, all_patents: List, families: List) -> Dict[str, Dict]:
        """Extrai todos os WOs únicos de todas as fontes"""
        wo_patents = {}
        
        # 1. WOs diretos (jurisdiction == 'WO')
        wo_direct = [p for p in all_patents if p.get('jurisdiction') == 'WO']
        for wo in wo_direct:
            wo_num = wo.get('publication_number')
            if wo_num and wo_num not in wo_patents:
                wo_patents[wo_num] = {
                    'publication_number': wo_num,
                    'publication_date': wo.get('publication_date'),
                    'title': wo.get('title'),
                    'abstract': wo.get('abstract'),
                    'source': wo.get('source'),
                    'source_engine': wo.get('source_engine'),
                    'source_url': wo.get('source_url'),
                    'priority_date': wo.get('priority_date'),
                    'filing_date': wo.get('filing_date'),
                    'family_id': wo.get('family_id'),
                    'assignees': wo.get('assignees', []),
                    'inventors': wo.get('inventors', []),
                    'ipc_classifications': wo.get('ipc_classifications', []),
                    'cpc_classifications': wo.get('cpc_classifications', [])
                }
        
        # 2. WOs referenciados nas patentes
        for patent in all_patents:
            wo_related = (
                patent.get('wo_related') or 
                patent.get('wo_number') or 
                patent.get('wo_primary')
            )
            if wo_related and wo_related not in wo_patents:
                wo_patents[wo_related] = {
                    'publication_number': wo_related,
                    'publication_date': None,
                    'title': None,
                    'abstract': None,
                    'source': 'Referenced',
                    'source_engine': 'Derived from national patents',
                    'source_url': None,
                    'priority_date': None,
                    'filing_date': None,
                    'family_id': patent.get('family_id'),
                    'assignees': [],
                    'inventors': [],
                    'ipc_classifications': [],
                    'cpc_classifications': []
                }
        
        # 3. WOs de family members
        for family in families:
            members = family.get('members', [])
            for member in members:
                wo_related = (
                    member.get('wo_related') or 
                    member.get('wo_number') or 
                    member.get('wo_primary')
                )
                if wo_related and wo_related not in wo_patents:
                    wo_patents[wo_related] = {
                        'publication_number': wo_related,
                        'publication_date': None,
                        'title': member.get('title'),
                        'abstract': member.get('abstract'),
                        'source': 'Referenced',
                        'source_engine': 'Derived from family members',
                        'source_url': None,
                        'priority_date': member.get('priority_date'),
                        'filing_date': member.get('filing_date'),
                        'family_id': family.get('family_id'),
                        'assignees': member.get('assignees', []),
                        'inventors': member.get('inventors', []),
                        'ipc_classifications': member.get('ipc_classifications', []),
                        'cpc_classifications': member.get('cpc_classifications', [])
                    }
        
        return wo_patents
    
    def _map_nationals_to_wo(self, all_patents: List) -> Dict[str, List[Dict]]:
        """Mapeia patentes nacionais aos seus WOs"""
        nationals_by_wo = defaultdict(list)
        
        for patent in all_patents:
            jurisdiction = patent.get('jurisdiction')
            
            # Pular WOs (já processados separadamente)
            if jurisdiction == 'WO':
                continue
            
            # Encontrar WO relacionado (pode estar em wo_number, wo_primary ou wo_related)
            wo_related = (
                patent.get('wo_related') or 
                patent.get('wo_number') or 
                patent.get('wo_primary')
            )
            
            if wo_related:
                nationals_by_wo[wo_related].append({
                    'jurisdiction': jurisdiction,
                    'patent_data': patent
                })
            else:
                # Patente sem WO relacionado
                nationals_by_wo['NO_WO'].append({
                    'jurisdiction': jurisdiction,
                    'patent_data': patent
                })
        
        return dict(nationals_by_wo)
    
    def _consolidate_patent_entry(self, wo_number: str, wo_data: Dict, 
                                  nationals: List[Dict]) -> Dict:
        """Consolida um WO com suas patentes nacionais"""
        # Separar nacionais por jurisdição
        nationals_by_jurisdiction = defaultdict(list)
        
        for nat in nationals:
            jur = nat['jurisdiction']
            patent = nat['patent_data']
            
            # Estrutura consolidada
            entry = {
                'patent_number': patent.get('publication_number'),
                'jurisdiction': jur,
                'patent_type': patent.get('patent_type'),
                'legal_status': patent.get('legal_status'),
                
                'bibliographic_data': {
                    'title': patent.get('title'),
                    'abstract': patent.get('abstract'),
                    'assignees': patent.get('assignees', []),
                    'inventors': patent.get('inventors', []),
                    'ipc_classifications': patent.get('ipc_classifications', []),
                    'cpc_classifications': patent.get('cpc_classifications', [])
                },
                
                'dates': {
                    'priority_date': patent.get('priority_date'),
                    'filing_date': patent.get('filing_date'),
                    'publication_date': patent.get('publication_date'),
                    'grant_date': patent.get('grant_date'),
                    'expiration_date': patent.get('expiry_date')
                },
                
                'family_data': {
                    'family_id': patent.get('family_id'),
                    'family_members': patent.get('family_members', []),
                    'wo_related': patent.get('wo_related'),
                    'worldwide_applications': patent.get('worldwide_applications', [])
                },
                
                'urls': {
                    'source_url': patent.get('source_url'),
                    'link_google_patents': f"https://patents.google.com/patent/{patent.get('publication_number')}" 
                        if patent.get('publication_number') else None
                },
                
                'citations': {
                    'forward_citations': patent.get('forward_citations', 0),
                    'backward_citations': patent.get('backward_citations', 0)
                },
                
                'source_info': {
                    'source': patent.get('source'),
                    'source_engine': patent.get('source_engine')
                },
                
                'raw_data': patent.get('raw_data', {})
            }
            
            nationals_by_jurisdiction[jur].append(entry)
        
        # Calcular patent cliff
        all_expirations = []
        for jur, patents_list in nationals_by_jurisdiction.items():
            for pat in patents_list:
                exp = pat['dates']['expiration_date']
                if exp:
                    all_expirations.append(exp)
        
        earliest_expiration = min(all_expirations) if all_expirations else None
        
        # Anos até expiração
        years_until_expiration = None
        if earliest_expiration:
            try:
                exp_date = datetime.strptime(earliest_expiration[:10], '%Y-%m-%d')
                today = datetime.now()
                years_until_expiration = round((exp_date - today).days / 365.25, 2)
            except:
                pass
        
        # Estrutura final consolidada
        return {
            'wo_number': wo_number,
            'wo_data': wo_data,
            'national_patents': dict(nationals_by_jurisdiction),
            
            'patent_cliff_impact': {
                'earliest_expiration': earliest_expiration,
                'years_until_expiration': years_until_expiration,
                'jurisdictions_with_protection': list(nationals_by_jurisdiction.keys()),
                'total_national_patents': len(nationals)
            },
            
            'statistics': {
                'total_national_patents': len(nationals),
                'jurisdictions_count': len(nationals_by_jurisdiction),
                'patents_by_jurisdiction': {
                    jur: len(pats) for jur, pats in nationals_by_jurisdiction.items()
                }
            }
        }
    
    def _calculate_stats(self, wo_patents: Dict, consolidated_patents: List, 
                        all_patents: List) -> tuple:
        """Calcula estatísticas e patent cliff"""
        # Contar BRs
        br_count = sum(1 for entry in consolidated_patents 
                      if 'BR' in entry['national_patents'])
        
        # Calcular patent cliff geral
        all_expirations = []
        for entry in consolidated_patents:
            exp = entry['patent_cliff_impact']['earliest_expiration']
            if exp:
                all_expirations.append(exp)
        
        patent_cliff_summary = {
            'first_expiration': min(all_expirations) if all_expirations else None,
            'last_expiration': max(all_expirations) if all_expirations else None,
            'total_patents_with_expiration': len(all_expirations)
        }
        
        if all_expirations:
            try:
                first_exp = datetime.strptime(min(all_expirations)[:10], '%Y-%m-%d')
                today = datetime.now()
                years_to_cliff = (first_exp - today).days / 365.25
                patent_cliff_summary['years_until_cliff'] = round(years_to_cliff, 2)
                patent_cliff_summary['status'] = 'Safe (>5 years)' if years_to_cliff > 5 else 'Warning (<5 years)'
            except:
                pass
        
        statistics = {
            'total_wo_patents': len(wo_patents),
            'wo_with_national_patents': len(consolidated_patents),
            'wo_without_national_patents': len(wo_patents) - len(consolidated_patents),
            'wo_with_br_patents': br_count,
            'patents_without_wo': len([p for p in all_patents if not p.get('wo_related') and p.get('jurisdiction') != 'WO']),
            'total_unique_jurisdictions': len(set(
                jur for entry in consolidated_patents 
                for jur in entry['national_patents'].keys()
            ))
        }
        
        return statistics, patent_cliff_summary


# Função helper para uso direto
def consolidate_search_results(search_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consolida resultados de busca em estrutura unificada
    
    Args:
        search_result: JSON completo do patent search
        
    Returns:
        JSON consolidado com WO-centric structure
    """
    consolidator = PatentConsolidator()
    return consolidator.consolidate(search_result)
