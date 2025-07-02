import pandas as pd
import numpy as np
import random
import logging
import optuna
from datetime import timedelta

from event_library import EVENT_LIBRARY, DOMINO_RULES
from config import (CONFIG, URETIM_STRATEJILERI, STOK_STRATEJILERI,
                    MONTH_NAMES, LOCATION_COORDINATES)

logger = logging.getLogger(__name__)

def calculate_tahmin_d(params, config):
    """
    Verilen parametreler ve konfigürasyona göre talep tahmin doğruluğunu hesaplar.
    Bu fonksiyon, kod tekrarını önlemek için merkezi birim olarak kullanılır.
    """
    model_cfg = config['strategy_impacts']['tahmin_modeli']
    kpi_cfg = config['kpi_defaults']
    
    tahmin_algoritmasi = params.get('tahmin_algoritmasi', 'Mevsimsel ARIMA (Basit Model)')
    bonus = model_cfg['algoritmalar'][tahmin_algoritmasi]['bonus']
    
    for kaynak in model_cfg['veri_kaynaklari'].keys():
        if params.get(kaynak, False):
             bonus += model_cfg['veri_kaynaklari'][kaynak]['bonus']
             
    return min(0.99, kpi_cfg['talep_tahmin_dogrulugu'] + bonus)

