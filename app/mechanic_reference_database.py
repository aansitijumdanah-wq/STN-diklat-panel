"""
Mechanic Reference Database - Common specs & procedures untuk garage Indonesia
Ini adalah fallback knowledge ketika dokumentasi spesifik tidak tersedia

ENGINES, VALVE CLEARANCES, COMMON PROCEDURES, DLL.
"""

# ============================================================================
# VALVE CLEARANCE SPECIFICATIONS (Most Common Queries)
# ============================================================================

VALVE_CLEARANCE_SPECS = {
    # Toyota 2NR Series
    '2nr': {
        'engine_full_name': 'Toyota 2NR-FE',
        'vehicle_models': ['Avanza', 'Xenia', 'Daihatsu Move'],
        'displacement': '1496cc',
        'inlet_cold': {'mm_range': '0.15-0.25', 'typical': 0.20},
        'exhaust_cold': {'mm_range': '0.25-0.35', 'typical': 0.30},
        'notes': 'Cold measurement saat engine sudah dingin minimal 3 jam',
        'procedure': 'Lepas cylinder head cover, kerjakan saat engine cold, gunakan feeler gauge'
    },
    '1nr': {
        'engine_full_name': 'Daihatsu/Toyota 1NR-FE',
        'vehicle_models': ['Terios T3', 'Gran Max', 'Taruna CX'],
        'displacement': '1298cc',
        'inlet_cold': {'mm_range': '0.15-0.25', 'typical': 0.20},
        'exhaust_cold': {'mm_range': '0.25-0.35', 'typical': 0.30},
        'notes': 'Sering di-swap dengan 2NR specifications sama',
        'procedure': 'Cek saat engine benar-benar cold (minimal 3 jam sejak mati)'
    },
    '3nr': {
        'engine_full_name': 'Daihatsu 3NR-FE',
        'vehicle_models': ['Terios LSX', 'Charade'],
        'displacement': '1495cc',
        'inlet_cold': {'mm_range': '0.20-0.30', 'typical': 0.25},
        'exhaust_cold': {'mm_range': '0.30-0.40', 'typical': 0.35},
        'notes': 'Clearance lebih besar dari 2NR',
        'procedure': 'Engine harus dingin, perhatikan exhaust clearance lebih besar'
    },
    # Honda Series
    '4g15': {
        'engine_full_name': 'Mitsubishi 4G15 (Dohc)',
        'vehicle_models': ['Mirage', 'Lancer'],
        'displacement': '1499cc',
        'inlet_cold': {'mm_range': '0.10-0.20', 'typical': 0.15},
        'exhaust_cold': {'mm_range': '0.20-0.30', 'typical': 0.25},
        'notes': '4G15 DOHC punya adjustment yang tidak perlu shim, semi-auto',
        'procedure': 'Some models ada hydraulic adjuster, cek manual'
    },
    '4a90': {
        'engine_full_name': 'Toyota 4A-90FE (4AFE)',
        'vehicle_models': ['Corolla, Starlet'],
        'displacement': '1839cc',
        'inlet_warm': {'mm_range': '0.05-0.15', 'typical': 0.10},
        'exhaust_warm': {'mm_range': '0.15-0.25', 'typical': 0.20},
        'notes': 'Cold vs warm - cek manual spesifik mana yang digunakan',
        'procedure': 'Perhatian: spec ini saat engine warm/operational'
    },
    # Suzuki Series
    'f10a': {
        'engine_full_name': 'Suzuki F10A (3-Cylinder)',
        'vehicle_models': ['Carry/Futura 1000cc'],
        'displacement': '993cc',
        'inlet_cold': {'mm_range': '0.15-0.25', 'typical': 0.20},
        'exhaust_cold': {'mm_range': '0.25-0.35', 'typical': 0.30},
        'notes': '3 cylinder - saat cold',
        'procedure': 'Gunakan shim & bucket adjuster'
    },
}

# ============================================================================
# COMMON PROCEDURES & TROUBLESHOOTING
# ============================================================================

