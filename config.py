CONFIG = {
    "kpi_defaults": { "otif": 0.85, "musteri_memnuniyeti_skoru": 7.5, "net_kar_aylik": (800_000_000 * 0.10) / 12, "esneklik_skoru": 4.0, "stok_devir_hizi": 3.0, "talep_tahmin_dogrulugu": 0.55, "naive_forecast_mae": 0.45, },
    "financial_impact_factors": {
        "target_otif": 0.95, "otif_penalty_ratio": 0.005, "slow_stock_ratio": 0.15,
        "annual_holding_cost_ratio": 0.20, "annual_revenue": 800_000_000, "total_inventory_value": 187_000_000
    },
    "ccc_factors": { "dso_days": 45, "dpo_days": 30 },
    "warehouse_capacities": { "Hindistan": 25000, "Güney Afrika": 6000, "Türkiye": 12000, "Toplam": 43000 },
    "physical_factors": { "avg_ton_per_sku_unit": 0.015 },
    "strategy_impacts": {
        "lojistik_3pl": {"max_maliyet_artis_yillik": 1_000_000, "verimlilik_esigi": 0.80},
        "uretim": {
            'Mevcut Strateji': {"is_agile_hub": False},
            'Strateji 1: G. Afrika Çevik Merkezi': {
                "is_agile_hub": True, "initial_cost": 400000, "monthly_otif_bonus": 0.02 / 12,
                "target_country": "Güney Afrika", "flexibility_bonus": 1.0, "a_category_ratio": 0.40
            },
            'Strateji 2: Türkiye Çevik Merkezi': {
                "is_agile_hub": True, "initial_cost": 300000, "monthly_otif_bonus": 0.015 / 12,
                "target_country": "Türkiye", "flexibility_bonus": 1.0, "a_category_ratio": 0.40
            }
        },
        "stok": {
            'Mevcut Politika': {},
            'Fazla Stokları Erit': {
                "initial_revenue": 2_000_000, "monthly_otif_bonus": 0.001, "monthly_turnover_bonus": 0.5 / 12
            },
            'Mevsimsel Stok Oluştur': {
                "setup_cost": 500000, "setup_months": [8, 9, 10],
                "impact_months": [11, 12, 1, 2], "impact_otif_bonus": 0.02
            },
            'SKU Optimizasyonu': {
                "initial_profit_gain": 150000, "initial_satisfaction_impact": -0.2,
                "monthly_satisfaction_penalty": -0.05, "monthly_otif_bonus": 0.001,
                "monthly_turnover_bonus": 0.1 / 12
            },
            'Kilit Müşteri Ayrıcalığı': {
                "initial_cost": 300000, "initial_satisfaction_impact": 0.4, "monthly_otif_bonus": 0.025 / 12
            }
        },
        "transport": { "modes": {
            "Hava Kargo (Hızlı)": {"co2_multiplier": 5.0, "monthly_otif_bonus": 0.025 / 12},
            "Deniz Yolu (Ekonomik)": {"co2_multiplier": 0.8, "monthly_otif_bonus": -0.01 / 12},
            "default": {"co2_multiplier": 1.0, "monthly_otif_bonus": 0}
        }},
        "ozel_sku": { "aylik_operasyonel_ek_maliyet": 350000, "gelir_payi": 0.40, "kar_marji_bonusu": 0.15, "stok_hizi_yavaslama_aylik": 0.02, "otif_hedefi": 0.97, "memnuniyet_penaltisi_hedef_alti": -0.25 },
        "tahmin_modeli": { "veri_kaynaklari": { "Pazar Trendleri": {"bonus": 0.10, "label": "Pazar Trendleri Verisi"}, "Rakip Fiyatlandırma": {"bonus": 0.08, "label": "Rakip Fiyatlandırma Verisi"}, "Makroekonomik Göstergeler": {"bonus": 0.07, "label": "Makroekonomik Göstergeler"} }, "algoritmalar": { "Mevsimsel ARIMA (Basit Model)": {"bonus": 0.0}, "Gradient Boosting (ML Modeli)": {"bonus": 0.10} } }
    },
    "simulation_parameters": { "months_in_year": 12, "hindistan_tesis_sayisi": 3, "mevsimsellik_otif_etkisi": -0.05, "mevsimsellik_aylari": [11, 12, 1], "kpi_sinirlari": {"min": 0.0, "max_otif": 1.0, "max_memnuniyet": 10.0, "max_esneklik": 10.0}, "esneklik_artis_puani": 0.1, "esneklik_azalis_puani": -0.5, "otif_memnuniyet_katsayisi": 2.0 },
    "co2_factors": { "hindistan_mesafe_km": 3000, "g_afrika_mesafe_km": 8000, "turkiye_mesafe_km": 1500, "emisyon_katsayisi_ton_km": 0.0005, },
    "simulation_thresholds": { "esneklik_otif_esigi": 0.80, "esneklik_kar_esigi": 1_500_000, },
    "stakeholder_analysis_thresholds": { "otif_baski_esigi": 0.90, "stok_hizi_baski_esigi": 3.0, "esneklik_kriz_esigi": 5.0 },
    "ui_settings": { "targets": {"otif": 0.95, "tasarruf": 5_000_000, "co2": 15000, "esneklik": 10.0, "stok_hizi": 4.0}, "sliders": { "tek_kaynak_orani": {"label": "Tek Kaynaktan Tedarik Oranı", "min": 0.0, "max": 1.0, "default": 0.3, "step": 0.05}, "lojistik_m": {"label": "Lojistik Dış Kaynak (3PL) Oranı", "min": 0.40, "max": 0.80, "default": 0.80, "step": 0.01}, }}
}

URETIM_STRATEJILERI = list(CONFIG['strategy_impacts']['uretim'].keys())
STOK_STRATEJILERI = list(CONFIG['strategy_impacts']['stok'].keys())

MONTH_NAMES = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
LOCATION_COORDINATES = { "Hindistan": {"lat": 20.5937, "lon": 78.9629}, "Güney Afrika": {"lat": -30.5595, "lon": 22.9375}, "Türkiye": {"lat": 38.9637, "lon": 35.2433} }