class KimotoSimulator:
    """Tüm simülasyon mantığını, durumunu ve akışını yöneten merkezi sınıf.

    Bir KimotoSimulator nesnesi, belirli bir strateji seti (parametreler)
    için tek bir tam (genellikle 12 aylık) simülasyon çalışmasını temsil eder.
    Simülasyonun durumunu (KPI'lar, tesis verileri) ay bazında günceller,
    stratejik etkileri, krizleri ve müdahaleleri uygular.

    Attributes:
        base_data (dict): Simülasyonun başlangıç durumunu içeren veri.
        params (dict): Kullanıcı tarafından seçilen strateji parametreleri.
        config (dict): Genel uygulama yapılandırması.
        state (dict): Simülasyonun anlık durumunu tutan sözlük.
        history (list): Her ayın sonundaki durumun kaydedildiği liste.
        results_df (pd.DataFrame): Simülasyon bittiğinde oluşturulan sonuç tablosu.
        final_tesis_df (pd.DataFrame): Simülasyon sonundaki tesislerin durum tablosu.
        co2_tasarrufu (float): Simülasyon sonucunda hesaplanan CO2 tasarrufu.
    """
    def __init__(self, base_data, params, config):
        """KimotoSimulator nesnesini başlatır.

        Args:
            base_data (dict): Simülasyon için başlangıç verilerini içeren sözlük.
                              'initial_kpis' ve 'tesisler_df' anahtarlarını içermelidir.
            params (dict): Kullanıcı tarafından seçilen strateji parametrelerini
                           içeren sözlük.
            config (dict): Uygulamanın genel yapılandırma sözlüğü.
        """
        self.base_data = base_data
        self.params = params
        self.config = config
        
        self.state = {
            "kpis": self.base_data["initial_kpis"].copy(),
            "tesisler_df": self.base_data["tesisler_df"].copy(),
            "month": 0,
            "initial_investment_cost": 0
        }
        self.initial_state_after_setup = None 
        self.history = []
        self.summary = {}
        
        self.results_df = None
        self.final_tesis_df = None
        self.co2_tasarrufu = 0
        logger.info(f"KimotoSimulator başlatıldı. Parametreler: {self.params}")

    def _apply_strategic_effects(self):
        """(İÇ) Seçilen uzun vadeli stratejilerin aylık yinelenen etkilerini uygular.

        Bu metot, her simülasyon ayında çağrılır ve 3PL kullanımı, üretim
        stratejisi, stok politikası gibi kararların KPI'lar (OTIF, net kar,
        stok devir hızı vb.) üzerindeki sürekli etkilerini simülasyon
        durumuna yansıtır.
        """
        cfg_sim = self.config['simulation_parameters']
        cfg_strat = self.config['strategy_impacts']
        months_in_year = cfg_sim['months_in_year']
        
        self.state['kpis']['net_kar_aylik'] -= (cfg_strat['lojistik_3pl']['verimlilik_esigi'] - self.params['lojistik_m']) / months_in_year * cfg_strat['lojistik_3pl']['max_maliyet_artis_yillik']
        
        uretim_s_config = cfg_strat['uretim'].get(self.params['uretim_s'], {})
        self.state['kpis']['otif'] += uretim_s_config.get("monthly_otif_bonus", 0)

        if uretim_s_config.get("is_agile_hub", False):
            transport_mode = self.params.get('transport_m', 'default')
            transport_impact = cfg_strat['transport']['modes'][transport_mode]
            self.state['kpis']['otif'] += transport_impact.get('monthly_otif_bonus', 0)

        stok_s_config = cfg_strat['stok'].get(self.params['stok_s'], {})
        self.state['kpis']['otif'] += stok_s_config.get("monthly_otif_bonus", 0)
        self.state['kpis']['stok_devir_hizi'] += stok_s_config.get("monthly_turnover_bonus", 0)
        
        if self.params['stok_s'] == 'SKU Optimizasyonu':
             self.state['kpis']['musteri_memnuniyeti_skoru'] += stok_s_config.get("monthly_satisfaction_penalty", 0)

        if self.state['month'] in stok_s_config.get("setup_months", []):
            cost_per_month = stok_s_config.get("setup_cost", 0) / len(stok_s_config["setup_months"]) if stok_s_config.get("setup_months") else 0
            self.state['kpis']['net_kar_aylik'] -= cost_per_month
        elif self.state['month'] in stok_s_config.get("impact_months", []):
            self.state['kpis']['otif'] += stok_s_config.get("impact_otif_bonus", 0)

        if self.params.get('ozel_sku_modu', False):
            ozel_sku_cfg = cfg_strat['ozel_sku']
            self.state['kpis']['net_kar_aylik'] -= ozel_sku_cfg['aylik_operasyonel_ek_maliyet']
            base_monthly_profit = self.config['kpi_defaults']['net_kar_aylik']
            profit_bonus = base_monthly_profit * ozel_sku_cfg['gelir_payi'] * ozel_sku_cfg['kar_marji_bonusu']
            self.state['kpis']['net_kar_aylik'] += profit_bonus
            self.state['kpis']['stok_devir_hizi'] -= ozel_sku_cfg['stok_hizi_yavaslama_aylik']

        if self.params['mevsimsellik_etkisi'] and self.state['month'] in cfg_sim['mevsimsellik_aylari']:
            self.state['kpis']['otif'] += cfg_sim['mevsimsellik_otif_etkisi']

        noise_factor = random.uniform(0.98, 1.02)
        self.state['kpis']['net_kar_aylik'] *= noise_factor
        self.state['kpis']['otif'] *= random.uniform(0.99, 1.01)

    def _apply_event_and_intervention(self, event, intervention_name, location=None):
        """(İÇ) Belirli bir aydaki kriz olayının ve seçilen müdahalenin etkilerini uygular.

        Bu metot, bir krizin (event) KPI'lar üzerindeki doğrudan etkisini
        (örn: OTIF düşüşü, üretim kaybı) ve bu etkiyi azaltan müdahalenin
        (intervention) maliyetini ve azaltım faktörünü hesaba katar.
        Coğrafi etkileri de yönetir.

        Args:
            event (dict): `EVENT_LIBRARY`'den gelen kriz olayı sözlüğü.
            intervention_name (str): Kullanıcının kriz için seçtiği müdahalenin adı.
            location (str, optional): Krizin etkilediği coğrafi bölge.
        """
        if not event or event["type"] == "none":
            return

        geo_impact_ratio = 1.0
        is_geo_specific_production_loss = False

        if event.get("is_geographic", False) and location:
            tesis_df = self.state['tesisler_df']
            total_production = tesis_df['Fiili_Uretim_Ton'].sum()
            location_production = tesis_df[tesis_df['Ulke'] == location]['Fiili_Uretim_Ton'].sum()
            geo_impact_ratio = location_production / total_production if total_production > 0 else 0
            if event.get("impact", {}).get("uretim_kaybi"):
                is_geo_specific_production_loss = True
        
        intervention = event["interventions"][intervention_name]
        self.state['kpis']['net_kar_aylik'] -= intervention["cost"]
        if "net_kar_multiplier" in intervention:
            self.state['kpis']['net_kar_aylik'] *= intervention["net_kar_multiplier"]

        impact = event.get("impact", {})
        mitigation_factor = intervention["mitigation_factor"]

        def get_impact_value(effect):
            """Etkinin sabit mi yoksa olasılıksal mı olduğunu kontrol eder ve değeri döndürür."""
            if isinstance(effect, dict) and 'dist' in effect:
                if effect['dist'] == 'uniform':
                    return random.uniform(effect['min'], effect['max'])
                elif effect['dist'] == 'normal':
                    return random.normalvariate(effect['mean'], effect['std'])
            return effect 
        
        if "satisfaction_shock" in impact:
            value = get_impact_value(impact["satisfaction_shock"])
            self.state['kpis']['musteri_memnuniyeti_skoru'] += value * mitigation_factor
        
        if "otif" in impact:
            value = get_impact_value(impact["otif"])
            self.state['kpis']['otif'] += value * geo_impact_ratio * mitigation_factor

        if "uretim_kaybi" in impact:
            value = get_impact_value(impact["uretim_kaybi"])
            loss_factor = value * self.params['tek_kaynak_orani'] * mitigation_factor
            if is_geo_specific_production_loss:
                self.state['tesisler_df'].loc[self.state['tesisler_df']['Ulke'] == location, 'Fiili_Uretim_Ton'] *= (1 - loss_factor)
            else:
                self.state['tesisler_df']['Fiili_Uretim_Ton'] *= (1 - loss_factor)
        
        if "net_kar" in impact:
            value = get_impact_value(impact["net_kar"])
            self.state['kpis']['net_kar_aylik'] += value * geo_impact_ratio * mitigation_factor
        
        if "net_kar_multiplier" in impact:
            if event["type"] in ["demand", "reputation"]:
                self.state['kpis']['net_kar_aylik'] *= impact.get("net_kar_multiplier", 1)

    def _update_and_bound_kpis(self, previous_state):
        """(İÇ) Birbirine bağımlı KPI'ları günceller ve değerleri makul sınırlar içinde tutar.

        Örneğin, OTIF'teki bir değişimin müşteri memnuniyetine nasıl yansıyacağını
        hesaplar. Ayrıca esneklik skorunu günceller ve tüm KPI'ların
        konfigürasyonda belirtilen min/max sınırlar içinde kalmasını sağlar.

        Args:
            previous_state (dict): Aylık döngü başlamadan önceki durumu içeren sözlük.
        """
        cfg_sim = self.config['simulation_parameters']
        cfg_strat = self.config['strategy_impacts']
        self.state['kpis']['musteri_memnuniyeti_skoru'] += (self.state['kpis']['otif'] - previous_state['kpis']['otif']) * cfg_sim['otif_memnuniyet_katsayisi']
        
        if self.params.get('ozel_sku_modu', False):
            ozel_sku_cfg = cfg_strat['ozel_sku']
            if self.state['kpis']['otif'] < ozel_sku_cfg['otif_hedefi']: 
                self.state['kpis']['musteri_memnuniyeti_skoru'] += ozel_sku_cfg['memnuniyet_penaltisi_hedef_alti']
        
        cfg_thresh = self.config['simulation_thresholds']
        if self.state['kpis']['otif'] < cfg_thresh['esneklik_otif_esigi'] or self.state['kpis']['net_kar_aylik'] < cfg_thresh['esneklik_kar_esigi']: 
            self.state['kpis']['esneklik_skoru'] += cfg_sim['esneklik_azalis_puani']
        else: 
            self.state['kpis']['esneklik_skoru'] += cfg_sim['esneklik_artis_puani']
            
        kpi_limits = cfg_sim['kpi_sinirlari']
        self.state['kpis']['otif'] = max(kpi_limits['min'], min(kpi_limits['max_otif'], self.state['kpis']['otif']))
        self.state['kpis']['stok_devir_hizi'] = max(0, self.state['kpis']['stok_devir_hizi'])
        self.state['kpis']['esneklik_skoru'] = max(kpi_limits['min'], min(kpi_limits['max_esneklik'], self.state['kpis']['esneklik_skoru']))
        self.state['kpis']['musteri_memnuniyeti_skoru'] = max(kpi_limits['min'], min(kpi_limits['max_memnuniyet'], self.state['kpis']['musteri_memnuniyeti_skoru']))
        
    def _run_monthly_cycle(self, event, intervention_name, location=None):
        """(İÇ) Tek bir aylık simülasyon döngüsünü yönetir.

        Bu metot, bir ay içindeki olayların sırasını düzenler:
        1. Stratejik etkileri uygular.
        2. Kriz ve müdahale etkilerini uygular.
        3. Bağımlı KPI'ları günceller ve sınırlandırır.

        Args:
            event (dict): Ayın kriz olayı sözlüğü.
            intervention_name (str): Ayın müdahalesinin adı.
            location (str, optional): Krizin coğrafi konumu.
        """
        previous_state = {"kpis": self.state["kpis"].copy()}
        self.state['kpis']['talep_tahmin_dogrulugu'] = self.params['tahmin_d']
        self._apply_strategic_effects()
        if event and event["type"] != "none":
            event_name = next((k for k, v in EVENT_LIBRARY.items() if v == event), "Bilinmeyen Olay")
            logger.info(f"Ay {self.state['month']}: '{event_name}' olayı uygulanıyor. Lokasyon: {location}. Müdahale: {intervention_name}")
        self._apply_event_and_intervention(event, intervention_name, location)
        self._update_and_bound_kpis(previous_state)

    def _apply_initial_strategy_impacts(self):
        """(İÇ) Simülasyon başlamadan önce stratejilerin başlangıç etkilerini uygular.

        Bu metot, simülasyonun 0. ayında (başlamadan hemen önce) çalışır ve
        bazı stratejilerin getirdiği tek seferlik maliyetleri (örn: yeni tesis
        kurulum maliyeti) veya faydaları (örn: esneklik bonusu) başlangıç
        durumuna yansıtır.
        """
        uretim_cfg = self.config['strategy_impacts']['uretim']
        stok_cfg = self.config['strategy_impacts']['stok']

        uretim_s_param = self.params.get('uretim_s', URETIM_STRATEJILERI[0])
        uretim_s_config = uretim_cfg.get(uretim_s_param, {})

        if uretim_s_config.get("is_agile_hub", False):
            self.state['initial_investment_cost'] += uretim_s_config.get("initial_cost", 0)
            self.state['kpis']['esneklik_skoru'] += uretim_s_config.get("flexibility_bonus", 0)
            
            hedef_ulke_adi = uretim_s_config.get("target_country")
            if hedef_ulke_adi:
                a_kategori_hacmi = self.base_data['toplam_hacim_yillik'] * uretim_s_config.get("a_category_ratio", 0)
                hedef_tesis = self.state['tesisler_df'][self.state['tesisler_df']['Ulke'] == hedef_ulke_adi].iloc[0]
                bos_kapasite = hedef_tesis['Kapasite_Ton_Yil'] - hedef_tesis['Fiili_Uretim_Ton']
                aktarilacak_hacim = min(a_kategori_hacmi, bos_kapasite)
            
                self.state['tesisler_df'].loc[self.state['tesisler_df']['Ulke'] == 'Hindistan', 'Fiili_Uretim_Ton'] -= aktarilacak_hacim / self.config['simulation_parameters']['hindistan_tesis_sayisi']
                self.state['tesisler_df'].loc[self.state['tesisler_df']['Ulke'] == hedef_ulke_adi, 'Fiili_Uretim_Ton'] += aktarilacak_hacim

        stok_s_param = self.params.get('stok_s', STOK_STRATEJILERI[0])
        stok_s_config = stok_cfg.get(stok_s_param, {})
        
        self.state['kpis']['net_kar_aylik'] += stok_s_config.get("initial_revenue", 0)
        self.state['initial_investment_cost'] += stok_s_config.get("initial_cost", 0)
        self.state['kpis']['net_kar_aylik'] += stok_s_config.get("initial_profit_gain", 0)
        self.state['kpis']['musteri_memnuniyeti_skoru'] += stok_s_config.get("initial_satisfaction_impact", 0)

        self.initial_state_after_setup = {
            "kpis": self.state["kpis"].copy(),
            "tesisler_df": self.state["tesisler_df"].copy(),
            "month": self.state["month"]
        }

    def _calculate_co2(self):
        """(İÇ) Simülasyon sonundaki toplam CO2 emisyonunu ve başlangıca göre tasarrufu hesaplar.

        Bu fonksiyon, seçilen taşıma modunun CO2 çarpanını, SADECE bir "Çevik Merkez"
        stratejisi aktifse ve SADECE o merkezden yapılan sevkiyatlar için uygular.
        Diğer tüm sevkiyatlar standart çarpana göre hesaplanır.
        """
        self.final_tesis_df['Kullanim_Orani'] = (self.final_tesis_df['Fiili_Uretim_Ton'] / self.final_tesis_df['Kapasite_Ton_Yil']).fillna(0)
        
        final_co2 = 0
        transport_mode = self.params.get('transport_m', 'default')
        co2_multiplier = self.config['strategy_impacts']['transport']['modes'][transport_mode]['co2_multiplier']
        emisyon_katsayisi = self.config['co2_factors']['emisyon_katsayisi_ton_km']
        
        uretim_s_param = self.params.get('uretim_s', URETIM_STRATEJILERI[0])
        uretim_s_config = self.config['strategy_impacts']['uretim'].get(uretim_s_param, {})
        is_agile_hub_strategy_active = uretim_s_config.get("is_agile_hub", False)
        agile_hub_country = uretim_s_config.get("target_country") if is_agile_hub_strategy_active else None

        for _, row in self.final_tesis_df.iterrows():
            base_co2_for_plant = row['Fiili_Uretim_Ton'] * self.base_data['distance_map'][row['Ulke']] * emisyon_katsayisi
            
            if agile_hub_country and row['Ulke'] == agile_hub_country:
                final_co2 += base_co2_for_plant * co2_multiplier
            else:
                final_co2 += base_co2_for_plant * 1.0 
                
        self.co2_tasarrufu = self.base_data['mevcut_co2_emisyonu'] - final_co2

    def _calculate_final_summary(self):
        """(İÇ) Simülasyon bittikten sonra nihai özet KPI'ları hesaplar."""
        final_row = self.results_df.iloc[-1]
        total_operational_profit = self.results_df['Aylık Net Kar'].sum()
        base_annual_profit = self.base_data['initial_kpis']['net_kar_aylik'] * self.config['simulation_parameters']['months_in_year']
        
        annual_profit_change = total_operational_profit - self.state['initial_investment_cost'] - base_annual_profit

        self.summary = {
            'annual_profit_change': annual_profit_change,
            'initial_investment_cost': self.state['initial_investment_cost'],
            'final_otif': final_row['OTIF'],
            'final_flexibility': final_row['Esneklik Skoru'],
            'final_satisfaction': final_row['Müşteri Memnuniyeti'],
            'final_turnover': final_row['Stok Devir Hızı'],
            'co2_savings': self.co2_tasarrufu
        }

    def run(self, user_timeline_events, user_event_locations, interventions):
            """Tüm 12 aylık simülasyonu baştan sona çalıştırır ve sonuçları döndürür.

            Bu, sınıfın ana dışa açık metodudur. Başlangıç etkilerini uygular,
            Domino Etkisi gibi olasılıksal olayları kontrol eder, 12 aylık döngüyü
            yönetir ve son olarak sonuçları bir DataFrame ve diğer verilerle
            birlikte bir sözlük içinde döndürür.

            Args:
                user_timeline_events (dict): Kullanıcının manuel olarak seçtiği krizler.
                                         {ay: olay_adi}.
                user_event_locations (dict): Coğrafi krizlerin etkilediği yerler.
                                         {ay: lokasyon_adi}.
                interventions (dict): Kullanıcının seçtiği müdahaleler. {ay: mudahale_adi}.

            Returns:
                dict: Simülasyonun tam sonuçlarını içeren bir sözlük. Anahtarlar:
                    'results_df', 'final_tesis_df', 'initial_state', 'co2_tasarrufu'.
            """
            self._apply_initial_strategy_impacts()

            final_timeline = {}
            for month, event_name in user_timeline_events.items():
                source = "Jüri Özel" if "Jüri Özel" in event_name else "Kullanıcı"
                final_timeline[month] = {"event": event_name, "source": source}

            for month, event_details in list(final_timeline.items()):
                event_name = event_details["event"]
                if event_name in DOMINO_RULES:
                    rule = DOMINO_RULES[event_name]
                    if random.random() < rule['probability']:
                        triggered_month = month + rule["delay"]
                        if triggered_month < self.config['simulation_parameters']['months_in_year'] + 1 and triggered_month not in final_timeline:
                            final_timeline[triggered_month] = {"event": rule["triggers"], "source": "Domino Etkisi"}
                            logger.info(f"Domino etkisi tetiklendi: '{event_name}' olayı, {rule['delay']} ay sonra '{rule['triggers']}' olayını tetikledi.")
        
            for month in range(1, self.config['simulation_parameters']['months_in_year'] + 1):
                self.state['month'] = month
                event_data = final_timeline.get(month)
                event_name = event_data["event"] if event_data else "Kriz Yok"
                event_source = event_data["source"] if event_data else "Yok"
            
                event_obj = EVENT_LIBRARY.get(event_name)
                event_location = user_event_locations.get(month)
                intervention_for_month = interventions.get(month, "Müdahale Yok")
            
                self._run_monthly_cycle(event_obj, intervention_for_month, location=event_location)
            
                self.history.append({
                    "Ay": month,
                    "OTIF": self.state['kpis']['otif'],
                    "Aylık Net Kar": self.state['kpis']['net_kar_aylik'],
                    "Müşteri Memnuniyeti": self.state['kpis']['musteri_memnuniyeti_skoru'],
                    "Esneklik Skoru": self.state['kpis']['esneklik_skoru'],
                    "Stok Devir Hızı": self.state['kpis']['stok_devir_hizi'],
                    "Gerçekleşen Olay": event_name,
                    "Olay Kaynağı": event_source,
                    "Müdahale": intervention_for_month if intervention_for_month != "Müdahale Yok" else "-"
                })

            self.results_df = pd.DataFrame(self.history)
            self.final_tesis_df = self.state['tesisler_df'].copy()
            self._calculate_co2()
            self._calculate_final_summary()
            logger.info("12 aylık simülasyon döngüsü tamamlandı.")
        
            return {
                "results_df": self.results_df,
                "final_tesis_df": self.final_tesis_df,
                "initial_state": self.initial_state_after_setup,
                "co2_tasarrufu": self.co2_tasarrufu,
                "summary": self.summary
            }

