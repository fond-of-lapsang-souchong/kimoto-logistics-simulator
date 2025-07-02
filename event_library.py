EVENT_LIBRARY = {
    "Kriz Yok": {"type": "none"},
    "Liman Grevi": {
        "type": "logistics", "is_geographic": True,
        "impact": {
            "otif": {"dist": "normal", "mean": -0.15, "std": 0.025}
        },
        "erp_stock_multiplier": {"categories": ['B', 'C'], "multiplier": 1.15},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Alternatif Liman ($750K)": {"cost": 750000, "mitigation_factor": 0.8, "label": "Alternatif Liman ($750K)"},
            "Hava Kargo ($2M)": {"cost": 2000000, "mitigation_factor": 0.4, "label": "Hava Kargo ($2M)"}
        }
    },
    "3PL İflası": {
        "type": "logistics", "is_geographic": True,
        "impact": {
            "otif": {"dist": "uniform", "min": -0.18, "max": -0.08},
            "satisfaction_shock": {"dist": "uniform", "min": -1.0, "max": -0.5}
        },
        "erp_stock_multiplier": {"categories": ['B', 'C'], "multiplier": 1.25},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Spot Navlun Anlaşmaları ($1.2M)": {"cost": 1200000, "mitigation_factor": 0.5, "label": "Spot Navlun Anlaşmaları ($1.2M)"}
        }
    },
    "Hammadde Tedarikçi Krizi": {
        "type": "supply", "is_geographic": True,
        "impact": {
            "uretim_kaybi": {"dist": "normal", "mean": 0.75, "std": 0.10},
            "satisfaction_shock": {"dist": "uniform", "min": -0.8, "max": -0.3}
        },
        "depends_on": "tek_kaynak_orani",
        "erp_stock_multiplier": {"categories": ['A'], "multiplier": 0.5},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Alternatif Tedarikçi ($2.5M)": {"cost": 2500000, "mitigation_factor": 0.3, "label": "Alternatif Tedarikçi ($2.5M)"}
        }
    },
    "Faiz Artışı Şoku": {
        "type": "financial", "impact": {"net_kar": -750000},
        "erp_stock_multiplier": {"categories": ['A'], "multiplier": 0.85},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Acil Maliyet Düşürme (-$200K)": {"cost": 200000, "mitigation_factor": 0.5, "label": "Acil Maliyet Düşürme (-$200K)"}
        }
    },
    "Yeni Gümrük Vergileri": {
        "type": "geopolitical", "is_geographic": True, "impact": {"net_kar": -1200000},
        "erp_stock_multiplier": {"categories": ['A'], "multiplier": 0.80},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Tedarik Zinciri Optimizasyonu (-$400K)": {"cost": 400000, "mitigation_factor": 1.0, "label": "Tedarik Zinciri Optimizasyonu (-$400K)"}
        }
    },
    "Talep Patlaması": {
        "type": "demand", "impact": {"net_kar_multiplier": 1.4, "otif": -0.05},
        "erp_stock_multiplier": {"multiplier": 0.80},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Fırsatı Değerlendir (Fazla Mesai - $500K)": {"cost": 500000, "mitigation_factor": 0.2, "label": "Fırsatı Değerlendir (Fazla Mesai - $500K)"}
        }
    },
    "Rakip Fiyat Kırması": {
        "type": "demand", "impact": {"net_kar_multiplier": 0.75},
        "erp_stock_multiplier": {"categories": ['B', 'C'], "multiplier": 1.15},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Fiyata Karşılık Ver (-%15 Kâr Marjı)": {"cost": 0, "mitigation_factor": 1.0, "net_kar_multiplier": 0.85, "label": "Fiyata Karşılık Ver (-%15 Kâr Marjı)"},
            "Marka Değeri Kampanyası ($600K)": {"cost": 600000, "mitigation_factor": 0.0, "label": "Marka Değeri Kampanyası ($600K)"}
        }
    },
    "Müşteri Güven Kaybı": {
        "type": "reputation", "impact": {"otif": -0.05, "net_kar_multiplier": 0.95},
        "erp_stock_multiplier": {"multiplier": 1.10},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "İtibar Yönetimi Kampanyası ($400K)": {"cost": 400000, "mitigation_factor": 0.0, "label": "İtibar Yönetimi Kampanyası ($400K)"}
        }
    },
    "Spot Piyasa Fiyat Artışı": {
        "type": "financial", "impact": {"net_kar": -1500000},
        "erp_stock_multiplier": {"multiplier": 0.85},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Kısa Vadeli Kontrat ($1M)": {"cost": 1000000, "mitigation_factor": 0.33, "label": "Kısa Vadeli Kontrat ($1M)"}
        }
    },
    "Stratejik İkilem (Talep & Fiyat)": {
        "type": "demand", "impact": {"net_kar_multiplier": 1.05, "otif": -0.05},
        "erp_stock_multiplier": {"multiplier": 0.90},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"}
        }
    },
    "Rakip Çekilmesi (Fırsat)": {
        "type": "demand", "impact": {"net_kar_multiplier": 1.6, "otif": -0.08},
        "erp_stock_multiplier": {"multiplier": 0.60},
        "interventions": {
            "Müdahale Yok": {"cost": 0, "mitigation_factor": 1.0, "label": "Müdahale Yok"},
            "Agresif Kapasite Artırımı ($1M)": {"cost": 1000000, "mitigation_factor": 0.5, "label": "Agresif Kapasite Artırımı ($1M)"}
        }
    }
}


