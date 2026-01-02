"""
Pharmyrus v31.0 - Output Structure Integration
================================================

Estrutura Final de Output:
1. Patent Search (WO-Centric UNIFIED)
2. P&D (Market Research & Intelligence)
3. Metadata & Statistics

Zero perda de dados, formato otimizado para frontend
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict
from patent_consolidator import PatentConsolidator


class PharmyrusOutputBuilder:
    """
    Constrói output final do Pharmyrus integrando:
    - Patent Search (estrutura WO-centric unificada)
    - P&D (clinical trials, FDA, market data, etc)
    - Statistics & Validation
    """
    
    def __init__(self):
        self.consolidator = PatentConsolidator()
        self.version = "v31.0-INTEGRATED"
    
    def build_complete_output(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Constrói output completo integrado
        
        Args:
            raw_data: JSON atual do sistema (formato darolutamide-base.json)
            
        Returns:
            JSON final integrado com Patent Search unificado + P&D
        """
        
        # 1. CONSOLIDAR PATENT SEARCH
        patent_search_consolidated = self._consolidate_patent_search(raw_data)
        
        # 2. EXTRAIR P&D (sem modificações)
        pd_section = self._extract_pd_section(raw_data)
        
        # 3. METADATA & SUMMARY
        metadata = self._build_metadata(raw_data, patent_search_consolidated)
        
        # 4. STATISTICS
        statistics = self._build_statistics(raw_data, patent_search_consolidated)
        
        # 5. ESTRUTURA FINAL
        output = {
            # ============================================
            # METADATA & EXECUTIVE SUMMARY
            # ============================================
            'metadata': metadata,
            
            'executive_summary': self._build_executive_summary(
                raw_data, patent_search_consolidated, pd_section
            ),
            
            # ============================================
            # PATENT SEARCH (WO-CENTRIC UNIFIED)
            # ============================================
            'patent_search': patent_search_consolidated,
            
            # ============================================
            # P&D (MARKET RESEARCH & INTELLIGENCE)
            # ============================================
            'research_and_development': pd_section,
            
            # ============================================
            # VALIDATION & STATISTICS
            # ============================================
            'validation_report': raw_data.get('validation_report', {}),
            'statistics': statistics,
            
            # ============================================
            # EXPORT & GENERATION INFO
            # ============================================
            'generated_at': datetime.now().isoformat(),
            'export_url': raw_data.get('export_url', ''),
            'version': self.version
        }
        
        return output
    
    def _consolidate_patent_search(self, raw_data: Dict) -> Dict:
        """Consolida Patent Search em estrutura WO-centric"""
        
        # Usar consolidador para gerar estrutura unificada
        search_result = {'search_result': raw_data.get('search_result', {})}
        consolidated = self.consolidator.consolidate(search_result)
        
        # Estrutura final do Patent Search
        return {
            'metadata': consolidated['metadata'],
            
            # Patent Cliff Summary
            'patent_cliff': consolidated['patent_cliff_summary'],
            
            # Consolidated Patents (WO-centric)
            'consolidated_patents': consolidated['consolidated_patents'],
            
            # WOs sem patentes nacionais
            'wo_without_nationals': consolidated['wo_patents_without_nationals'],
            
            # Patentes sem WO
            'nationals_without_wo': consolidated.get('patents_without_wo', []),
            
            # Statistics
            'statistics': consolidated['statistics'],
            
            # INPI Results (mantém separado para fácil acesso)
            'inpi_enrichment': raw_data.get('inpi_results', []),
            
            # Search Engines Used
            'search_engines': raw_data.get('search_result', {}).get('search_engines_used', []),
            
            # Warnings & Errors
            'warnings': raw_data.get('search_result', {}).get('warnings', []),
            'errors': raw_data.get('search_result', {}).get('errors', [])
        }
    
    def _extract_pd_section(self, raw_data: Dict) -> Dict:
        """Extrai seção de P&D sem modificações"""
        
        executive = raw_data.get('executive_summary', {})
        
        return {
            # Clinical Trials
            'clinical_trials': executive.get('clinical_trials_data', {}),
            
            # FDA Data
            'fda_data': executive.get('fda_data', {}),
            
            # Orange Book
            'orange_book': raw_data.get('orange_book_entries', []),
            
            # Market Intelligence (se disponível no executive_summary)
            'market_intelligence': {
                'generic_name': executive.get('generic_name'),
                'commercial_name': executive.get('commercial_name'),
                'molecule_name': executive.get('molecule_name')
            },
            
            # Placeholder para futuras expansões
            'drugbank': None,
            'pubmed': None,
            'market_size': None,
            'competitive_landscape': None
        }
    
    def _build_metadata(self, raw_data: Dict, patent_search: Dict) -> Dict:
        """Constrói metadata consolidada"""
        
        exec_summary = raw_data.get('executive_summary', {})
        search_metadata = patent_search.get('metadata', {})
        
        return {
            'molecule_name': search_metadata.get('molecule_name', 'Unknown'),
            'commercial_name': exec_summary.get('commercial_name', 'Unknown'),
            'generic_name': exec_summary.get('generic_name', 'Unknown'),
            
            'version': self.version,
            'generated_at': datetime.now().isoformat(),
            'search_timestamp': search_metadata.get('search_timestamp'),
            
            'data_sources': {
                'patent_search': search_metadata.get('search_engines', []),
                'clinical_trials': 'ClinicalTrials.gov',
                'fda': 'FDA Orange Book',
                'inpi': 'INPI Brasil'
            },
            
            'completeness': {
                'patent_search': 'Complete',
                'clinical_trials': 'Complete' if exec_summary.get('clinical_trials_data') else 'Missing',
                'fda_data': 'Complete' if exec_summary.get('fda_data') else 'Missing',
                'market_intelligence': 'Partial'
            }
        }
    
    def _build_executive_summary(self, raw_data: Dict, 
                                 patent_search: Dict, pd_section: Dict) -> Dict:
        """Constrói executive summary consolidado"""
        
        exec_raw = raw_data.get('executive_summary', {})
        patent_stats = patent_search.get('statistics', {})
        patent_cliff = patent_search.get('patent_cliff', {})
        
        return {
            # Molecule Info
            'molecule_name': exec_raw.get('molecule_name'),
            'commercial_name': exec_raw.get('commercial_name'),
            'generic_name': exec_raw.get('generic_name'),
            
            # Patent Overview
            'patent_overview': {
                'total_wo_patents': patent_stats.get('total_wo_patents', 0),
                'total_national_patents': patent_stats.get('wo_with_national_patents', 0),
                'br_patents': patent_stats.get('wo_with_br_patents', 0),
                'jurisdictions': exec_raw.get('jurisdictions', {}),
                'patent_families': exec_raw.get('total_families', 0)
            },
            
            # Patent Cliff
            'patent_cliff': {
                'first_expiration': patent_cliff.get('first_expiration'),
                'years_until_cliff': patent_cliff.get('years_until_cliff'),
                'status': patent_cliff.get('status'),
                'risk_level': 'High' if patent_cliff.get('years_until_cliff', 999) < 3 
                             else 'Medium' if patent_cliff.get('years_until_cliff', 999) < 5 
                             else 'Low'
            },
            
            # Patent Types
            'patent_types': exec_raw.get('patent_types', {}),
            
            # Clinical Trials Summary
            'clinical_trials_summary': {
                'total_trials': pd_section['clinical_trials'].get('total_trials', 0),
                'completed': pd_section['clinical_trials'].get('completed_trials_count', 0),
                'ongoing': pd_section['clinical_trials'].get('ongoing_trials_count', 0),
                'total_enrollment': pd_section['clinical_trials'].get('total_enrollment', 0)
            },
            
            # Quality Score
            'quality_metrics': {
                'consistency_score': exec_raw.get('consistency_score', 0),
                'data_completeness': self._calculate_completeness(raw_data)
            }
        }
    
    def _build_statistics(self, raw_data: Dict, patent_search: Dict) -> Dict:
        """Constrói estatísticas consolidadas"""
        
        raw_stats = raw_data.get('statistics', {})
        patent_stats = patent_search.get('statistics', {})
        
        return {
            # Patent Statistics
            'patent_statistics': {
                'unique_patents': raw_stats.get('unique_patents', 0),
                'total_wo_patents': patent_stats.get('total_wo_patents', 0),
                'total_national_patents': sum(
                    entry['statistics']['total_national_patents']
                    for entry in patent_search.get('consolidated_patents', [])
                ),
                'jurisdictions': patent_stats.get('total_unique_jurisdictions', 0)
            },
            
            # Coverage Statistics
            'coverage': {
                'assignee_coverage': raw_stats.get('assignee_coverage_percentage', 0),
                'family_coverage': raw_stats.get('family_coverage_percentage', 0),
                'overall_score': raw_stats.get('overall_coverage_score', 0),
                'attribute_coverage': raw_stats.get('attribute_coverage', {})
            },
            
            # Top Entities
            'top_entities': {
                'assignees': raw_stats.get('top_assignees', []),
                'jurisdictions': raw_stats.get('top_jurisdictions', [])
            },
            
            # Patent Type Distribution
            'patent_type_distribution': raw_stats.get('patent_type_distribution', {}),
            
            # Data Quality
            'data_quality': {
                'patents_with_legal_status': raw_stats.get('patents_with_legal_status', 0),
                'primary_source_percentage': raw_stats.get('primary_source_percentage', 0)
            }
        }
    
    def _calculate_completeness(self, raw_data: Dict) -> float:
        """Calcula completude dos dados"""
        
        sections = [
            'search_result',
            'executive_summary',
            'validation_report',
            'statistics',
            'orange_book_entries'
        ]
        
        present = sum(1 for s in sections if raw_data.get(s))
        return round((present / len(sections)) * 100, 2)