# ==============================================================================
# OPTİMİZASYON, ANA AKIŞ VE MONTE CARLO FONKSİYONLARI
# ==============================================================================

def objective(trial, base_data, config, timeline, locations, interventions, optimization_goal):
    """Optuna için hedef fonksiyonu. Bir dizi parametreyle simülasyonu çalıştırır ve skoru döndürür."""
    params = {}
    model_cfg = config['strategy_impacts']['tahmin_modeli']
    
    for key, slider_config in config['ui_settings']['sliders'].items():
        params[key] = trial.suggest_float(key, slider_config['min'], slider_config['max'], step=slider_config['step'])
    
    uretim_stratejileri_list = list(config['strategy_impacts']['uretim'].keys())
    params['uretim_s'] = trial.suggest_categorical('uretim_s', uretim_stratejileri_list)
    
    if params['uretim_s'] != URETIM_STRATEJILERI[0]:
        transport_options = list(config['strategy_impacts']['transport']['modes'].keys())
        transport_options.remove('default')
        params['transport_m'] = trial.suggest_categorical('transport_m', transport_options)
    else:
        params['transport_m'] = 'default'
        
    stok_stratejileri_list = list(config['strategy_impacts']['stok'].keys())
    params['stok_s'] = trial.suggest_categorical('stok_s', stok_stratejileri_list)
    params['mevsimsellik_etkisi'] = trial.suggest_categorical('mevsimsellik_etkisi', [True, False])
    params['ozel_sku_modu'] = trial.suggest_categorical('ozel_sku_modu', [True, False])
    
    params['tahmin_algoritmasi'] = trial.suggest_categorical('tahmin_algoritmasi', list(model_cfg['algoritmalar'].keys()))
    for kaynak in model_cfg['veri_kaynaklari'].keys():
        params[kaynak] = trial.suggest_categorical(kaynak, [True, False])
    
    params['tahmin_d'] = calculate_tahmin_d(params, config)

    sim_results = trigger_single_simulation(params, base_data, timeline, locations, interventions, config)
    
    score = 0
    if optimization_goal == "Yıllık Net Kârı Maksimize Et":
        score = sim_results['results_df']['Aylık Net Kar'].sum()
    elif optimization_goal == "Final OTIF'i Maksimize Et":
        score = sim_results['results_df'].iloc[-1]['OTIF']
    elif optimization_goal == "Final Esneklik Skorunu Maksimize Et":
        score = sim_results['results_df'].iloc[-1]['Esneklik Skoru']
    elif optimization_goal == "CO2 Tasarrufunu Maksimize Et":
        score = sim_results['co2_tasarrufu']
    
    return -score if "Maksimize Et" in optimization_goal else score

