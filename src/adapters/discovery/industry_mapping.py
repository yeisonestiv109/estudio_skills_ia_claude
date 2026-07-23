"""
Industry Mapping para Apollo Discovery — Mapeo inteligente de industrias target.

En lugar de buscar "empresas tech genéricas", busca industrias específicas que
tienen dolor tecnológico pero no son competidores directos de consultoras IT.

Diseño: Búsqueda escalonada que distribuye 50 empresas entre todos los sectores
target, con deduplicación automática para evitar repetición entre ejecuciones.
"""

import time
from typing import Dict, List

TARGET_INDUSTRIES_BY_CLIENT = {
    "CONSULTORA_IT": {
        "target_keywords": [
            # Retail & E-commerce (necesitan escalabilidad)
            "e-commerce", "retail", "marketplace", "fashion",

            # Fintech (regulación + performance)
            "fintech", "banking", "insurance", "payments",

            # Healthcare (compliance + integración)
            "healthcare", "telemedicine", "pharmaceuticals",

            # Logistics (optimización + tracking)
            "logistics", "transportation", "supply chain",

            # Manufacturing (IoT + automation)
            "manufacturing", "industrial", "automotive",

            # Agriculture (IoT + trazabilidad)
            "agriculture", "food processing", "agtech",

            # Energy (smart grids + monitoring)
            "energy", "utilities", "renewable energy",

            # Real Estate (PropTech)
            "real estate", "construction", "property management"
        ],

        "exclude_keywords": [
            # Competidores directos
            "consulting", "consultora", "software development",
            "IT services", "digital agency", "system integrator",

            # Entidades no-empresa
            "media", "news", "universidad", "foundation"
        ],

        # Configuración de búsqueda escalonada
        "search_config": {
            "batch_size": 12,                    # Empresas por ejecución
            "companies_per_sector": 1,           # ~50/12 = 4 empresas por sector
            "max_searches_per_sector": 3,        # Límite de búsquedas por sector
            "rate_limit_seconds": 1,             # Delay entre búsquedas
        }
    }
}

def get_target_industries(categoria_cliente: str) -> Dict:
    """
    Retorna la configuración de industrias target para un tipo de cliente.

    Args:
        categoria_cliente: Valor de CategoriaEmpresa (ej: "CONSULTORA_IT")

    Returns:
        Diccionario con target_keywords, exclude_keywords y search_config
    """
    return TARGET_INDUSTRIES_BY_CLIENT.get(categoria_cliente, {})

def get_sector_distribution(target_keywords: List[str], batch_size: int) -> Dict[str, int]:
    """
    Calcula cuántas empresas buscar por cada sector para llenar un batch.

    Args:
        target_keywords: Lista de keywords de sectores
        batch_size: Total de empresas objetivo

    Returns:
        Dict con keyword -> número de empresas a buscar
    """
    sectors_count = len(target_keywords)
    if sectors_count == 0:
        return {}

    base_per_sector = batch_size // sectors_count
    remainder = batch_size % sectors_count

    distribution = {}
    for i, keyword in enumerate(target_keywords):
        # Distribuir el remainder entre los primeros sectores
        companies_for_sector = base_per_sector + (1 if i < remainder else 0)
        distribution[keyword] = companies_for_sector

    return distribution