COMMON_PROCEDURES = {
    'valve_clearance_check': {
        'title': 'Cara Check & Adjust Valve Clearance',
        'tools_required': [
            'Feeler gauge set (0.1-1.0mm)',
            'Screwdriver set',
            'Socket & wrench set',
            'Service manual (WAJIB)',
            'Straightedge / ruler'
        ],
        'safety': [
            'Engine HARUS dalam keadaan cold (tunggu minimal 3 jam)',
            'Pastikan engine off dan kunci pada OFF',
            'Disconnect battery terminal (-)',
            'Timing mark harus di TDC (Top Dead Center)'
        ],
        'estimated_time': '30-45 menit per cylinder head',
        'procedure_steps': [
            '1. Lepas cylinder head cover dan gasket (hati-hati)',
            '2. Cari TDC #1 cylinder (align timing marks)',
            '3. Gunakan feeler gauge antara cam lobe & rocker arm',
            '4. Jika ada clearance buruk: adjust screw / ganti shim',
            '5. Turn crankshaft ke cylinder berikutnya, ulangi'
        ],
        'notes': [
            'Jangan force feeler gauge - harus smooth resistance',
            'Turut-turutan paling penting untuk DOHC/SOHC',
            'Double-check spesifikasi di manual sebelum adjust',
            'Kalo sudah adjust, cek lagi semuanya'
        ]
    },
    'engine_rough_idle': {
        'title': 'Diagnosis: Engine Rough Idle (Mesin Kecil-Kecilan)',
        'possible_causes': [
            {
                'cause': 'Valve clearance tidak sesuai spec',
                'probability': '25%',
                'how_to_check': 'Check clearance seperti di atas, harus persis spec'
            },
            {
                'cause': 'Spark plug rusak / fouled',
                'probability': '20%',
                'how_to_check': 'Lepas semua spark plug, lihat warna (hitam = kaya, putih = lean)'
            },
            {
                'cause': 'Ignition timing off',
                'probability': '15%',
                'how_to_check': 'Gunakan timing light, compare dengan mark di crankshaft'
            },
            {
                'cause': 'Idle air control valve (IACV) kotor',
                'probability': '20%',
                'how_to_check': 'Lepas IACV, bersihkan dengan carburetor cleaner, check pintle gerakan'
            },
            {
                'cause': 'Vacuum leak',
                'probability': '10%',
                'how_to_check': 'Cek semua vacuum hose, sebut jika ada yang retak/loose'
            },
            {
                'cause': 'Injector performance issue (fuel injection)',
                'probability': '10%',
                'how_to_check': 'Check dan clean injectors, test spray pattern'
            }
        ],
        'diagnosis_procedure': [
            'Coba mula dari paling likely cause (valve clearance)',
            'Jangan langsung ganti suku cadang - diagnosis dulu',
            'Gunakan process of elimination'
        ],
        'estimated_time': '1-2 jam diagnosis, waktu perbaikan tergantung cause'
    },
    'carburetor_tune': {
        'title': 'Carburetor Tuning untuk Performa Optimal',
        'tools_required': [
            'Screwdriver (Phillips & flathead)',
            'Carburetor cleaner',
            'Wrench/socket untuk mounting bolts',
            'Feeler gauge (jika ada)'
        ],
        'key_adjustment_points': [
            {
                'name': 'Air Screw (AFR - Air Fuel Ratio)',
                'location': 'Di sisi carburetor, bisa ada 1-2 screw',
                'procedure': 'Putar fully in (hati-hati jangan force), kemudian tarik keluar 1.5 turns (starting point)',
                'fine_tuning': 'Jika kurang responsive: tarik keluar 0.25 turn, test RPM'
            },
            {
                'name': 'Idle Screw',
                'location': 'Di sisi bawah atau samping',
                'procedure': 'Putar untuk achieve smooth idling (~700 rpm)',
                'check': 'RPM harus constant, tidak naik-turun'
            },
            {
                'name': 'Mixture Screw (jika ada)',
                'location': 'Berbeda per model',
                'procedure': 'Adjust untuk smooth acceleration, tidak hesitation',
                'warning': 'Jangan hanya main-main, perhatikan exhaust smoke'
            }
        ],
        'verification': [
            'Idle RPM: Should be 700-900 rpm (cek spesifikasi)',
            'Acceleration: Harus smooth, tidak hesitate',
            'No stalling: Throttle blip harus stabil',
            'Exhaust: Black smoke (rich) atau white (lean)?'
        ]
    }
}

# ============================================================================
# ENGINE QUICK REFERENCE
# ============================================================================