def run_optimization(params, base_data, timeline, locations, interventions, config, n_trials, optimization_goal, callback_func=None):
    """Optuna optimizasyon sürecini yönetir."""
    study = optuna.create_study(direction="minimize")
    
    callbacks = [callback_func] if callback_func else []
    study.optimize(
        lambda trial: objective(trial, base_data, config, timeline, locations, interventions, optimization_goal),
        n_trials=n_trials,
        callbacks=callbacks
    )
    
    best_value = -study.best_value if "Maksimize Et" in optimization_goal and study.best_value is not None else study.best_value
    
    return study.best_params, best_value, study.trials_dataframe()

def trigger_single_simulation(params, base_data, timeline, locations, interventions, config):
    """SADECE TEK BİR simülasyonu çalıştırır ve ham sonuçları döndürür."""
    simulator = KimotoSimulator(base_data, params, config)
    simulation_results = simulator.run(timeline, locations, interventions)
    return simulation_results

def run_monte_carlo_simulation(params, base_data, timeline, locations, interventions, config, num_runs, callback_func=None):
    """
    Belirtilen senaryoyu `num_runs` kadar çalıştırır ve sonuçların detaylı dağılımını döndürür.
    """
    simulation_runs_data = []

    for i in range(num_runs):
        simulator = KimotoSimulator(base_data, params, config)
        results = simulator.run(timeline, locations, interventions)
        
        summary = results['summary']
        
        realized_events_list = [
            {"event": row["Gerçekleşen Olay"], "source": row["Olay Kaynağı"]}
            for _, row in results['results_df'].iterrows() if row["Gerçekleşen Olay"] != "Kriz Yok"
        ]

        simulation_runs_data.append({
            "run_id": i + 1,
            "annual_profits": summary['annual_profit_change'],
            "final_otifs": summary['final_otif'],
            "final_flexibility": summary['final_flexibility'],
            "final_satisfaction": summary['final_satisfaction'],
            "co2_savings": summary['co2_savings'],
            "realized_events": realized_events_list
        })
        
        if callback_func:
            callback_func(i + 1, num_runs)

    return simulation_runs_data