DOMINO_RULES = {
    "Liman Grevi": {"triggers": "Müşteri Güven Kaybı", "delay": 1, "probability": 0.40},
    "Hammadde Tedarikçi Krizi": {"triggers": "Spot Piyasa Fiyat Artışı", "delay": 2, "probability": 0.60}
}

JURY_SCENARIOS = {
    "Kum Fırtınası": {
        "timeline": {2: "Liman Grevi", 5: "Hammadde Tedarikçi Krizi"},
        "locations": {2: "Hindistan", 5: "Hindistan"},
        "interventions": {},
        "params": { 
            'uretim_s': 'Mevcut Strateji',
            'stok_s': 'Mevcut Politika',
            'tek_kaynak_orani': 0.7, 
            'lojistik_m': 0.8,
            'tahmin_algoritmasi': 'Mevsimsel ARIMA (Basit Model)',
            'Pazar Trendleri': False,
            'Rakip Fiyatlandırma': False,
            'Makroekonomik Göstergeler': False,
            'mevsimsellik_etkisi': False,
            'ozel_sku_modu': False
        }
    },
    "Operasyonel Kâbus": {
        "timeline": {11: "3PL İflası"},
        "locations": {11: "Hindistan"},
        "interventions": {},
        "params": { 
            'uretim_s': 'Mevcut Strateji',
            'stok_s': 'Mevsimsel Stok Oluştur',
            'tek_kaynak_orani': 0.3,
            'lojistik_m': 0.8,
            'tahmin_algoritmasi': 'Gradient Boosting (ML Modeli)',
            'Pazar Trendleri': True,
            'Rakip Fiyatlandırma': False,
            'Makroekonomik Göstergeler': False,
            'mevsimsellik_etkisi': True,
            'ozel_sku_modu': False
        }
    },
    "Stratejik İkilem": {
        "timeline": {4: "Stratejik İkilem (Talep & Fiyat)"},
        "locations": {4: "Hindistan"},
        "interventions": {},
        "params": { 
            'uretim_s': 'Strateji 2: Türkiye Çevik Merkezi',
            'transport_m': 'Deniz Yolu (Ekonomik)',
            'stok_s': 'Fazla Stokları Erit',
            'tek_kaynak_orani': 0.2,
            'lojistik_m': 0.6,
            'tahmin_algoritmasi': 'Gradient Boosting (ML Modeli)',
            'Pazar Trendleri': True,
            'Rakip Fiyatlandırma': True,
            'Makroekonomik Göstergeler': True,
            'mevsimsellik_etkisi': False,
            'ozel_sku_modu': False
        }
    },
    "Büyüme Fırsatı": {
        "timeline": {3: "Rakip Çekilmesi (Fırsat)"},
        "locations": {3: "Güney Afrika"},
        "interventions": {},
        "params": { 
            'uretim_s': 'Strateji 1: G. Afrika Çevik Merkezi',
            'transport_m': 'Hava Kargo (Hızlı)',
            'stok_s': 'Kilit Müşteri Ayrıcalığı',
            'tek_kaynak_orani': 0.1,
            'lojistik_m': 0.5,
            'tahmin_algoritmasi': 'Gradient Boosting (ML Modeli)',
            'Pazar Trendleri': True,
            'Rakip Fiyatlandırma': True,
            'Makroekonomik Göstergeler': False,
            'mevsimsellik_etkisi': False,
            'ozel_sku_modu': True
        }
    }
}