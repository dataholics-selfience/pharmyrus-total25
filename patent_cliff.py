# Correção para patent_cliff.py - melhorar performance e evitar travamentos

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set
from collections import defaultdict

def group_patent_families_optimized(patents: List[Dict]) -> List[Dict]:
    """
    Optimized family grouping - avoid O(n²) comparisons
    """
    logging.info("👨‍👩‍👧‍👦 Grouping patent families...")
    
    # Build indexes for fast lookup
    families_by_wo = {}  # wo_number -> family
    families_by_priority = defaultdict(list)  # priority_key -> families
    families_by_title = defaultdict(list)  # normalized_title -> families
    all_families = []
    
    for patent in patents:
        # Extract key identifiers
        wo_num = patent.get('wo_number') or patent.get('publication_number', '')
        priorities = patent.get('priority_numbers', [])
        title = patent.get('title', '').lower().strip()[:50]  # First 50 chars normalized
        
        # Try to find existing family
        existing_family = None
        
        # 1. Check by WO number (fastest)
        if wo_num and wo_num in families_by_wo:
            existing_family = families_by_wo[wo_num]
        
        # 2. Check by priority numbers
        if not existing_family and priorities:
            for priority in priorities[:3]:  # Check first 3 priorities only
                priority_key = priority.get('number', '')
                if priority_key:
                    matching_families = families_by_priority.get(priority_key, [])
                    if matching_families:
                        existing_family = matching_families[0]
                        break
        
        # 3. Check by title similarity (last resort, only if title is substantial)
        if not existing_family and title and len(title) > 20:
            matching_families = families_by_title.get(title, [])
            if matching_families:
                existing_family = matching_families[0]
        
        # Add to existing family or create new one
        if existing_family:
            existing_family['members'].append(patent)
            
            # Update indexes with new patent info
            if wo_num and wo_num not in families_by_wo:
                families_by_wo[wo_num] = existing_family
            for priority in priorities[:3]:
                pkey = priority.get('number', '')
                if pkey and existing_family not in families_by_priority[pkey]:
                    families_by_priority[pkey].append(existing_family)
        else:
            # Create new family
            new_family = {
                'family_id': f"FAM_{len(all_families) + 1}",
                'members': [patent]
            }
            all_families.append(new_family)
            
            # Add to indexes
            if wo_num:
                families_by_wo[wo_num] = new_family
            for priority in priorities[:3]:
                pkey = priority.get('number', '')
                if pkey:
                    families_by_priority[pkey].append(new_family)
            if title and len(title) > 20:
                families_by_title[title].append(new_family)
    
    logging.info(f"   ✅ Created {len(all_families)} patent families")
    return all_families


def calculate_patent_cliff_optimized(patents: List[Dict]) -> Dict[str, Any]:
    """
    Optimized patent cliff calculation with timeout protection
    """
    logging.info("📊 Calculating Patent Cliff...")
    
    # Quick validation
    if not patents:
        logging.warning("   ⚠️  No patents to analyze")
        return _empty_cliff_result()
    
    start_time = datetime.now()
    timeout_seconds = 30  # Max 30 seconds for this calculation
    
    try:
        # Group families (optimized)
        families = group_patent_families_optimized(patents)
        
        if (datetime.now() - start_time).seconds > timeout_seconds:
            logging.warning("   ⏱️  Timeout in family grouping")
            return _empty_cliff_result()
        
        # Find expiration dates (simplified)
        expirations_by_year = defaultdict(list)
        earliest_expiry = None
        latest_expiry = None
        
        for family in families:
            # Take first valid expiration date from family
            family_expiry = None
            
            for member in family['members'][:5]:  # Check max 5 members
                exp_date = _extract_expiration_date(member)
                if exp_date:
                    family_expiry = exp_date
                    break
            
            if family_expiry:
                year = family_expiry.year
                expirations_by_year[year].append({
                    'family_id': family['family_id'],
                    'date': family_expiry.isoformat(),
                    'patent_count': len(family['members'])
                })
                
                if not earliest_expiry or family_expiry < earliest_expiry:
                    earliest_expiry = family_expiry
                if not latest_expiry or family_expiry > latest_expiry:
                    latest_expiry = family_expiry
            
            # Timeout check
            if (datetime.now() - start_time).seconds > timeout_seconds:
                logging.warning("   ⏱️  Timeout in expiration calculation")
                break
        
        # Build timeline (simplified)
        timeline = []
        if expirations_by_year:
            sorted_years = sorted(expirations_by_year.keys())
            for year in sorted_years[:20]:  # Max 20 years
                timeline.append({
                    'year': year,
                    'families_expiring': len(expirations_by_year[year]),
                    'patents_expiring': sum(e['patent_count'] for e in expirations_by_year[year]),
                    'expirations': expirations_by_year[year][:10]  # Max 10 per year
                })
        
        # Calculate summary
        total_families = len(families)
        families_with_expiry = len([f for f in families if any(_extract_expiration_date(m) for m in f['members'][:5])])
        
        result = {
            'summary': {
                'total_patent_families': total_families,
                'families_with_known_expiry': families_with_expiry,
                'earliest_expiry': earliest_expiry.isoformat() if earliest_expiry else None,
                'latest_expiry': latest_expiry.isoformat() if latest_expiry else None,
                'analysis_years': len(timeline)
            },
            'timeline': timeline,
            'families': [
                {
                    'family_id': f['family_id'],
                    'member_count': len(f['members']),
                    'countries': list(set(m.get('country', 'Unknown') for m in f['members'][:10]))
                }
                for f in families[:50]  # Max 50 families in response
            ]
        }
        
        elapsed = (datetime.now() - start_time).seconds
        logging.info(f"   ✅ Patent cliff calculated in {elapsed}s")
        
        return result
        
    except Exception as e:
        logging.error(f"   ❌ Error calculating patent cliff: {e}")
        return _empty_cliff_result()


def _extract_expiration_date(patent: Dict) -> datetime:
    """Extract expiration date from patent (simplified)"""
    try:
        # Try filing date + 20 years
        filing_date = patent.get('filing_date') or patent.get('application_date')
        if filing_date:
            if isinstance(filing_date, str):
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y%m%d']:
                    try:
                        dt = datetime.strptime(filing_date, fmt)
                        return dt + timedelta(days=20*365)
                    except:
                        continue
        
        # Try explicit expiration date
        exp_date = patent.get('expiration_date') or patent.get('expiry_date')
        if exp_date and isinstance(exp_date, str):
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y%m%d']:
                try:
                    return datetime.strptime(exp_date, fmt)
                except:
                    continue
        
        return None
    except:
        return None


def _empty_cliff_result() -> Dict[str, Any]:
    """Return empty result structure"""
    return {
        'summary': {
            'total_patent_families': 0,
            'families_with_known_expiry': 0,
            'earliest_expiry': None,
            'latest_expiry': None,
            'analysis_years': 0
        },
        'timeline': [],
        'families': []
    }


# Export main function
calculate_patent_cliff = calculate_patent_cliff_optimized