# ==============================================================================
# YARDIMCI, ANALİZ VE GÖRSELLEŞTİRME FONKSİYONLARI
# ==============================================================================

def calculate_risk_matrix(_base_data, _config, _params):
    """
    Farklı strateji ve kriz kombinasyonları için risk skorlarını (kâr kaybı) hesaplar.
    """
    strategies_to_test = {
        "Mevcut Strateji": {'uretim_s': URETIM_STRATEJILERI[0]},
        "G. Afrika Merkezi": {'uretim_s': URETIM_STRATEJILERI[1]},
        "Türkiye Merkezi": {'uretim_s': URETIM_STRATEJILERI[2]}
    }
    crises_to_test = ["Liman Grevi", "Hammadde Tedarikçi Krizi", "Talep Patlaması", "3PL İflası"]
    
    risk_matrix = pd.DataFrame(index=list(strategies_to_test.keys()), columns=crises_to_test, dtype=float)

    for strat_name, strat_params in strategies_to_test.items():
        temp_params = _params.copy()
        temp_params.update(strat_params)

        sim_baseline = KimotoSimulator(_base_data, temp_params, _config)
        baseline_results = sim_baseline.run(user_timeline_events={}, user_event_locations={}, interventions={})
        baseline_profit = baseline_results['results_df'].iloc[0]['Aylık Net Kar'] 

        for crisis_name in crises_to_test:
            sim_crisis = KimotoSimulator(_base_data, temp_params, _config)
            crisis_timeline = {1: crisis_name} 
            crisis_results = sim_crisis.run(user_timeline_events=crisis_timeline, user_event_locations={}, interventions={})
            crisis_profit = crisis_results['results_df'].iloc[0]['Aylık Net Kar']
            
            profit_loss = baseline_profit - crisis_profit
            risk_matrix.loc[strat_name, crisis_name] = profit_loss
            
    return risk_matrix

