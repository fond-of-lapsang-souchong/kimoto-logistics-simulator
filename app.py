import streamlit as st
import datetime
import time
import pandas as pd
import logging

from erp_module import load_erp_data
from config import CONFIG

from simulation_engine import (KimotoSimulator, trigger_single_simulation,
                               generate_final_erp_data, run_monte_carlo_simulation,
                               run_optimization, calculate_tahmin_d, analyze_warehouse_feasibility,
                               analyze_stock_composition_by_category)

from ui_manager import UIManager
from event_library import JURY_SCENARIOS

def apply_custom_styles():
    """Uygulama geneli için özel CSS stillerini uygular."""
    custom_css = """
        <style>
            /* Ana gövde başlıkları */
            .main .block-container h1 { font-size: 2.2rem !important; }
            .main .block-container h2 { font-size: 1.8rem !important; }
            .main .block-container h3 { font-size: 1.5rem !important; }
            
            /* Kontrol paneli bölüm başlıkları (altı çizgili) */
            .main .block-container h6 { 
                font-size: 1.0rem !important; 
                font-weight: 600; 
                color: #cdd3dc; 
                border-bottom: 1px solid #31333f;
                padding-bottom: 0.5rem;
                margin-bottom: 1rem;
            }

            /* Kenar çubuğu elemanları */
            [data-testid="stSidebar"] h1 { /* 'Kimoto Solutions' */
                font-size: 1.4rem !important;
                font-weight: 600;
            }
            [data-testid="stSidebar"] h2 { /* 'Karar Destek Sistemi' */
                font-size: 1.1rem !important;
                color: #aab0b6;
                font-weight: 400;
                margin-top: -0.8rem;
                margin-bottom: 0.5rem;
            }
            [data-testid="stSidebar"] hr { /* Ayraç çizgileri */
                margin: 0.75rem 0 !important;
                background-color: #31333f;
                height: 1px;
                border: none;
            }
            [data-testid="stSidebar"] .stRadio > label[data-baseweb="radio"] { /* Navigasyon */
                padding: 0.3rem 0;
            }
            [data-testid="stSidebar"] p, [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {
                font-size: 0.9rem !important;
                line-height: 1.4;
            }

            .sidebar-header {
                display: flex;
                align-items: center;
                margin-bottom: 0.5rem;
            }
            .sidebar-icon {
                font-size: 1.2rem;
                margin-right: 0.5rem;
            }
            .sidebar-title {
                font-size: 1.0rem;
                font-weight: 600;
                color: #cdd3dc;
            }
            .sidebar-caption {
                font-size: 0.85rem !important;
                color: #aab0b6;
                margin-bottom: 0.5rem !important;
                line-height: 1.4;
            }
            .dashboard-info-box {
                background-color: rgba(40, 81, 130, 0.15);
                border-left: 5px solid #00b0f0;
                padding: 1rem 1.2rem;
                margin-bottom: 1rem;
                border-radius: 5px;
                font-size: 0.95rem;
            }

            /* Metrik kutuları */
            div[data-testid="stMetricLabel"] > div { font-size: 0.9rem !important; line-height: 1.3; }
            div[data-testid="stMetricValue"] { font-size: 1.7rem !important; }
            
            /* Radio button ve checkbox etiketleri */
            label[data-baseweb="radio"] span, .st-checkbox label span { font-size: 0.95rem !important; }

            /* Ana 'Simülasyonu Başlat' butonu (Modernleştirilmiş) */
            div[data-testid="stButton"] > button[kind="primary"] { 
                font-size: 1.05rem !important; 
                padding: 0.6rem 1.2rem !important;
                box-shadow: 0 4px 14px 0 rgba(255, 75, 75, 0.39);
                transition: all 0.2s ease-in-out;
            }
            div[data-testid="stButton"] > button[kind="primary"]:hover {
                transform: translateY(-1px);
                box-shadow: 0 6px 20px 0 rgba(255, 75, 75, 0.45);
            }

            /* Expander başlığı */
            summary[aria-expanded] p { font-size: 1.0rem !important; font-weight: 500; }

            /* "Başlangıç Rehberi" kutusu */
            div[data-testid="stInfo"] { font-size: 0.95rem !important; text-align: left !important; padding: 1.1rem !important; }
            div[data-testid="stInfo"] p { margin-bottom: 0.6rem !important; }

            .guidance-pill {
                display: inline-block;
                background-color: #31333f;
                color: #cdd3dc;
                padding: 0.2em 0.6em;
                border-radius: 1rem;
                font-size: 0.9em;
                font-weight: 600;
                border: 1px solid #4a4c54;
                vertical-align: middle;
                margin: 0 0.2em;
            }

            .guidance-pill-main {
                display: inline-block;
                background-color: #ff4b4b;
                color: white;
                padding: 0.2em 0.6em;
                border-radius: 6px; /* Daha köşeli, butona benzer */
                font-size: 0.9em;
                font-weight: 600;
                border: 1px solid #ff7b7b;
                vertical-align: middle;
                margin: 0 0.2em;
                box-shadow: 0 2px 5px 0 rgba(255, 75, 75, 0.2);
            }
        </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

def setup_logging():
    """Tüm uygulama için genel logging yapılandırmasını kurar.

    Bu fonksiyon, logların hem bir dosyaya (`simulation.log`) hem de
    konsola yazılmasını sağlar. Uygulama başlatıldığında bir kez çağrılır.
    """
    log_formatter = logging.Formatter("[%(asctime)s] - %(levelname)s - %(message)s")
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler("simulation.log", mode='w')
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

setup_logging()
logger = logging.getLogger(__name__)

@st.cache_data
def get_initial_data(_config):
    """Simülasyon için temel başlangıç verilerini oluşturur ve önbelleğe alır.

    Bu fonksiyon, tesis bilgileri, yıllık hacim, CO2 emisyonları ve
    temel KPI'lar gibi simülasyonun başlangıç durumunu temsil eden
    verileri hesaplar. Streamlit'in cache mekanizması sayesinde sadece
    bir kez çalıştırılır.

    Args:
        _config (dict): Uygulamanın genel yapılandırma sözlüğü.

    Returns:
        dict: Simülasyonun başlangıç durumunu içeren bir sözlük.
              Anahtarlar: 'tesisler_df', 'toplam_hacim_yillik',
              'distance_map', 'mevcut_co2_emisyonu', 'initial_kpis'.
    """
    logger.info("Başlangıç verileri oluşturuluyor (get_initial_data).")
    tesis_data = pd.DataFrame({'Tesis Yeri': ['Hindistan 1', 'Hindistan 2', 'Hindistan 3', 'Güney Afrika', 'Türkiye'], 'Ulke': ['Hindistan', 'Hindistan', 'Hindistan', 'Güney Afrika', 'Türkiye'],'Kapasite_Ton_Yil': [100000/3, 100000/3, 100000/3, 50000, 40000], 'Kullanim_Orani': [0.75, 0.75, 0.75, 0.42, 0.60]})
    tesis_data['Fiili_Uretim_Ton'] = tesis_data['Kapasite_Ton_Yil'] * tesis_data['Kullanim_Orani']
    distance_map = {'Hindistan': _config['co2_factors']['hindistan_mesafe_km'], 'Güney Afrika': _config['co2_factors']['g_afrika_mesafe_km'], 'Türkiye': _config['co2_factors']['turkiye_mesafe_km']}
    mevcut_co2_emisyonu = sum(tesis_data['Fiili_Uretim_Ton'] * tesis_data['Ulke'].map(distance_map)) * _config['co2_factors']['emisyon_katsayisi_ton_km']
    return {'tesisler_df': tesis_data, 'toplam_hacim_yillik': 120000,'distance_map': distance_map, 'mevcut_co2_emisyonu': mevcut_co2_emisyonu,'initial_kpis': _config['kpi_defaults']}

def manage_erp_data_sourcing():
    """Kenar çubuğundaki ERP veri çekme arayüzünü ve mantığını yönetir.

    Kullanıcının bir butona tıklayarak ERP verisini (prototipte bir CSV dosyası)
    yüklemesini sağlar. Yüklenen veriyi ve son senkronizasyon zamanını
    Streamlit'in session state'inde saklar.
    """
    if 'last_sync_time' not in st.session_state: st.session_state.last_sync_time = None
    if 'erp_data' not in st.session_state: st.session_state.erp_data = None
    
    st.sidebar.subheader("Sistem Durumu ve Entegrasyon")
    st.sidebar.caption("Bu prototip, harici bir CSV dosyasını okuyarak ERP entegrasyon yeteneğini simüle eder.")
    if st.sidebar.button("🔄 ERP'den Canlı Veri Çek"):
        with st.spinner("ERP sisteminden veri çekiliyor..."):
            erp_data = load_erp_data()
            if erp_data is not None and not erp_data.empty:
                st.session_state.last_sync_time = datetime.datetime.now()
                st.session_state.erp_data = erp_data
                st.sidebar.success(f"{len(erp_data)} SKU verisi başarıyla çekildi.")
                time.sleep(1)
                st.rerun()
    
    if st.session_state.last_sync_time:
        st.sidebar.success(f"🔗 ERP Bağlantısı: Aktif")
        st.sidebar.caption(f"Son Veri Çekme: {st.session_state.last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if st.session_state.erp_data is not None:
             st.sidebar.metric("Yönetilen SKU Sayısı", len(st.session_state.erp_data))
    else: 
        st.sidebar.warning("🔗 ERP Bağlantısı: Pasif")

def process_and_store_single_results(sim_results, params, scenario_title, config, run_type="single", best_value=None, optimization_goal=None, optimization_trials_df=None):
    """Tek bir simülasyonun ham sonuçlarını işler ve standart bir formatta sözlük olarak döndürür.

    Bu fonksiyon, simülasyon motorundan gelen çıktıları alır, son durum ERP verisini
    oluşturur ve tüm bu bilgileri UI Manager tarafından kullanılacak tek bir
    sözlük yapısında birleştirir.

    Args:
        sim_results (dict): `trigger_single_simulation` tarafından döndürülen sonuçlar.
        params (dict): Simülasyonu çalıştırmak için kullanılan parametreler.
        scenario_title (str): Sonuçların başlığında kullanılacak senaryo adı.
        config (dict): Ana uygulama yapılandırma sözlüğü.
        run_type (str, optional): Çalıştırma türü ('single' veya 'optimization').
        best_value (float, optional): Optimizasyon çalışması için en iyi değer.
        optimization_goal (str, optional): Optimizasyon hedefinin açıklaması.
        optimization_trials_df (pd.DataFrame, optional): Optimizasyon denemelerini içeren DataFrame.
    
    Returns:
        dict: UI katmanında kullanılmak üzere işlenmiş ve yapılandırılmış sonuç sözlüğü.
    """
    final_kpis = sim_results["results_df"].iloc[-1].copy()
    final_kpis['Gerçekleşen Olaylar_Listesi'] = list(sim_results["results_df"][sim_results["results_df"]['Gerçekleşen Olay'] != 'Kriz Yok']['Gerçekleşen Olay'])
    
    initial_erp_data = st.session_state.get('erp_data')
    final_erp_data = None 
    if initial_erp_data is not None:
         logger.info("Simülasyon sonrası ERP verisi oluşturuluyor.")
         final_erp_data = generate_final_erp_data(initial_erp_data, final_kpis, params)
    
    warehouse_analysis = analyze_warehouse_feasibility(final_erp_data, config)
    stock_composition = analyze_stock_composition_by_category(final_erp_data, config)

    result_dict = {
        "run_type": run_type,
        "results_df": sim_results["results_df"],
        "final_tesis_df": sim_results["final_tesis_df"], 
        "initial_state": sim_results["initial_state"], 
        "summary": sim_results.get("summary", {}),
        "params": params, 
        "scenario_title": scenario_title, 
        "final_erp_data": final_erp_data,
        "warehouse_feasibility": warehouse_analysis,
        "stock_composition": stock_composition
    }

    if run_type == "optimization":
        result_dict["best_value"] = best_value
        result_dict["optimization_goal"] = optimization_goal
        if optimization_trials_df is not None:
            result_dict["optimization_trials_df"] = optimization_trials_df

    return result_dict

def process_and_store_mc_results(mc_results, params, scenario_title):
    """Monte Carlo simülasyon sonuçlarını işler ve standart bir sözlük olarak döndürür.

    Args:
        mc_results (list): `run_monte_carlo_simulation` tarafından döndürülen sonuç listesi.
        params (dict): Simülasyonu çalıştırmak için kullanılan parametreler.
        scenario_title (str): Sonuçların başlığında kullanılacak senaryo adı.

    Returns:
        dict: UI katmanında kullanılmak üzere işlenmiş Monte Carlo sonuç sözlüğü.
    """
    return {
        "run_type": "monte_carlo",
        "mc_results": mc_results,
        "params": params,
        "scenario_title": scenario_title
    }

def run_simulation_flow(params_main, params_compare, is_comparison_mode, is_mc_mode, num_runs, base_data, timeline, locations, interventions, config, scenario_details):            
    """Simülasyon akışını yönetir.

    Kullanıcı tarafından seçilen moda göre (tek, karşılaştırmalı, Monte Carlo)
    gerekli simülasyonları çalıştırır ve sonuçları `st.session_state`'e kaydeder.

    Args:
        params_main (dict): Ana strateji parametreleri.
        params_compare (dict): Karşılaştırma stratejisi parametreleri.
        is_comparison_mode (bool): Karşılaştırma modunun aktif olup olmadığı.
        is_mc_mode (bool): Monte Carlo modunun aktif olup olmadığı.
        num_runs (int): Monte Carlo için tekrar sayısı.
        base_data (dict): Başlangıç verileri.
        timeline (dict): Aylara göre kriz olayları.
        locations (dict): Krizlerin etkileneceği coğrafyalar.
        interventions (dict): Krizlere karşı alınacak müdahaleler.
        config (dict): Genel yapılandırma.
        scenario_details (str): Çalıştırılan senaryonun açıklaması.
    """
    st.session_state.last_results = None
    st.session_state.comparison_results = None

    logger.info("Simülasyon akışı için talep tahmin doğruluğu anahtarı kontrol ediliyor ve ayarlanıyor.")
    if 'tahmin_d' not in params_main:
        params_main['tahmin_d'] = calculate_tahmin_d(params_main, config)
    
    if is_comparison_mode and params_compare and 'tahmin_d' not in params_compare:
        params_compare['tahmin_d'] = calculate_tahmin_d(params_compare, config)

    if is_mc_mode:
        logger.info(f"Monte Carlo simülasyonu başlatıldı. Tekrar sayısı: {num_runs}")
        progress_bar = st.progress(0, text="Monte Carlo simülasyonu çalıştırılıyor...")
        def mc_callback(current_run, total_runs):
            progress = current_run / total_runs
            progress_bar.progress(progress, text=f"Monte Carlo: Tekrar {current_run}/{total_runs}")
        mc_sim_results = run_monte_carlo_simulation(params_main, base_data, timeline, locations, interventions, config, num_runs, mc_callback)
        progress_bar.empty()
        st.session_state.last_results = process_and_store_mc_results(mc_sim_results, params_main, f"Monte Carlo | {scenario_details}")
    else:
        logger.info(f"Manuel simülasyon başlatıldı. Senaryo: {scenario_details}")
        with st.spinner(f"'{scenario_details}' senaryosu için Ana Strateji çalıştırılıyor..."):
            main_sim_results = trigger_single_simulation(params_main, base_data, timeline, locations, interventions, config)
            st.session_state.last_results = process_and_store_single_results(main_sim_results, params_main, f"Ana Strateji | {scenario_details}", config)

        if is_comparison_mode:
            logger.info("Karşılaştırma modu aktif, ikinci simülasyon çalıştırılıyor.")
            with st.spinner(f"'{scenario_details}' senaryosu için Karşılaştırma Stratejisi çalıştırılıyor..."):
                comp_sim_results = trigger_single_simulation(params_compare, base_data, timeline, locations, interventions, config)
                st.session_state.comparison_results = process_and_store_single_results(comp_sim_results, params_compare, f"Karşılaştırma Stratejisi | {scenario_details}", config)

def run_optimization_flow(params_main, base_data, timeline, locations, interventions, config, n_trials, optimization_goal, scenario_details):
    """Optimizasyon motoru akışını yönetir.

    Optuna kullanarak belirtilen hedefi optimize edecek en iyi strateji
    parametrelerini bulur. Ardından, bulunan en iyi parametrelerle son bir
    detaylı simülasyon çalıştırır ve sonuçları `st.session_state`'e kaydeder.

    Args:
        params_main (dict): Optimizasyon için başlangıç veya varsayılan parametreler.
        base_data (dict): Başlangıç verileri.
        timeline (dict): Aylara göre kriz olayları.
        locations (dict): Krizlerin etkileneceği coğrafyalar.
        interventions (dict): Krizlere karşı alınacak müdahaleler.
        config (dict): Genel yapılandırma.
        n_trials (int): Optimizasyon deneme sayısı.
        optimization_goal (str): Optimize edilecek hedef (örn: "Yıllık Net Kârı Maksimize Et").
        scenario_details (str): Çalıştırılan senaryonun açıklaması.
    """
    st.session_state.last_results = None
    st.session_state.comparison_results = None

    logger.info(f"Optimizasyon akışı başlatıldı. Hedef: {optimization_goal}, Deneme Sayısı: {n_trials}")
    progress_bar = st.progress(0, text="Strateji Optimizasyon Motoru çalıştırılıyor...")
    status_text = st.empty()
    def opt_callback(study, trial):
        progress = (trial.number + 1) / n_trials
        best_val_display = -study.best_value if study.best_value is not None and "Maksimize Et" in optimization_goal else study.best_value
        progress_bar.progress(progress, text=f"Optimizasyon: Deneme {trial.number + 1}/{n_trials}")
        status_text.text(f"Mevcut En İyi Skor: {best_val_display:,.2f}")
    
    best_params, best_value, optimization_trials_df = run_optimization(params_main, base_data, timeline, locations, interventions, config, n_trials, optimization_goal, opt_callback)
    
    progress_bar.empty()
    status_text.empty()
    
    logger.info(f"Optimizasyon tamamlandı. En iyi değer: {best_value}, Parametreler: {best_params}")
    st.success(f"Optimizasyon tamamlandı! Bulunan en iyi strateji ile sonuçlar hesaplanıyor...")

    best_params['tahmin_d'] = calculate_tahmin_d(best_params, config)

    with st.spinner("Optimal stratejinin detaylı sonuçları oluşturuluyor..."):
        final_sim_results = trigger_single_simulation(best_params, base_data, timeline, locations, interventions, config)
        
        st.session_state.last_results = process_and_store_single_results(
            sim_results=final_sim_results, 
            params=best_params, 
            scenario_title=f"Optimal Strateji | {scenario_details}", 
            config=config,
            run_type="optimization",
            best_value=best_value,
            optimization_goal=optimization_goal,
            optimization_trials_df=optimization_trials_df
        )

def main():
    """Ana uygulama akışını yöneten orkestratör fonksiyon.

    Bu fonksiyon, uygulamanın ana giriş noktasıdır. Başlangıç verilerini yükler,
    UI yöneticisini başlatır, sayfa navigasyonunu yönetir ve kullanıcı
    etkileşimlerine göre simülasyon veya optimizasyon akışlarını tetikler.
    """
    st.set_page_config(
        page_title="Kimoto Solutions - Entegre Simülatör",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    apply_custom_styles()

    logger.info("="*50)
    logger.info("Uygulama başlatıldı.")

    base_data = get_initial_data(CONFIG)
    ui = UIManager(base_data)

    st.sidebar.title("Kimoto Solutions")
    st.sidebar.markdown("### Entegre Karar Destek Sistemi")
    st.sidebar.markdown("<hr>", unsafe_allow_html=True)
    
    app_mode = st.sidebar.radio(
        "Navigasyon", 
        ('Ana Simülatör', 'Yönetim Paneli (Dashboard)', 'Dijital Dönüşüm Mimarisi', 'Metodoloji ve Stratejik Değer', 'Uygulama Yol Haritası'),
        label_visibility="collapsed"
    )
    st.sidebar.markdown("<hr>", unsafe_allow_html=True)

    manage_erp_data_sourcing()
    st.sidebar.markdown("<hr>", unsafe_allow_html=True)
    
    params_main, params_compare, is_comparison_mode, selected_jury_scenario = ui.draw_sidebar()

    if 'active_scenario' not in st.session_state:
        st.session_state.active_scenario = "-"
        
    if selected_jury_scenario != st.session_state.active_scenario:
        st.session_state.active_scenario = selected_jury_scenario
        if selected_jury_scenario != "-":
            scenario_params = JURY_SCENARIOS[selected_jury_scenario].get("params", {})
            st.session_state.params_main = scenario_params.copy()
            st.toast(f"'{selected_jury_scenario}' senaryosu ve stratejileri yüklendi!", icon="✅")
        st.rerun()
    
    if app_mode == 'Ana Simülatör':
        (user_timeline, user_locations, user_interventions, run_mode, 
         is_mc_mode, num_runs, optimization_goal, n_trials) = ui.draw_main_simulator_page()
    
        active_scenario_name = st.session_state.get('active_scenario', '-')
        if active_scenario_name != "-":
            st.success(f"**Hazır Senaryo Yüklendi:** '{active_scenario_name}'. Strateji ayarları kenar çubuğunda otomatik olarak güncellendi. Analizi başlatmak için butona tıklayın.")
    
        button_text = "🚀 Analizi Başlat"
        if run_mode == "🤖 Strateji Optimizasyon Motoru":
            button_text = f"💡 En İyi Stratejiyi Bul ({n_trials} Deneme)"
        elif is_mc_mode:
            button_text = f"🎲 Monte Carlo Simülasyonunu Başlat ({num_runs} Tekrar)"
        elif is_comparison_mode:
            button_text = "🆚 İki Stratejiyi Karşılaştır"

        run_sim = st.button(button_text, use_container_width=True, type="primary")
    
        if run_sim:
            active_scenario_name_for_run = st.session_state.get('active_scenario', '-')
            if active_scenario_name_for_run != "-":
                scenario_details = f"Jüri Özel: '{active_scenario_name_for_run}'"
                scenario_config = JURY_SCENARIOS.get(active_scenario_name_for_run, {})
                timeline = scenario_config.get("timeline", {})
                locations = scenario_config.get("locations", {})
                params_main = scenario_config.get("params", params_main)
                interventions = user_interventions
            else:
                scenario_details = "Manuel Senaryo"
                timeline, locations, interventions = user_timeline, user_locations, user_interventions

            if run_mode == "🤖 Strateji Optimizasyon Motoru":
                run_optimization_flow(params_main, base_data, timeline, locations, interventions, CONFIG, n_trials, optimization_goal, scenario_details)
            else:  
                run_simulation_flow(params_main, params_compare, is_comparison_mode, is_mc_mode, num_runs, base_data, timeline, locations, interventions, CONFIG, scenario_details)
    
        ui.draw_simulation_results()

    elif app_mode == 'Yönetim Paneli (Dashboard)':
        ui.draw_dashboard_page()
    elif app_mode == 'Dijital Dönüşüm Mimarisi':
        ui.draw_architecture_page()
    elif app_mode == 'Metodoloji ve Stratejik Değer':
        ui.draw_methodology_page()
    elif app_mode == 'Uygulama Yol Haritası':
        ui.draw_rollout_page()

if __name__ == "__main__":
    main()