ENGINE_QUICK_REFERENCE = {
    'toyota_2nrfe': {
        'common_issues': ['Valve clearance out of spec', 'Carbon buildup', 'Spark plug fouling'],
        'maintenance_interval': '40,000 km - valve clearance check',
        'oil_capacity': '3.0L',
        'spark_plug': 'Denso K20PR-U11',
        'valve_clearance': 'Inlet: 0.20mm, Exhaust: 0.30mm',
        'timing_belt': 'Yes - replace 80,000 km',
        'fuel_type': 'RON 88 minimum'
    },
    'daihatsu_1nrfe': {
        'common_issues': ['Valve clearance spec variation', 'Carbon'],
        'maintenance_interval': '40,000 km',
        'oil_capacity': '2.8L',
        'spark_plug': 'Denso K20PR-U11',
        'valve_clearance': 'Inlet: 0.20mm, Exhaust: 0.30mm',
        'timing_belt': 'Yes - 80,000 km',
        'fuel_type': 'RON 88 minimum'
    }
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_valve_clearance_spec(engine_code: str):
    """
    Get valve clearance specification untuk engine code
    
    Args:
        engine_code: e.g., '2nr', '1nr', '4g15'
    
    Returns:
        Dictionary dengan spec atau None
    """
    engine_code_lower = engine_code.lower().strip()
    return VALVE_CLEARANCE_SPECS.get(engine_code_lower)


def find_similar_engines(engine_code: str, similarity_threshold=0.7):
    """
    Find similar engines jika exact match tidak ditemukan
    Useful untuk "2NR-related" engines
    """
    engine_code_lower = engine_code.lower().strip()
    
    # Hardcoded similarity mapping
    similar_map = {
        '2nr': ['1nr', '3nr'],
        '1nr': ['2nr', '3nr'],
        '3nr': ['1nr', '2nr'],
        '4g15': ['4g13', '4g92'],
    }
    
    return similar_map.get(engine_code_lower, [])


def format_valve_clearance_response(engine_code: str) -> str:
    """
    Format comprehensive valve clearance answer untuk engine
    """
    spec = get_valve_clearance_spec(engine_code)
    
    if not spec:
        similar = find_similar_engines(engine_code)
        response = f"""❌ Spesifikasi untuk {engine_code} tidak ditemukan dalam database.

🔍 ENGINE SERUPA yang mungkin relevan:
"""
        for similar_engine in similar:
            similar_spec = get_valve_clearance_spec(similar_engine)
            if similar_spec:
                response += f"\n• {similar_engine.upper()}: Inlet {similar_spec['inlet_cold']['typical']}mm, Exhaust {similar_spec['exhaust_cold']['typical']}mm"
        
        response += """

💡 REKOMENDASI:
1. Confirm engine code dari block dengan pemilik/dokumen
2. Buka service manual - WAJIB punya untuk akurasi
3. Hubungi dealer resmi untuk spesifikasi exact
"""
        return response
    
    # Format specification
    response = f"""✅ SPESIFIKASI VALVE CLEARANCE: {spec['engine_full_name']}

📋 INFO ENGINE:
• Nama: {spec['engine_full_name']}
• Displacement: {spec['displacement']}
• Digunakan di: {', '.join(spec['vehicle_models'])}

🎯 CLEARANCE SPECIFICATION (Saat Engine COLD):
• INLET: {spec['inlet_cold']['mm_range']}mm (typical: {spec['inlet_cold']['typical']}mm)
• EXHAUST: {spec['exhaust_cold']['mm_range']}mm (typical: {spec['exhaust_cold']['typical']}mm)

⚠️  PENTING:
• Measurement harus saat engine DINGIN (minimal 3 jam tidak dinyalakan)
• Gunakan feeler gauge, jangan tebak
• Ikuti prosedur TDC (Top Dead Center) dengan teliti
• Double-check dengan service manual resmi

📖 CATATAN TAMBAHAN:
{spec['notes']}

🔧 PROSEDUR ADJUST:
{spec['procedure']}

⏱️  Waktu estimasi: 30-45 menit per cylinder head
"""
    return response


def get_procedure_response(procedure_type: str) -> str:
    """
    Get formatted procedure response
    """
    procedure = COMMON_PROCEDURES.get(procedure_type)
    
    if not procedure:
        return "Procedure tidak ditemukan dalam database."
    
    response = f"""🔧 PROSEDUR: {procedure['title']}

⏱️  ESTIMASI WAKTU: {procedure['estimated_time']}

🛠️  TOOLS YANG DIPERLUKAN:
"""
    for tool in procedure['tools_required']:
        response += f"  • {tool}\n"
    
    if 'safety' in procedure:
        response += f"\n⚠️  SAFETY PRECAUTIONS (WAJIB):\n"
        for safety in procedure['safety']:
            response += f"  • {safety}\n"
    
    if 'procedure_steps' in procedure:
        response += f"\n📋 LANGKAH-LANGKAH:\n"
        for step in procedure['procedure_steps']:
            response += f"  {step}\n"
    
    if 'notes' in procedure:
        response += f"\n💡 NOTES & TIPS:\n"
        for note in procedure['notes']:
            response += f"  • {note}\n"
    
    return response


# ============================================================================
# MAIN EXPORT
# ============================================================================

__all__ = [
    'get_valve_clearance_spec',
    'find_similar_engines',
    'format_valve_clearance_response',
    'get_procedure_response',
    'VALVE_CLEARANCE_SPECS',
    'COMMON_PROCEDURES',
    'ENGINE_QUICK_REFERENCE'
]