def generate_final_erp_data(initial_erp_df, final_kpis, params):
    """
    Simülasyon sonuçlarına ve parametrelere göre "son durum" ERP verisini üretir.
    Bu versiyon, vaka metnine dayalı, kategori öncelikli bir optimizasyon mantığı kullanır.
    """
    if initial_erp_df is None or initial_erp_df.empty:
        return pd.DataFrame()
    final_df = initial_erp_df.copy()

    final_df['Stok_Adedi'] = final_df['Stok_Adedi'].astype(float)
    
    initial_turnover = CONFIG['kpi_defaults']['stok_devir_hizi']
    final_turnover = final_kpis['Stok Devir Hızı']

    if final_turnover > 0 and abs(initial_turnover - final_turnover) > 1e-6:
        final_df['Stok_Degeri'] = final_df['Stok_Adedi'] * final_df['Birim_Maliyet']
        initial_total_stock_value = final_df['Stok_Degeri'].sum()
        target_total_stock_value = initial_total_stock_value * (initial_turnover / final_turnover)

        value_change = initial_total_stock_value - target_total_stock_value

        reduction_priority = ['B', 'C', 'A']
        increase_priority = ['A', 'C', 'B']

        if value_change > 0:
            for category in reduction_priority:
                if value_change <= 0:
                    break
                category_mask = final_df['Kategori'] == category
                category_current_value = final_df.loc[category_mask, 'Stok_Degeri'].sum()
                if category_current_value > 0:
                    reduction_from_this_category = min(value_change, category_current_value * 0.90)
                    reduction_ratio = 1 - (reduction_from_this_category / category_current_value)
                    final_df.loc[category_mask, 'Stok_Adedi'] *= reduction_ratio
                    value_change -= reduction_from_this_category
        elif value_change < 0: 
            value_to_increase = abs(value_change)
            for category in increase_priority:
                if value_to_increase <= 0:
                    break
                category_mask = final_df['Kategori'] == category
                category_current_value = final_df.loc[category_mask, 'Stok_Degeri'].sum()
                if category_current_value > 0:
                    increase_to_this_category = min(value_to_increase, category_current_value)
                    increase_ratio = 1 + (increase_to_this_category / category_current_value)
                    final_df.loc[category_mask, 'Stok_Adedi'] *= increase_ratio
                    value_to_increase -= increase_to_this_category

    if 'Stok_Degeri' in final_df.columns:
        final_df = final_df.drop(columns=['Stok_Degeri'])

    stok_s = params.get('stok_s')
    if stok_s == 'Fazla Stokları Erit':
        final_df.loc[final_df['Yavas_Hareket'] == True, 'Stok_Adedi'] *= 0.20
    elif stok_s == 'SKU Optimizasyonu':
        final_df.loc[final_df['Yavas_Hareket'] == True, 'Stok_Adedi'] = 0
    elif stok_s == 'Kilit Müşteri Ayrıcalığı':
        final_df.loc[final_df['Musteri_Ozel'] == True, 'Stok_Adedi'] *= 1.20
        final_df.loc[final_df['Musteri_Ozel'] == False, 'Stok_Adedi'] *= 0.90

    olay_listesi = final_kpis.get('Gerçekleşen Olaylar_Listesi', [])
    for olay_adi in olay_listesi:
        event_config = EVENT_LIBRARY.get(olay_adi, {})
        erp_impact = event_config.get('erp_stock_multiplier')
        if erp_impact:
            multiplier = erp_impact.get('multiplier', 1.0)
            categories = erp_impact.get('categories')
            if categories:
                final_df.loc[final_df['Kategori'].isin(categories), 'Stok_Adedi'] *= multiplier
            else:
                final_df['Stok_Adedi'] *= multiplier

    final_df['Stok_Adedi'] = final_df['Stok_Adedi'].round().astype(int).clip(lower=0)
    return final_df