# =============================================================================
# FUNÇÃO PRINCIPAL DE USO
# =============================================================================

def build_pharmyrus_output(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constrói output final do Pharmyrus
    
    Args:
        raw_data: JSON atual do sistema (formato darolutamide-base.json)
        
    Returns:
        JSON final integrado:
        - Patent Search (WO-centric unificado)
        - P&D (clinical trials, FDA, etc)
        - Metadata & Statistics
    
    Example:
        >>> raw = json.load(open('darolutamide-base.json'))
        >>> output = build_pharmyrus_output(raw)
        >>> json.dump(output, open('output-final.json', 'w'), indent=2)
    """
    builder = PharmyrusOutputBuilder()
    return builder.build_complete_output(raw_data)


# =============================================================================
# TESTE
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python output_builder.py <input.json> [output.json]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'pharmyrus-output-final.json'
    
    print(f"📖 Lendo {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    print("🔄 Construindo output integrado...")
    output = build_pharmyrus_output(raw_data)
    
    print(f"💾 Salvando {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*60)
    print("✅ OUTPUT FINAL GERADO!")
    print("="*60)
    print(f"📊 Molecule: {output['metadata']['molecule_name']}")
    print(f"🔬 WO Patents: {output['patent_search']['statistics']['total_wo_patents']}")
    print(f"🇧🇷 BR Patents: {output['patent_search']['statistics']['wo_with_br_patents']}")
    print(f"⏰ Patent Cliff: {output['executive_summary']['patent_cliff']['first_expiration']}")
    print(f"📈 Completeness: {output['executive_summary']['quality_metrics']['data_completeness']}%")
    print("="*60)