def analyze_stock_and_demand_risk(df, risk_threshold=1.25):
    """Verilen ERP verisini analiz ederek stok/talep risklerini hesaplar."""
    if df is None or df.empty: return None
    analysis_df = df.copy(); epsilon = 1e-6
    analysis_df['Stok_Karsilama_Orani'] = analysis_df['Stok_Adedi'] / (analysis_df['Talep_Tahmini'] + epsilon)
    yetersiz_stok_df = analysis_df[analysis_df['Stok_Karsilama_Orani'] < 1.0].copy()
    yetersiz_stok_sku_sayisi = len(yetersiz_stok_df)
    yetersiz_stok_df['Eksik_Talep_Adedi'] = yetersiz_stok_df['Talep_Tahmini'] - yetersiz_stok_df['Stok_Adedi']
    yetersiz_stok_df['Kaybedilen_Ciro'] = yetersiz_stok_df['Eksik_Talep_Adedi'] * yetersiz_stok_df['Birim_Fiyat']
    toplam_kaybedilen_ciro = yetersiz_stok_df['Kaybedilen_Ciro'].sum()
    fazla_stok_df = analysis_df[analysis_df['Stok_Karsilama_Orani'] > risk_threshold].copy()
    fazla_stok_sku_sayisi = len(fazla_stok_df)
    fazla_stok_df['Fazla_Stok_Adedi'] = fazla_stok_df['Stok_Adedi'] - (fazla_stok_df['Talep_Tahmini'] * risk_threshold)
    fazla_stok_df['Atil_Sermaye'] = fazla_stok_df['Fazla_Stok_Adedi'] * fazla_stok_df['Birim_Maliyet']
    toplam_atil_sermaye = fazla_stok_df['Atil_Sermaye'].sum()
    top_yetersiz_df = yetersiz_stok_df.sort_values('Kaybedilen_Ciro', ascending=False).head(5)[['SKU', 'Kategori', 'Stok_Adedi', 'Talep_Tahmini', 'Kaybedilen_Ciro']]
    top_fazla_df = fazla_stok_df.sort_values('Atil_Sermaye', ascending=False).head(5)[['SKU', 'Kategori', 'Stok_Adedi', 'Talep_Tahmini', 'Atil_Sermaye']]
    return {"yetersiz_stok_sku_sayisi": yetersiz_stok_sku_sayisi, "toplam_kaybedilen_ciro": toplam_kaybedilen_ciro, "fazla_stok_sku_sayisi": fazla_stok_sku_sayisi, "toplam_atil_sermaye": toplam_atil_sermaye, "top_yetersiz_df": top_yetersiz_df, "top_fazla_df": top_fazla_df}

def perform_abc_analysis(df):
    """
    Verilen ERP DataFrame'i üzerinde ABC (Pareto) analizi yapar.
    Bu versiyon, ciro hesaplamasını Talep Tahmini yerine, simülasyonun bir sonucu olan
    Stok Adedi'ne dayandırarak analizin dinamik olmasını sağlar.
    """
    if df is None or df.empty or 'Stok_Adedi' not in df.columns or 'Birim_Fiyat' not in df.columns:
        return None, None
    
    abc_df = df.copy()

    abc_df['Ciro'] = abc_df['Stok_Adedi'] * abc_df['Birim_Fiyat']

    abc_df = abc_df[abc_df['Ciro'] > 0]
    
    if abc_df.empty:
        return None, None

    abc_df = abc_df.sort_values(by='Ciro', ascending=False)
    
    total_ciro = abc_df['Ciro'].sum()
    if total_ciro == 0: return None, None

    abc_df['Kumulatif_Ciro'] = abc_df['Ciro'].cumsum()
    abc_df['Kumulatif_Yuzde'] = (abc_df['Kumulatif_Ciro'] / total_ciro) * 100
    
    def assign_abc_category(percentage):
        if percentage <= 80: return 'A'
        elif percentage <= 95: return 'B'
        else: return 'C'
        
    abc_df['ABC_Kategori'] = abc_df['Kumulatif_Yuzde'].apply(assign_abc_category)
    
    summary = abc_df.groupby('ABC_Kategori').agg(
        SKU_Sayisi=('SKU', 'count'),
        Ciro_Toplami=('Ciro', 'sum')
    ).reset_index()
    
    total_sku_count = summary['SKU_Sayisi'].sum()
    if total_sku_count == 0: return abc_df, None

    summary['SKU_Yuzdesi'] = (summary['SKU_Sayisi'] / total_sku_count) * 100
    summary['Ciro_Yuzdesi'] = (summary['Ciro_Toplami'] / total_ciro) * 100
    
    return abc_df, summary.sort_values(by='ABC_Kategori')

def analyze_warehouse_feasibility(final_erp_data, config):
    """
    Simülasyon sonrası envanterin vaka metnindeki depo kapasitelerine sığıp sığmadığını analiz eder.
    """
    if final_erp_data is None or final_erp_data.empty:
        return {"kullanim_orani": 0, "fark_ton": 0, "status": "Veri Yok"}

    try:
        total_stock_units = final_erp_data['Stok_Adedi'].sum()
        ton_per_unit = config.get('physical_factors', {}).get('avg_ton_per_sku_unit', 0.015)
        total_capacity_tons = config.get('warehouse_capacities', {}).get('Toplam', 43000)

        total_stock_tonnage = total_stock_units * ton_per_unit

        if total_capacity_tons == 0:
            return {"kullanim_orani": 0, "fark_ton": total_stock_tonnage, "status": "Kapasite Tanımsız"}

        kullanim_orani = total_stock_tonnage / total_capacity_tons
        fark_ton = total_stock_tonnage - total_capacity_tons
        status = "Yeterli" if fark_ton <= 0 else "Yetersiz"

        return {
            "kullanim_orani": kullanim_orani,
            "fark_ton": fark_ton,
            "status": status,
            "gereken_hacim_ton": total_stock_tonnage,
            "toplam_kapasite_ton": total_capacity_tons
        }
    except Exception as e:
        logger.error(f"Depo fizibilite analizinde hata: {e}")
        return {"kullanim_orani": 0, "fark_ton": 0, "status": "Hesaplama Hatası"}
    
def analyze_stock_composition_by_category(final_erp_data, config):
    """
    Gereken toplam stok hacminin ürün kategorilerine göre (A, B, C)
    dağılımını ton cinsinden hesaplar.
    """
    if final_erp_data is None or final_erp_data.empty:
        return {}

    ton_per_unit = config.get('physical_factors', {}).get('avg_ton_per_sku_unit', 0.015)
    
    composition = (final_erp_data.groupby('Kategori')['Stok_Adedi'].sum() * ton_per_unit).to_dict()
    
    return composition

def calculate_crisis_impact_comparison(params_main, params_compare, base_data, config):
    """
    İki farklı strateji setini, belirli krizler karşısındaki finansal
    dayanıklılıkları açısından karşılaştırır.
    """
    crises_to_test = ["Liman Grevi", "Hammadde Tedarikçi Krizi", "Talep Patlaması", "3PL İflası"]
    comparison_results = []

    for strategy_name, params in [("Ana Strateji", params_main), ("Karşılaştırma Stratejisi", params_compare)]:
        sim_baseline = KimotoSimulator(base_data, params, config)
        baseline_results = sim_baseline.run({}, {}, {})
        baseline_profit = baseline_results['results_df'].iloc[0]['Aylık Net Kar']

        for crisis_name in crises_to_test:
            sim_crisis = KimotoSimulator(base_data, params, config)
            crisis_timeline = {1: crisis_name}
            crisis_location = {1: "Hindistan"} if EVENT_LIBRARY[crisis_name].get("is_geographic") else {}
            
            crisis_results = sim_crisis.run(crisis_timeline, crisis_location, {})
            crisis_profit = crisis_results['results_df'].iloc[0]['Aylık Net Kar']
            
            profit_loss = baseline_profit - crisis_profit
            
            comparison_results.append({
                "Strateji": strategy_name,
                "Kriz Senaryosu": crisis_name,
                "Aylık Kâr Kaybı ($)": profit_loss
            })

    return pd.DataFrame(comparison_results)