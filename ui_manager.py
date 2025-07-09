import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import altair as alt
from streamlit_folium import st_folium
from collections import Counter

from event_library import EVENT_LIBRARY, DOMINO_RULES, JURY_SCENARIOS
from config import (CONFIG, URETIM_STRATEJILERI, STOK_STRATEJILERI, MONTH_NAMES)
from simulation_engine import (calculate_risk_matrix, analyze_stock_and_demand_risk, 
                               perform_abc_analysis,calculate_crisis_impact_comparison)

from ui_components import (
    display_colored_progress,
    render_before_diagram,
    render_after_diagram,
    render_stakeholder_analysis,
    render_rollout_plan,
    plot_risk_heatmap,
    render_financial_intelligence_panel,
    plot_abc_analysis,
    create_interactive_map
)

class UIManager:
    """Tüm Streamlit arayüzünü (UI) çizmekten ve yönetmekten sorumlu sınıf.

    Bu sınıf, `st.session_state`'ten ve simülasyon sonuçlarından gelen verileri
    alıp kullanıcıya görsel olarak (grafikler, tablolar, metrikler vb.) sunar.
    Kullanıcı etkileşimlerini (sidebar'daki parametre seçimleri, buton tıklamaları)
    yakalar ve ana uygulama akışına girdi sağlar.
    """
    def __init__(self, base_data):
        """UIManager nesnesini başlatır.

        Args:
            base_data (dict): `get_initial_data` tarafından oluşturulan ve
                              başlangıç KPI'larını, 'As-Is' durumunu göstermek
                              için gereken verileri içeren sözlük.
        """
        self.base_data = base_data
        self.config = CONFIG

        if 'scenarios' not in st.session_state:
            st.session_state.scenarios = []
        if 'risk_matrix_df' not in st.session_state:
            st.session_state.risk_matrix_df = None

        if 'scenarios' not in st.session_state: st.session_state.scenarios = []

    def _get_default_params(self):
        """Tüm strateji parametreleri için varsayılan değerleri içeren bir sözlük oluşturur."""
        defaults = {}
        for key, slider_config in self.config['ui_settings']['sliders'].items():
            defaults[key] = slider_config['default']
        
        defaults['uretim_s'] = URETIM_STRATEJILERI[0]
        defaults['transport_m'] = 'default'
        defaults['stok_s'] = STOK_STRATEJILERI[0]
        
        defaults['tahmin_algoritmasi'] = list(self.config['strategy_impacts']['tahmin_modeli']['algoritmalar'].keys())[0]
        for kaynak in self.config['strategy_impacts']['tahmin_modeli']['veri_kaynaklari'].keys():
            defaults[kaynak] = False
        
        defaults['mevsimsellik_etkisi'] = False
        defaults['ozel_sku_modu'] = False
        
        return defaults

    def _draw_strategy_parameters(self, params_key, title):
        st.subheader(title)
        params = st.session_state.get(params_key, {})

        tek_kaynak_config = self.config['ui_settings']['sliders']['tek_kaynak_orani']
        params['tek_kaynak_orani'] = st.slider(
            tek_kaynak_config['label'], min_value=tek_kaynak_config['min'], max_value=tek_kaynak_config['max'],
            value=params.get('tek_kaynak_orani', tek_kaynak_config['default']),
            step=tek_kaynak_config['step'], key=f"tek_kaynak_orani_{params_key}",
            help="💡 `Hammadde Tedarikçi Krizi` gibi arz şoklarına karşı kırılganlığınızı belirler."
        )

        lojistik_m_config = self.config['ui_settings']['sliders']['lojistik_m']
        params['lojistik_m'] = st.slider(
            lojistik_m_config['label'], min_value=lojistik_m_config['min'], max_value=lojistik_m_config['max'],
            value=params.get('lojistik_m', lojistik_m_config['default']),
            step=lojistik_m_config['step'], key=f"lojistik_m_{params_key}",
            help="💡 Lojistik esnekliğinizi ve değişken maliyet yapınızı etkiler."
        )

        uretim_stratejileri_list = list(self.config['strategy_impacts']['uretim'].keys())
        uretim_s_default = params.get('uretim_s', uretim_stratejileri_list[0])
        params['uretim_s'] = st.selectbox(
            'Üretim Stratejisi', options=uretim_stratejileri_list,
            index=uretim_stratejileri_list.index(uretim_s_default), key=f"uretim_s_{params_key}",
            help="🎯 Üretim ağınızın çevikliğini, CO2 ayak izinizi ve sabit maliyetlerinizi yeniden şekillendirir."
        )

        params['transport_m'] = "default"
        if params['uretim_s'] != uretim_stratejileri_list[0]:
            transport_options = list(self.config['strategy_impacts']['transport']['modes'].keys())
            transport_options.remove('default')
            current_transport_index = 0
            if params.get('transport_m', 'default') in transport_options:
                current_transport_index = transport_options.index(params['transport_m'])

            params['transport_m'] = st.selectbox(
                '🚚 Çevik Merkez Taşıma Modu',
                options=transport_options,
                index=current_transport_index,
                key=f"transport_m_{params_key}",
                help="Çevik üretim merkezinden yapılacak sevkiyatlar için daha hızlı (ama pahalı) veya daha yavaş (ama ucuz) taşıma modlarını seçerek hizmet seviyesi ve maliyet dengesini kurun."
            )

        st.markdown("---")

        stok_stratejileri_list = list(self.config['strategy_impacts']['stok'].keys())
        stok_s_default = params.get('stok_s', stok_stratejileri_list[0])
        params['stok_s'] = st.selectbox(
            'Stok Optimizasyon Odağı', options=stok_stratejileri_list,
            index=stok_stratejileri_list.index(stok_s_default), key=f"stok_s_{params_key}",
            help="🎯 Hizmet seviyesi, müşteri memnuniyeti ve nakit döngü süresi arasındaki dengeyi kurar."
        )

        st.markdown("---")

        params['mevsimsellik_etkisi'] = st.checkbox(
            '❄️ Mevsimsel Talep Dalgalanmasını Simüle Et', 
            value=params.get('mevsimsellik_etkisi', False), 
            key=f"mevsim_{params_key}",
            help="💡 Aktif edildiğinde, C kategorisi ürünlerin talebinin yoğunlaştığı kış aylarında (Kasım, Aralık, Ocak) OTIF üzerinde oluşacak operasyonel baskıyı simüle eder. Bu, tedarik zincirinin talep zirvelerine ne kadar hazırlıklı olduğunu test eder."
        )
        params['ozel_sku_modu'] = st.checkbox('🏭 Özel SKU Üretim Modu Aktif', help="Özel müşteri siparişlerinin getirdiği ek operasyonel maliyeti ve daha yüksek hizmet beklentisini simüle eder.", value=params.get('ozel_sku_modu', False), key=f"sku_{params_key}")

        st.session_state[params_key] = params

    def draw_sidebar(self):
        """Uygulamanın kenar çubuğunu (sidebar) çizer ve yönetir."""

        if 'params_main' not in st.session_state:
            st.session_state.params_main = self._get_default_params()
        if 'params_compare' not in st.session_state:
            st.session_state.params_compare = self._get_default_params()
        
        st.sidebar.markdown("""
            <div class="sidebar-header">
                <span class="sidebar-icon">⚡</span>
                <span class="sidebar-title">Hızlı Başlangıç: Senaryo Yükle</span>
            </div>
        """, unsafe_allow_html=True)
        st.sidebar.markdown("<p class='sidebar-caption'>Analize hızlıca başlamak için aşağıdaki Jüri Özel senaryolarından birini seçin. Seçiminiz aşağıdaki ayarları otomatik güncelleyecektir.</p>", unsafe_allow_html=True)
        
        jury_scenarios = ["-"] + list(JURY_SCENARIOS.keys())
        selected_jury_scenario = st.sidebar.selectbox(
            "Jüri Özel Senaryosu:",
            options=jury_scenarios,
            key='selected_scenario_widget',
            index=jury_scenarios.index(st.session_state.get('active_scenario', '-'))
        )

        is_comparison_mode = st.sidebar.checkbox("🆚 Strateji Karşılaştırma Modunu Aktif Et")

        with st.sidebar.expander("🛠️ Özel Strateji ve Tahmin Modeli Ayarları", expanded=False):
            st.markdown("<h6>🧠 Talep Tahmin Modeli Ayarları</h6>", unsafe_allow_html=True)
            model_cfg = self.config['strategy_impacts']['tahmin_modeli']
            kpi_cfg = self.config['kpi_defaults']
            
            current_params_for_common_settings = st.session_state.get('params_main', {})
            
            tahmin_algoritmasi_options = list(model_cfg['algoritmalar'].keys())
            tahmin_algoritmasi_default = current_params_for_common_settings.get('tahmin_algoritmasi', tahmin_algoritmasi_options[0])
            tahmin_algoritmasi = st.selectbox("Tahmin Algoritması", 
                                             options=tahmin_algoritmasi_options, 
                                             index=tahmin_algoritmasi_options.index(tahmin_algoritmasi_default),
                                             key="tahmin_algo_ortak")
            
            veri_kaynaklari = {}
            st.write("**Kullanılacak Ek Veri Kaynakları:**")
            for kaynak, ayar in model_cfg['veri_kaynaklari'].items(): 
                veri_kaynaklari[kaynak] = st.checkbox(f"{ayar['label']} (`+{ayar['bonus']:.0%}`)", 
                                                     value=current_params_for_common_settings.get(kaynak, False),
                                                     key=f"{kaynak}_ortak")
        
            base_accuracy = kpi_cfg['talep_tahmin_dogrulugu']
            bonus = model_cfg['algoritmalar'][tahmin_algoritmasi]['bonus']
            for kaynak, is_checked in veri_kaynaklari.items():
                if is_checked: bonus += model_cfg['veri_kaynaklari'][kaynak]['bonus']
            
            calculated_accuracy = min(0.99, base_accuracy + bonus)
            forecast_value_add = calculated_accuracy - base_accuracy

            for params_key in ['params_main', 'params_compare']:
                st.session_state[params_key]['tahmin_algoritmasi'] = tahmin_algoritmasi
                st.session_state[params_key].update(veri_kaynaklari)
                st.session_state[params_key]['tahmin_d'] = calculated_accuracy

            st.metric(label="Hesaplanan Tahmin Doğruluğu", value=f"{calculated_accuracy:.1%}")
            st.metric(label="Tahmin Katma Değeri (FVA)", value=f"+{forecast_value_add:.1%}", 
                      help="Seçilen model ve veri kaynaklarının, temel modele kıyasla sağladığı ek doğruluk.",
                      delta_color="normal" if forecast_value_add > 0.001 else "off")

            st.markdown("<hr>", unsafe_allow_html=True)
            
            if is_comparison_mode:
                strategy_to_edit = st.radio("Düzenlenecek Strateji:", ("Ana Strateji", "Karşılaştırma Stratejisi"), horizontal=True, label_visibility="collapsed")
                if strategy_to_edit == "Ana Strateji":
                    self._draw_strategy_parameters('params_main', 'Ana Strateji Ayarları')
                else:
                    self._draw_strategy_parameters('params_compare', 'Karşılaştırma Stratejisi Ayarları')
            else:
                self._draw_strategy_parameters('params_main', 'Ana Strateji Ayarları')

        params_compare = st.session_state.params_compare if is_comparison_mode else None

        return st.session_state.params_main, params_compare, is_comparison_mode, selected_jury_scenario

    def draw_main_simulator_page(self):
        """'Ana Simülatör' sekmesinin ana içerik alanını çizer.

        Bu alan, kullanıcının simülasyon modunu (Manuel, Optimizasyon, Monte Carlo)
        seçmesini, aylık krizleri ve müdahaleleri belirlemesini sağlar.
        """
        st.title("Entegre Karar Destek Sistemi | Ana Simülatör")
        with st.info('**Başlangıç Rehberi**', icon="💡"):
            st.markdown(
                "1. **Veri Yükleme:** <span class='guidance-pill'>🔄 ERP'den Canlı Veri Çek</span> butonuyla başlayarak analiz için temel verileri yükleyin.\n"
                "2. **Senaryo ve Strateji Belirleme:**\n"
                "   - **Hızlı Başlangıç:** <span class='guidance-pill'>⚡ Hızlı Başlangıç</span> bölümünden bir Jüri Senaryosu seçerek analize hemen başlayın.\n"
                "   - **Detaylı Ayarlar:** Veya <span class='guidance-pill'>🛠️ Özel Strateji ve Tahmin Modeli Ayarları</span> bölümünü genişleterek kendi stratejinizi tasarlayın.\n"
                "3. **Analiz Modunu Seçin:**\n"
                "   - **Tekil Analiz:** <span class='guidance-pill'>Manuel Strateji Analizi</span> ile belirlediğiniz stratejinin sonuçlarını görün.\n"
                "   - **Karşılaştırma:** <span class='guidance-pill'>🆚 Strateji Karşılaştırma</span> seçeneğiyle iki farklı stratejiyi kıyaslayın.\n"
                "   - **Risk Analizi:** <span class='guidance-pill'>🎲 Monte Carlo Modu</span> ile stratejinizin olasılıksal risklere karşı dayanıklılığını ölçün.\n"
                "   - **Yapay Zeka:** <span class='guidance-pill'>🤖 Strateji Optimizasyon Motoru</span> ile hedeflerinizi maksimize edecek en iyi stratejiyi yapay zekanın bulmasını sağlayın.\n"
                "4. **Analizi Başlat:** Ayarlarınızı yaptıktan sonra aşağıdaki <span class='guidance-pill-main'>🚀 Analizi Başlat</span> butonuna tıklayın.",
                unsafe_allow_html=True
            )

        is_mc_mode, num_runs, optimization_goal, n_trials = False, 1, None, 100
        user_timeline_events, user_event_locations, interventions = {}, {}, {}

        with st.container(border=True):
            st.subheader("🕹️ Simülatör Kontrol Paneli")

            st.markdown("<h6>1. Simülasyon Modunu ve Hedefini Belirleyin</h6>", unsafe_allow_html=True)
            run_mode = st.radio(
                "Çalışma Modu:",
                ("Manuel Strateji Analizi", "🤖 Strateji Optimizasyon Motoru"),
                horizontal=True,
                key="run_mode",
                label_visibility="collapsed"
            )

            if run_mode == "Manuel Strateji Analizi":
                is_mc_mode = st.checkbox("🎲 Monte Carlo Modunu Aktif Et (Olasılıksal Risk Analizi)", help="Seçili senaryoyu birden çok kez çalıştırarak sonuçların istatistiksel dağılımını analiz eder. Yalnızca olasılıksal olaylar (örn: Domino Etkisi) içeren senaryolar için anlamlıdır.")
                if is_mc_mode:
                    num_runs = st.slider("Tekrar Sayısı", min_value=10, max_value=500, value=100, step=10)
            else: 
                st.info("Bu mod, seçtiğiniz hedefi maksimize edecek en iyi strateji kombinasyonunu bulmak için yapay zeka kullanır. Strateji parametreleri kenar çubuğundan değil, motor tarafından otomatik olarak seçilecektir.")
                optimization_goal = st.selectbox(
                    "Optimizasyon Hedefiniz Nedir?",
                    ("Yıllık Net Kârı Maksimize Et", "Final OTIF'i Maksimize Et", "Final Esneklik Skorunu Maksimize Et", "CO2 Tasarrufunu Maksimize Et")
                )
                n_trials = st.slider(
                    "Optimizasyon Hassasiyeti (Deneme Sayısı)",
                    min_value=20, max_value=1000, value=100, step=10,
                    help="Daha yüksek deneme sayısı, daha iyi bir strateji bulma olasılığını artırır ancak daha uzun sürer."
                )

            st.markdown("<hr style='margin-top:1rem; margin-bottom:1rem'>", unsafe_allow_html=True)
            st.markdown("<h6>2. Senaryo ve Müdahaleleri Planlayın (İsteğe Bağlı)</h6>", unsafe_allow_html=True)
            st.caption("Kendi özel kriz takviminizi oluşturmak için bu bölümü kullanabilirsiniz. Kenar çubuğundan bir Jüri Senaryosu seçtiyseniz, o senaryonun krizleri otomatik yüklenir ancak siz yine de onlara karşı kendi müdahalelerinizi buradan seçebilirsiniz.")

            with st.expander("🛠️ Manuel Kriz Takvimi Oluştur"):
                cols_events = st.columns(4)
                for month in range(1, self.config['simulation_parameters']['months_in_year'] + 1):
                    with cols_events[(month - 1) % 4]:
                        selected_event = st.selectbox(f"{MONTH_NAMES[month-1]} Olayı", options=list(EVENT_LIBRARY.keys()), key=f"month_event_{month}", disabled=(run_mode == "🤖 Strateji Optimizasyon Motoru"))
                        if selected_event != "Kriz Yok":
                            user_timeline_events[month] = selected_event
                            event_details = EVENT_LIBRARY.get(selected_event, {})
                            if event_details.get("is_geographic", False):
                                location_options = ['Genel'] + list(self.base_data['tesisler_df']['Ulke'].unique())
                                selected_location = st.selectbox("Etkilenen Bölge", options=location_options, key=f"month_location_{month}", disabled=(run_mode == "🤖 Strateji Optimizasyon Motoru"))
                                if selected_location != 'Genel':
                                    user_event_locations[month] = selected_location
                st.markdown("---")

                st.subheader("Taktiksel Müdahaleler")
                is_intervention_disabled = (run_mode == "🤖 Strateji Optimizasyon Motoru")
                active_crisis_months = sorted([m for m, e in user_timeline_events.items() if EVENT_LIBRARY[e].get("interventions") and len(EVENT_LIBRARY[e]["interventions"]) > 1])

                if not active_crisis_months or is_intervention_disabled:
                    st.info("Müdahale edilebilir bir kriz eklediğinizde (ve manuel analiz modundayken), seçenekler burada görünecektir.")
                else:
                    cols_interventions = st.columns(len(active_crisis_months) if active_crisis_months else 1)
                    for i, month in enumerate(active_crisis_months):
                        with cols_interventions[i]:
                            event_name = user_timeline_events[month]
                            intervention_options = list(EVENT_LIBRARY[event_name].get("interventions").keys())
                            interventions[month] = st.selectbox(f"{MONTH_NAMES[month-1]} Müdahalesi", options=intervention_options, key=f"int_{month}")

        return user_timeline_events, user_event_locations, interventions, run_mode, is_mc_mode, num_runs, optimization_goal, n_trials

    def draw_methodology_page(self):
        """'Metodoloji ve Stratejik Değer' sayfasını çizer."""
        st.title("🧠 Metodoloji ve Stratejik Değer")
        st.info("Bu bölüm, simülatörün neden basit bir tablolama aracından daha fazlası olduğunu ve hangi varsayımlar üzerine kurulu olduğunu şeffaflıkla açıklamaktadır.")

        with st.container(border=True):
            st.subheader("💡 Neden Basit Bir Excel Tablosu Değil?")
            st.markdown("""
            Bir Excel tablosu mevcut durumun bir **fotoğrafını** çekebilir. Bu Karar Destek Sistemi ise, tedarik zincirinizin **dinamik bir filmini** oynatır ve geleceğe yönelik stratejik kararlar vermenizi sağlar. Excel'in cevaplayamadığı kritik sorular şunlardır:
            """)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("##### 🔗 Etkileşim (Domino Etkisi)")
                st.markdown("Bir tedarik krizinin, 2 ay sonra bir müşteri güven krizini tetikleme olasılığını ve birleşik etkisini Excel'de modelleyebilir misiniz?")
            with col2:
                st.markdown("##### 🎲 Olasılıksal Risk Analizi")
                st.markdown("Seçtiğiniz stratejinin, 100 farklı gelecek senaryosunda size en kötü ihtimalle ne kadara mal olacağını ve başarı olasılığınızın tam olarak % kaç olduğunu Excel size söyleyebilir mi?")
            with col3:
                st.markdown("##### 🤖 Akıllı Optimizasyon")
                st.markdown("Hedefiniz kârı maksimize etmek olduğunda, binlerce strateji kombinasyonu arasından insan aklının gözden kaçırabileceği en optimal üretim ve stok politikasını Excel sizin için bulabilir mi?")
        
        st.markdown("---")

        with st.container(border=True):
            st.subheader("🔬 Modelin Kavramsal Sınırları ve Evrim Potensiyeli")
            st.info("""
            Her model, gerçek dünyanın bir basitleştirmesidir. Bu prototipin gücü, karmaşık ilişkileri anlaşılır kılmasında yatmaktadır. Modelimizin mevcut sınırlarını ve bir sonraki mantıksal evrim adımlarını şeffaflıkla tanımlıyoruz:
            """)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("##### 1. Veri Bağımsızlığı (Mevcut Sınır)")
                st.markdown("""
                **Tespit:** Prototip, statik bir veri setine (`erp_data_300_sku.csv`) dayanmaktadır. Bu, modelin temel mantığını ve stratejilerin göreceli etkilerini test etmek için mükemmel bir başlangıç noktasıdır.
                **Potansiyel Evrim:** Modelin en temel evrim adımı, herhangi bir şirketin kendi ERP verisini yükleyebileceği bir arayüzle (`st.file_uploader` gibi) **veri-bağımsız** hale getirilmesidir.
                """)
                st.markdown("##### 2. Davranışsal Modelleme (Mevcut Varsayım)")
                st.markdown("""
                **Tespit:** Esneklik skorundaki değişim katsayıları (+0.1 artış, -0.5 düşüş) asimetriktir.
                **Mantık:** Bu bilinçli bir modelleme kararıdır. Kriz anında yaşanan bir şokun (örn: OTIF'in çökmesi) organizasyon üzerindeki olumsuz etkisinin, normal zamanlarda elde edilen kademeli iyileşmelerden çok daha hızlı ve şiddetli olduğunu varsayıyoruz. Bu asimetri, tedarik zincirinin kırılganlığını ve bir krizden toparlanmanın ne kadar zor olduğunu daha gerçekçi bir şekilde yansıtır.
                """)
            with col2:
                st.markdown("##### 3. Parametre Kalibrasyonu (Gelecek Vizyonu)")
                st.markdown("""
                **Tespit:** Modelimizdeki kriz etkisi ve davranışsal katsayılar, literatür ve mantıksal varsayımlara dayanmaktadır. Bu, genel bir stratejik yönlendirme sağlar.
                **Potansiyel Evrim:** Modelin en ileri seviyesi, bir şirketin **kendi geçmiş verileriyle eğitilerek** bir **"Dijital İkiz"** haline getirilmesidir. Bu süreçte, örneğin geçmişteki bir tedarikçi krizinin gerçek OTIF etkisine bakılarak, modelin kriz katsayıları istatistiksel olarak **kalibre edilir.** Bu, modelin sadece stratejik değil, aynı zamanda operasyonel tahmin gücünü de zirveye taşıyan bir veri bilimi adımıdır.
                """)

    def draw_simulation_results(self):
        """Simülasyon sonuçlarını görüntülemek için ana yönlendirici (dispatcher) fonksiyonu.

        `st.session_state`'teki `last_results` verisinin türüne göre
        (tek, karşılaştırma, optimizasyon, monte carlo) ilgili sonuç
        görüntüleme fonksiyonunu çağırır.
        """
        if 'last_results' not in st.session_state or not st.session_state.last_results:
            return

        st.header("📈 Simülasyon Sonuçları ve Analizi")

        results_data = st.session_state.last_results
        scenario_title = results_data.get('scenario_title', 'Bilinmeyen Senaryo')
        run_type = results_data.get("run_type", "single")

        if run_type == "optimization":
            optimization_goal = results_data.get('optimization_goal', '')
            st.success(f"**Optimizasyon Tamamlandı!** Hedef: `{optimization_goal}`")
        elif run_type == "monte_carlo":
            st.info(f"**Çalıştırılan Senaryo:** {scenario_title} ({len(results_data.get('mc_results', []))} Tekrar)")
        else:
            st.info(f"**Çalıştırılan Senaryo:** {scenario_title}")

        if run_type == "optimization":
            self.draw_optimization_results()
        elif run_type == "monte_carlo":
            self.draw_monte_carlo_summary()
        else:
            is_comparison_run = 'comparison_results' in st.session_state and st.session_state.comparison_results
            if is_comparison_run:
                self.draw_comparison_view()
            else:
                self.draw_single_view()

    def draw_optimization_results(self):
        results_data, best_params = st.session_state.last_results, st.session_state.last_results["params"]
        best_value, optimization_goal, results_df = results_data["best_value"], results_data["optimization_goal"], results_data["results_df"]
        st.subheader("🤖 Optimizasyon Motoru Sonuçları")
        with st.container(border=True):
            st.markdown(f"#### 🎯 Hedef: {optimization_goal}")
            formatted_value = f"{best_value:.2f}"
            if "Kâr" in optimization_goal: formatted_value = f"${best_value:,.0f}"
            elif "OTIF" in optimization_goal: formatted_value = f"{best_value:.1%}"
            elif "CO2" in optimization_goal: formatted_value = f"{best_value:,.0f} ton"
            st.metric(label="Ulaşılan En İyi Değer", value=formatted_value)
            st.markdown("##### 💡 Bulunan Optimal Strateji Paketi:")
            readable_params = {"Üretim Stratejisi": best_params.get('uretim_s'), "Stok Stratejisi": best_params.get('stok_s'), "Tek Kaynak Oranı": f"{best_params.get('tek_kaynak_orani', 0):.0%}", "3PL Oranı": f"{best_params.get('lojistik_m', 0):.0%}", "Özel SKU Modu": "Aktif" if best_params.get('ozel_sku_modu') else "Pasif", "Mevsimsellik Zirvesi": "Aktif" if best_params.get('mevsimsellik_etkisi') else "Pasif", "Tahmin Algoritması": best_params.get('tahmin_algoritmasi')}
            if best_params.get('transport_m', 'default') != 'default': readable_params["Çevik Merkez Taşıma Modu"] = best_params['transport_m']
            cols = st.columns(3)
            for i, (key, value) in enumerate(readable_params.items()):
                with cols[i % 3]: st.markdown(f"**{key}:** {value}")
            st.markdown("---")
            scenario_note = f"Optimum: {optimization_goal}"
            if st.button('Bu Optimal Senaryoyu Karşılaştırmak İçin Kaydet 💾', key='save_optimal_scenario'):
                final_row_save = results_df.iloc[-1]
                yillik_toplam_kar_zarar_save = results_df['Aylık Net Kar'].sum() - (self.base_data['initial_kpis']['net_kar_aylik'] * self.config['simulation_parameters']['months_in_year'])
                co2_tasarrufu_save = results_data.get('summary', {}).get('co2_savings', 0)
                st.session_state.scenarios.append({"Not": scenario_note, "Final OTIF": f"{final_row_save['OTIF']:.1%}", "Yıllık Kar/Zarar": f"${yillik_toplam_kar_zarar_save:,.0f}", "CO2 Tasarrufu": f"{co2_tasarrufu_save:,.0f} ton", "Final Esneklik": f"{final_row_save['Esneklik Skoru']:.1f}"})
                st.success(f"Senaryo '{scenario_note}' kaydedildi!")
        st.markdown("---")
        st.markdown("### Optimal Stratejinin Detaylı Analizi")
        self.draw_single_view()

    def draw_monte_carlo_summary(self):
        results_data = st.session_state.last_results
        mc_results_df = pd.DataFrame(results_data["mc_results"])
        num_runs = len(mc_results_df)

        profits = mc_results_df["annual_profits"]
        otifs = mc_results_df["final_otifs"]

        st.success("Sonuçlar hazır! Detaylı interaktif analiz için kenar çubuğundan **'Yönetim Paneli (Dashboard)'** sekmesine gidin.")
        st.subheader("Olasılıksal Sonuç Özeti")
        st.caption("Bu metrikler, senaryonun potansiyel sonuç yelpazesini ve risklerini gösterir.")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 💸 Yıllık Net Kâr/Zarar Dağılımı")
            st.metric("Ortalama Sonuç", f"${profits.mean():,.0f}")
            st.metric("En Kötü Durum (P5)", f"${profits.quantile(0.05):,.0f}", "Daha düşük kayıp beklenir")
            st.metric("En İyi Durum (P95)", f"${profits.quantile(0.95):,.0f}", "Daha yüksek kazanç beklenir")
        with col2:
            st.markdown("##### 🎯 Final OTIF Dağılımı")
            st.metric("Ortalama OTIF", f"{otifs.mean():.2%}")
            st.metric("En Kötü Durum (P5)", f"{otifs.quantile(0.05):.2%}")
            st.metric("En İyi Durum (P95)", f"{otifs.quantile(0.95):.2%}")

        st.markdown("---")
        st.subheader("Sonuç Dağılım Grafikleri")
        fig_profit = px.histogram(mc_results_df, x="annual_profits", nbins=30, title="Yıllık Net Kâr/Zarar Dağılımı", labels={'annual_profits': 'Yıllık Net Kâr/Zarar ($)'})
        fig_profit.add_vline(x=profits.mean(), line_dash="dash", line_color="red", annotation_text=f"Ortalama: ${profits.mean():,.0f}")
        st.plotly_chart(fig_profit, use_container_width=True)

        fig_otif = px.histogram(mc_results_df, x="final_otifs", nbins=30, title="Final OTIF Dağılımı", labels={'final_otifs': 'Final OTIF'})
        fig_otif.update_xaxes(tickformat=".1%")
        fig_otif.add_vline(x=otifs.mean(), line_dash="dash", line_color="red", annotation_text=f"Ortalama: {otifs.mean():.1%}")
        st.plotly_chart(fig_otif, use_container_width=True)

    def _render_as_is_panel(self):
        st.header("Başlangıç (As-Is)")
        as_is_col1, as_is_col2 = st.columns(2)
        with as_is_col1:
            st.metric("OTIF", f"{self.base_data['initial_kpis']['otif']:.0%}")
            st.metric("Stok Devir Hızı", f"{self.base_data['initial_kpis']['stok_devir_hizi']:.2f} kez")
            st.metric("Müşteri Memnuniyeti", f"{self.base_data['initial_kpis']['musteri_memnuniyeti_skoru']:.1f}/10")
        with as_is_col2:
            st.metric("Esneklik Skoru", f"{self.base_data['initial_kpis']['esneklik_skoru']:.1f}/10")
            st.metric("Yıllık CO2 Emisyonu", f"{self.base_data['mevcut_co2_emisyonu']:,.0f} ton")
            st.metric("Aylık Net Kar", f"${self.base_data['initial_kpis']['net_kar_aylik']:,.0f}")

    def _calculate_financial_breakdown(self, final_row):
        fin_factors = self.config['financial_impact_factors']
        otif_shortfall = fin_factors['target_otif'] - final_row['OTIF']
        otif_cost = otif_shortfall * fin_factors['annual_revenue'] * fin_factors['otif_penalty_ratio'] if otif_shortfall > 0 else 0
        dead_stock_cost = fin_factors['total_inventory_value'] * fin_factors['slow_stock_ratio'] * fin_factors['annual_holding_cost_ratio']
        return otif_cost, dead_stock_cost
    
    def _render_full_financial_breakdown_section(self, final_row):
        st.markdown("##### 💸 Operasyonel Kayıpların Finansal Dökümü")
        st.caption("Operasyonel verimsizliklerin (düşük hizmet seviyesi ve yavaş stoklar) yıllıklandırılmış parasal karşılığını gösterir. Bu rakamlar, simülasyonun yıllık net kâr/zarar rakamına dahil DEĞİLDİR; potansiyel iyileştirme alanlarını vurgular.")
        otif_cost, dead_stock_cost = self._calculate_financial_breakdown(final_row)
        fin_col1, fin_col2 = st.columns(2)
        with fin_col1:
            st.metric("Düşük OTIF Maliyeti", f"$ {otif_cost:,.0f}", help="Müşterilerin talep ettiği OTIF hedefine ulaşılamamasından kaynaklanan tahmini yıllık kayıp.")
        with fin_col2:
            st.metric("Atıl Stok Maliyeti", f"$ {dead_stock_cost:,.0f}", help="Yavaş/atıl stoğun yıllık stok taşıma maliyeti.")

    def _render_kpi_card(self, title, value, initial_value, target, value_format_str, delta_prefix="", higher_is_better=True, help_text=None):
        """
        Standart bir KPI kartını (metrik, delta ve progress bar) çizen yardımcı fonksiyon.
        """
        delta = value - initial_value
    
        delta_color = "normal"
        if (delta < 0 and higher_is_better) or (delta > 0 and not higher_is_better):
            delta_color = "inverse"
        if abs(delta) < 1e-6:
            delta_color = "off"

        formatted_value = value_format_str.format(value)
        
        if " kez" in delta_prefix:
            formatted_delta = f"{value_format_str.format(abs(delta))}{delta_prefix}"
        else: 
            formatted_delta = f"{delta_prefix}{value_format_str.format(abs(delta))}"

        st.metric(
            label=f"{title} (Hedef: {value_format_str.format(target)})",
            value=formatted_value,
            delta=formatted_delta,
            delta_color=delta_color,
            help=help_text
        )
        display_colored_progress(value, target)

    def _render_comparison_column(self, results_data, title, include_financial_breakdown=True):
        st.header(title)
        
        summary = results_data.get("summary", {})
        params = results_data.get("params", {})
        ui_targets = self.config['ui_settings']['targets']
        ccc_cfg = self.config['ccc_factors']
    
        yillik_net_tasarruf = summary.get('annual_profit_change', 0)
        final_otif = summary.get('final_otif', 0)
        final_turnover_rate = summary.get('final_turnover', self.base_data['initial_kpis']['stok_devir_hizi'])
        final_satisfaction = summary.get('final_satisfaction', 0)
        final_flexibility = summary.get('final_flexibility', 0)

        initial_dio = 365 / self.base_data['initial_kpis']['stok_devir_hizi']
        ccc_initial = initial_dio + ccc_cfg['dso_days'] - ccc_cfg['dpo_days']
        final_dio = 365 / final_turnover_rate if final_turnover_rate > 0 else float('inf')
        ccc_final = final_dio + ccc_cfg['dso_days'] - ccc_cfg['dpo_days']

        sub_col1, sub_col2, sub_col3 = st.columns(3)

        with sub_col1:
            st.subheader("Operasyonel")
            otif_target = ui_targets['otif']
            if params.get('ozel_sku_modu', False):
                otif_target = self.config['strategy_impacts']['ozel_sku']['otif_hedefi']
        
            self._render_kpi_card(
                title="Final OTIF",
                value=final_otif,
                initial_value=self.base_data['initial_kpis']['otif'],
                target=otif_target,
                value_format_str="{:.1%}",
                delta_prefix=""
            )
            self._render_kpi_card(
                title="Final Stok Devir Hızı",
                value=final_turnover_rate,
                initial_value=self.base_data['initial_kpis']['stok_devir_hizi'],
                target=ui_targets['stok_hizi'],
                value_format_str="{:.2f}",
                delta_prefix=" kez"
            )

        with sub_col2:
            st.subheader("Finansal")
            st.metric(f"Yıllık Net Kâr/Zarar", f"${yillik_net_tasarruf:,.0f}")
            display_colored_progress(yillik_net_tasarruf if yillik_net_tasarruf > 0 else 0, ui_targets['tasarruf'])
        
            st.metric("Nakit Döngü Süresi (CCC)", f"{ccc_final:.0f} gün", f"{ccc_final - ccc_initial:.0f} gün", delta_color="inverse")

            if include_financial_breakdown:
                otif_cost, dead_stock_cost = self._calculate_financial_breakdown(pd.Series({'OTIF': final_otif}))
                st.metric("Düşük OTIF Maliyeti", f"$ {otif_cost:,.0f}")
                st.metric("Atıl Stok Maliyeti", f"$ {dead_stock_cost:,.0f}")

        with sub_col3:
            st.subheader("Stratejik")
            st.metric(
                label="Final Müşteri Memnuniyeti",
                value=f"{final_satisfaction:.1f}/10",
                delta=f"{final_satisfaction - self.base_data['initial_kpis']['musteri_memnuniyeti_skoru']:.1f}"
            )
        
            self._render_kpi_card(
                title="Final Esneklik Skoru",
                value=final_flexibility,
                initial_value=self.base_data['initial_kpis']['esneklik_skoru'],
                target=ui_targets['esneklik'],
                value_format_str="{:.1f}",
                delta_prefix="",
                help_text=f"Skor, OTIF'in <{self.config['simulation_thresholds']['esneklik_otif_esigi']:.0%} veya Aylık Kârın <${self.config['simulation_thresholds']['esneklik_kar_esigi']:,.0f} olması durumunda ayda {self.config['simulation_parameters']['esneklik_azalis_puani']} puan düşer; aksi halde {self.config['simulation_parameters']['esneklik_artis_puani']} puan artar. Çevik merkez gibi stratejiler başlangıç bonusu sağlar."
            )

    def _draw_production_comparison_chart(self, main_results, comp_results):
        st.subheader("🛠️ Operasyonel Etki Karşılaştırması: Üretim Dağılımı")
        df_main, df_comp = main_results['final_tesis_df'].copy(), comp_results['final_tesis_df'].copy()
        df_main['Strateji'], df_comp['Strateji'] = 'Ana Strateji', 'Karşılaştırma Stratejisi'
        fig = px.bar(pd.concat([df_main, df_comp]), x='Tesis Yeri', y='Fiili_Uretim_Ton', color='Strateji', barmode='group', title='Stratejilere Göre Tesislerdeki Nihai Üretim Miktarları (Ton)', labels={'Fiili_Uretim_Ton': 'Nihai Üretim (Ton)', 'Tesis Yeri': 'Tesis'}, color_discrete_map={'Ana Strateji': '#1f77b4', 'Karşılaştırma Stratejisi': '#ff7f0e'})
        st.plotly_chart(fig, use_container_width=True)

    def draw_comparison_view(self):
        main_results, comp_results = st.session_state.last_results, st.session_state.comparison_results
        specific_scenario_name = main_results['scenario_title'].split('|', 1)
        if len(specific_scenario_name) > 1:
            st.info(f"**Karşılaştırılan Senaryo:** {specific_scenario_name[1].strip()}")
        
        st.subheader("🏆 Karşılaştırma Özeti")
        base_profit_monthly, months = self.base_data['initial_kpis']['net_kar_aylik'], self.config['simulation_parameters']['months_in_year']
        yillik_kar_main = main_results['results_df']['Aylık Net Kar'].sum() - (base_profit_monthly * months)
        yillik_kar_comp = comp_results['results_df']['Aylık Net Kar'].sum() - (base_profit_monthly * months)
        kar_farki, otif_farki, esneklik_farki = yillik_kar_main - yillik_kar_comp, main_results['results_df'].iloc[-1]['OTIF'] - comp_results['results_df'].iloc[-1]['OTIF'], main_results['results_df'].iloc[-1]['Esneklik Skoru'] - comp_results['results_df'].iloc[-1]['Esneklik Skoru']
        def get_delta_text(diff, higher_is_better=True):
            if abs(diff) < 1e-6: return "Fark Yok", "off"
            return ("Ana Strateji lehine", "normal") if (diff > 0 and higher_is_better) or (diff < 0 and not higher_is_better) else ("Karşı. Stratejisi lehine", "inverse")
        kar_delta_text, kar_delta_color = get_delta_text(kar_farki)
        otif_delta_text, otif_delta_color = get_delta_text(otif_farki)
        esneklik_delta_text, esneklik_delta_color = get_delta_text(esneklik_farki)
        col1, col2, col3 = st.columns(3)
        with col1: st.metric(label="Yıllık Kâr Avantajı", value=f"${abs(kar_farki):,.0f}", delta=kar_delta_text, delta_color=kar_delta_color if kar_farki !=0 else "off")
        with col2: st.metric(label="Final OTIF Avantajı", value=f"{abs(otif_farki):.1%}", delta=otif_delta_text, delta_color=otif_delta_color if otif_farki !=0 else "off")
        with col3: st.metric(label="Final Esneklik Avantajı", value=f"{abs(esneklik_farki):.1f}", delta=esneklik_delta_text, delta_color=esneklik_delta_color if esneklik_farki !=0 else "off")
        with st.expander("Başlangıç Durumunu (As-Is) Görüntüle"): self._render_as_is_panel()
        st.markdown("---"); st.subheader("KPI'ların Zaman İçindeki Değişimi (Karşılaştırmalı)")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=main_results['results_df']['Ay'], y=main_results['results_df']['Aylık Net Kar'], name='Net Kar (Ana)', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=main_results['results_df']['Ay'], y=main_results['results_df']['OTIF'], name='OTIF (Ana)', yaxis='y2', line=dict(color='cyan')))
        fig.add_trace(go.Scatter(x=comp_results['results_df']['Ay'], y=comp_results['results_df']['Aylık Net Kar'], name='Net Kar (Karşı.)', line=dict(color='red', dash='dash')))
        fig.add_trace(go.Scatter(x=comp_results['results_df']['Ay'], y=comp_results['results_df']['OTIF'], name='OTIF (Karşı.)', yaxis='y2', line=dict(color='orange', dash='dash')))
        fig.update_layout(yaxis=dict(title="Aylık Net Kar ($)"), yaxis2=dict(title="OTIF Oranı", overlaying="y", side="right", range=[0.7, 1], tickformat=".0%"), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("12 Ayın Sonundaki Durum Karşılaştırması")
        col1, col2 = st.columns(2, gap="large")
        with col1: self._render_comparison_column(main_results, "Ana Strateji")
        with col2: self._render_comparison_column(comp_results, "Karşılaştırma Stratejisi")
        st.markdown("---"); self._draw_production_comparison_chart(main_results, comp_results)
        st.markdown("---"); st.subheader("👥 Paydaş Etki Analizi Karşılaştırması")
        col1, col2 = st.columns(2, gap="large")
        with col1: st.markdown("##### Ana Strateji Etkileri"); render_stakeholder_analysis(main_results['params'], main_results['scenario_title'], main_results['results_df'], main_results['results_df'].iloc[-1])
        with col2: st.markdown("##### Karşılaştırma Stratejisi Etkileri"); render_stakeholder_analysis(comp_results['params'], comp_results['scenario_title'], comp_results['results_df'], comp_results['results_df'].iloc[-1])
        with st.expander("Detaylı Analiz Tablolarını ve Senaryo Yönetimini Görüntüle"):
            st.info("Not: Senaryo yönetimi, 'Ana Strateji' sonuçları üzerinden yapılır."); self.draw_scenario_management_section()
        st.markdown("---")
        st.subheader("⚔️ Stratejik Kırılganlık Karşılaştırması")
        st.info(
            "Bu analiz, iki stratejinin de temel krizler karşısında ne kadar finansal hasar aldığını "
            "doğrudan karşılaştırır. Daha düşük çubuk, stratejinin o krize karşı daha dayanıklı olduğunu gösterir."
        )
        with st.spinner("Stratejilerin kriz dayanıklılığı karşılaştırılıyor..."):
            comparison_df = calculate_crisis_impact_comparison(
                main_results['params'], 
                comp_results['params'], 
                self.base_data, 
                self.config
            )

        if not comparison_df.empty:
            fig_comparison = px.bar(
                comparison_df,
                x="Kriz Senaryosu",
                y="Aylık Kâr Kaybı ($)",
                color="Strateji",
                barmode="group",
                title="Stratejilerin Krizlere Karşı Finansal Etkisi",
                labels={"Aylık Kâr Kaybı ($)": "Aylık Kâr Kaybı ($)"},
                color_discrete_map={
                    'Ana Strateji': '#1f77b4', 
                    'Karşılaştırma Stratejisi': '#ff7f0e'
                }
            )
            st.plotly_chart(fig_comparison, use_container_width=True)
        else:
            st.warning("Kırılganlık karşılaştırma analizi için veri üretilemedi.")

    def draw_single_view(self):
        results_data = st.session_state.last_results
        results_df, params, scenario_title = results_data["results_df"], results_data["params"], results_data["scenario_title"]
        
        st.subheader("KPI'ların Zaman İçindeki Değişimi")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=results_df['Ay'], y=results_df['Aylık Net Kar'], name='Aylık Net Kar', yaxis='y1'))
        fig.add_trace(go.Scatter(x=results_df['Ay'], y=results_df['Esneklik Skoru'], name='Esneklik Skoru', yaxis='y1'))
        fig.add_trace(go.Scatter(x=results_df['Ay'], y=results_df['OTIF'], name='OTIF', yaxis='y2'))
        fig.update_layout(yaxis=dict(title="Aylık Net Kar ($) / Esneklik Skoru"), yaxis2=dict(title="OTIF Oranı", overlaying="y", side="right", range=[0,1], tickformat=".0%"), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("12 Ayın Sonundaki Durum")
        col1, col2 = st.columns(2)
        with col1: self._render_as_is_panel()
        with col2: self._render_comparison_column(results_data, "Nihai Durum (To-Be)", include_financial_breakdown=False)

        st.markdown("---"); render_stakeholder_analysis(params, scenario_title, results_df, results_df.iloc[-1])
        with st.expander("Detaylı Analiz Tablolarını ve Senaryo Yönetimini Görüntüle"): self.draw_scenario_management_section()

    def draw_scenario_management_section(self):
        results_data = st.session_state.last_results
        results_df = results_data["results_df"]
        st.subheader("Senaryo Yönetimi")
        senaryo_notu = st.text_input("Bu senaryoya bir not ekle:", placeholder="Örn: Agresif G.Afrika stratejisi, 2 krizli")
        if st.button('Bu Senaryoyu Karşılaştırmak İçin Kaydet 💾', key='save_scenario'):
            final_row_save = results_df.iloc[-1]
            yillik_toplam_kar_zarar_save = results_df['Aylık Net Kar'].sum() - (self.base_data['initial_kpis']['net_kar_aylik'] * self.config['simulation_parameters']['months_in_year'])
            co2_tasarrufu_save = results_data.get('summary', {}).get('co2_savings', 0)
            st.session_state.scenarios.append({"Not": senaryo_notu, "Final OTIF": f"{final_row_save['OTIF']:.1%}", "Yıllık Kar/Zarar": f"${yillik_toplam_kar_zarar_save:,.0f}", "CO2 Tasarrufu": f"{co2_tasarrufu_save:,.0f} ton", "Final Esneklik": f"{final_row_save['Esneklik Skoru']:.1f}"})
            st.success(f"Senaryo '{senaryo_notu}' kaydedildi!")
        if st.session_state.scenarios:
            st.subheader("Kaydedilen Senaryoların Karşılaştırması")
            comparison_df = pd.DataFrame(st.session_state.scenarios)
            st.dataframe(comparison_df, use_container_width=True)
            @st.cache_data
            def convert_df_to_csv(df): return df.to_csv(index=False).encode('utf-8')
            st.download_button(label="Karşılaştırmayı CSV Olarak İndir", data=convert_df_to_csv(comparison_df), file_name='senaryo_karsilastirmasi.csv', mime='text/csv')
            if st.button("Karşılaştırmayı Temizle", key='clear_scenarios'): st.session_state.scenarios = []; st.rerun()
        st.subheader("Aylık Sonuç Tablosu ve Yaşanan Olaylar")
        def highlight_rows(row):
            if "Jüri Özel" in row["Olay Kaynağı"]: return ['background-color: #4B0082; color: white'] * len(row)
            if row["Olay Kaynağı"] == "Domino Etkisi": return ['background-color: #58181F'] * len(row)
            if row["Müdahale"] != "-": return ['background-color: #0A4A3A'] * len(row)
            return [''] * len(row)
        st.dataframe(results_df.style.apply(highlight_rows, axis=1).format(precision=2))
        st.subheader("Üretim Tesisleri Son Durum Analizi"); st.dataframe(results_data["final_tesis_df"].style.format({'Kapasite_Ton_Yil': '{:,.0f}', 'Kullanim_Orani': '{:.1%}', 'Fiili_Uretim_Ton': '{:,.0f}'}), use_container_width=True)

    def _create_kpi_donut_chart(self, value, target, title, color, value_suffix=""):
        """KPI'lar için görsel bir donut chart göstergesi oluşturur."""
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': title, 'font': {'size': 16}},
            number={'suffix': value_suffix, 'font': {'size': 24}},
            gauge={
                'axis': {'range': [0, target], 'visible': False},
                'bar': {'color': color, 'thickness': 1},
                'bgcolor': "#1E1E1E",
                'borderwidth': 0,
            }
        ))
        fig.update_layout(
            height=150,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            font={'color': 'white'}
        )
        return fig

    def draw_dashboard_page(self):
        """'Yönetim Paneli (Dashboard)' sekmesini çizer."""
        st.title("📊 Yönetim Paneli (Power BI Prototipi)")

        if 'last_results' not in st.session_state or not st.session_state.last_results:
            st.warning("Panel verilerini görmek için lütfen 'Ana Simülatör' sekmesinden bir simülasyon çalıştırın.")
            return

        is_comparison_run = 'comparison_results' in st.session_state and st.session_state.comparison_results
        
        if 'dashboard_view_choice' not in st.session_state:
            st.session_state.dashboard_view_choice = 'Ana Strateji'
        
        if not is_comparison_run and st.session_state.dashboard_view_choice == 'Karşılaştırma Stratejisi':
             st.session_state.dashboard_view_choice = 'Ana Strateji'

        if is_comparison_run:
            main_title = st.session_state.last_results.get('scenario_title', 'Ana Strateji')
            comp_title = st.session_state.comparison_results.get('scenario_title', 'Karşılaştırma Stratejisi')
            options = {main_title: 'Ana Strateji', comp_title: 'Karşılaştırma Stratejisi'}
            display_options = list(options.keys())
            
            try:
                current_choice_value = st.session_state.dashboard_view_choice
                titles_by_value = {v: k for k, v in options.items()}
                current_display_title = titles_by_value[current_choice_value]
                current_index = display_options.index(current_display_title)
            except (ValueError, KeyError):
                current_index = 0

            selected_display_option = st.selectbox("İncelenecek Senaryo:", display_options, index=current_index, key="dashboard_selector")
            
            new_choice_key = options[selected_display_option]
            if st.session_state.dashboard_view_choice != new_choice_key:
                st.session_state.dashboard_view_choice = new_choice_key
                st.rerun()

        if st.session_state.dashboard_view_choice == 'Karşılaştırma Stratejisi' and is_comparison_run:
            results_data = st.session_state.comparison_results
        else:
            results_data = st.session_state.last_results

        run_type = results_data.get("run_type", "single")

        if run_type == "monte_carlo":
            self.draw_monte_carlo_dashboard(results_data)
            return

        with st.expander("ℹ️ Modelin Felsefesi ve Temel Varsayımları"):
            st.info("""
            **Bu araç bir kahin değil, bir pusuladır.** Amacı, mutlak kesinlikte tahminler yapmak değil, farklı stratejilerin belirsizlikler karşısındaki **göreceli performansını** karşılaştırarak en doğru kararları vermenizi sağlamaktır.
            """)
            st.warning("""
            **Bilinçli Modelleme Kararları (Kırılgan Varsayımlarımız):**

            1.  **Akıllı Stok Optimizasyonu:** Bu prototip, stok devir hızındaki bir iyileşmenin getireceği envanter azaltımını, vaka metnindeki sorunlara dayanarak **kategori önceliklendirmesi** ile yapar. Vaka metninde "B kategorisinde fazla stok", "A kategorisinde stok yetersizliği" belirtildiği için, modelimiz envanter azaltma hedefine ulaşırken **önce B, sonra C kategorisindeki stokları hedefler ve yüksek kârlı A kategorisindeki stratejik stoklara en son dokunur.** Bu, basit bir orantısal dağılımdan çok daha gerçekçi ve iş odaklı bir yaklaşımdır.

            2.  **Olasılıksal Kriz Etkileri:** Krizlerin KPI'lar üzerindeki etkileri (örn: Liman Grevi'nin OTIF'e etkisi) ve müdahale maliyetleri, endüstri standartları ve vaka verileri baz alınarak **olasılıksal aralıklar (normal, uniform dağılım)** olarak modellenmiştir. Bu, her simülasyonun kendine özgü bir senaryo olmasını sağlar, ancak gerçek dünyadaki bir "kara kuğu" olayının etkisi daha farklı olabilir.

            Modelin gücü, bu varsayımların mutlak doğruluğundan çok, A stratejisinin B stratejisine kıyasla bu şoklara karşı ne kadar daha **dayanıklı veya esnek** olduğunu gösterebilmesindedir.
            """)
        
        st.markdown('<div class="dashboard-info-box">Bu panel, çalıştırılan son tekil simülasyonun sonuçlarını interaktif bir şekilde görselleştirir.</div>', unsafe_allow_html=True)

        summary = results_data.get("summary", {})
        results_df = results_data.get("results_df", pd.DataFrame())
        final_tesis_df = results_data.get("final_tesis_df", pd.DataFrame())
        params = results_data.get("params", {})
        scenario_title = results_data.get("scenario_title", "Bilinmeyen Senaryo")
        
        yillik_toplam_kar_zarar = summary.get('annual_profit_change', 0)
        final_otif = summary.get('final_otif', 0)
        final_esneklik = summary.get('final_flexibility', 0)
        co2_tasarrufu = summary.get('co2_savings', 0)

        if results_data.get("run_type") == "optimization":
            st.info(f"**Senaryo:** `{results_data.get('optimization_goal')}` hedefi için motorun bulduğu **Optimal Strateji**")
        else:
            st.info(f"**Senaryo:** {scenario_title}")

        st.markdown("### Genel Performans Karnesi")
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric("Yıllık Toplam Kar/Zarar", f"${yillik_toplam_kar_zarar:,.0f}", f"{yillik_toplam_kar_zarar / (self.base_data['initial_kpis']['net_kar_aylik']*12):.1%}" if self.base_data['initial_kpis']['net_kar_aylik'] > 0 else "N/A")
        with kpi2:
            st.metric("Final OTIF", f"{final_otif:.1%}")
        with kpi3:
            st.metric("Final Esneklik Skoru", f"{final_esneklik:.1f}/10")
        with kpi4:
            st.metric("Yıllık CO2 Tasarrufu", f"{co2_tasarrufu:,.0f} ton")

        st.markdown("---")
        self.draw_dashboard_charts(results_df, final_tesis_df)
        st.markdown("---")
        st.subheader("Stratejik Risk Matrisi")
        st.info(
            "**Not:** Bu analiz, stratejik bir **'stres testi'** işlevi görür. Şu anda **incelenen senaryonun** "
            "temel parametrelerini (örn: Tek Kaynak Oranı) baz alarak, farklı **üretim stratejilerinin** "
            "('Mevcut', 'G. Afrika', 'Türkiye') standart krizler karşısındaki finansal kırılganlığını test eder. "
            "Sonuç, hangi üretim yapısının hangi krize karşı ne kadar dayanıklı olduğunu gösteren bir ısı haritasıdır.",
            icon="ℹ️"
        )
        if st.button("Risk Matrisini Hesapla ve Göster"):
            with st.spinner("Risk matrisi farklı senaryolar için hesaplanıyor... (Bu işlem 10-15 saniye sürebilir)"):
                st.session_state.risk_matrix_df = calculate_risk_matrix(self.base_data, self.config, params)
        if st.session_state.risk_matrix_df is not None:
            st.plotly_chart(plot_risk_heatmap(st.session_state.risk_matrix_df), use_container_width=True)
            if st.button("Risk Matrisini Gizle", key="clear_risk_matrix"):
                st.session_state.risk_matrix_df = None
                st.rerun()

        st.markdown("---")
        st.subheader("🔍 Derinlemesine Finans ve Envanter Analizi")
        final_erp_data = results_data.get('final_erp_data')
        if final_erp_data is None or final_erp_data.empty:
            st.warning("Derinlemesine analizleri görüntülemek için lütfen kenar çubuğundan ERP verisini çekip bir simülasyon çalıştırın.")
        else:
            final_row_for_breakdown = pd.Series({'OTIF': final_otif})
            tabs = st.tabs([
                "**💰 Finansal Zeka Paneli**", 
                "**📦 Stok ve Talep Riskleri**", 
                "**📊 ABC (Pareto) Analizi**",
                "**💸 Finansal Kayıp Analizi**",
                "**🏗️ Lojistik Fizibilite**"
            ])
            with tabs[0]:
                self.draw_erp_financial_analysis(results_data)
            with tabs[1]:
                self.draw_stock_demand_risk_radar(results_data)
            with tabs[2]:
                self.draw_abc_analysis_section(results_data)
            with tabs[3]:
                self._render_full_financial_breakdown_section(final_row_for_breakdown)
            with tabs[4]:
                self.draw_warehouse_feasibility_analysis(results_data)

    def draw_warehouse_feasibility_analysis(self, results_data):
        feasibility_data = results_data.get('warehouse_feasibility')
        composition_data = results_data.get('stock_composition')

        if not feasibility_data or not composition_data:
            st.warning("Fizibilite ve kompozisyon analizi için veri bulunamadı.")
            return

        st.subheader("1. Teşhis: Depo Taşıma Kapasitesinin Kök Neden Analizi")
        st.caption("Mevcut envanterin depoda ne kadar yer kapladığını ve bu yükün hangi ürün kategorilerinden kaynaklandığını analiz eder.")
    
        col1, col2 = st.columns([1, 2])
    
        with col1:
            total_required = feasibility_data.get('gereken_hacim_ton', 0)
            total_capacity = feasibility_data.get('toplam_kapasite_ton', 0)
            overflow = total_required - total_capacity
        
            st.metric("Gereken Toplam Hacim", f"{total_required:,.0f} ton")
            st.metric("Mevcut Toplam Kapasite", f"{total_capacity:,.0f} ton")
        
            if overflow > 0:
                st.metric("Kapasite Aşımı Miktarı", f"{overflow:,.0f} ton", "DİKKAT", delta_color="inverse")
            else:
                st.metric("Boş Kapasite", f"{-overflow:,.0f} ton", "YETERLİ", delta_color="normal")

        with col2:
            comp_df = pd.DataFrame(list(composition_data.items()), columns=['Kategori', 'Hacim (ton)'])
            comp_df = comp_df.sort_values(by='Hacim (ton)', ascending=False)
        
            fig_comp = px.bar(comp_df, x='Kategori', y='Hacim (ton)', 
                              text_auto='.2s', title="Gereken Hacmin Kategori Dağılımı",
                              color='Kategori', color_discrete_map={'A': '#1f77b4', 'B': '#ff7f0e', 'C': '#d62728'})
            fig_comp.update_layout(showlegend=False)
            st.plotly_chart(fig_comp, use_container_width=True)

        st.markdown("---")

        st.subheader("2. Etki: Kapasiteye Karşı İhtiyaç Görselleştirmesi")
        st.caption("Bu grafik, gereken toplam hacmin mevcut kapasiteyi ne ölçüde aştığını ve bu aşımın hangi kategorilerden geldiğini net bir şekilde gösterir.")

        plot_df = pd.DataFrame([
            {'Kategori': 'A', 'Hacim': composition_data.get('A', 0)},
            {'Kategori': 'B', 'Hacim': composition_data.get('B', 0)},
            {'Kategori': 'C', 'Hacim': composition_data.get('C', 0)},
        ])
    
        fig_impact = go.Figure()
        fig_impact.add_trace(go.Bar(
            y=['Depo Durumu'],
            x=plot_df[plot_df['Kategori']=='A']['Hacim'],
            name='A Kategorisi',
            orientation='h',
            marker=dict(color='#1f77b4', line=dict(color='white', width=1))
        ))
        fig_impact.add_trace(go.Bar(
            y=['Depo Durumu'],
            x=plot_df[plot_df['Kategori']=='B']['Hacim'],
            name='B Kategorisi',
            orientation='h',
            marker=dict(color='#ff7f0e', line=dict(color='white', width=1))
        ))
        fig_impact.add_trace(go.Bar(
            y=['Depo Durumu'],
            x=plot_df[plot_df['Kategori']=='C']['Hacim'],
            name='C Kategorisi',
            orientation='h',
            marker=dict(color='#d62728', line=dict(color='white', width=1))
        ))

        fig_impact.add_vline(x=total_capacity, line_width=3, line_dash="dash", line_color="white",
                            annotation_text="Kapasite Limiti", annotation_position="top left",
                            annotation_font_size=12, annotation_font_color="white")

        fig_impact.update_layout(barmode='stack', title_text='Gereken Hacim vs. Kapasite Limiti',
                                xaxis_title="Hacim (ton)", yaxis_title="",
                                legend_title="Ürün Kategorisi",
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_impact, use_container_width=True)
    
        st.markdown("---")

        st.subheader("3. Reçete: Stratejik Çözüm Yolları")
        st.caption("Tespit edilen fizibilite riskini ortadan kaldırmak için seçilebilecek iki ana stratejik yol ve bunların sonuçları:")

        sol1, sol2 = st.columns(2)
        with sol1:
            st.markdown("##### 🌱 Operasyonel Verimlilik (Önerilen Yol)")
            st.markdown("""
            Bu yol, ek yatırım gerektirmeden, mevcut kaynakları daha akıllı kullanarak sorunu çözer.
            - **Tahmin Doğruluğunu Artırın:** Daha iyi tahmin, daha az belirsizlik demektir. Bu da ihtiyaç duyulan güvenlik stoğunu azaltarak depoda doğrudan yer açar.
            - **Stok Stratejisini Değiştirin:** 'SKU Optimizasyonu' veya 'Fazla Stokları Erit' gibi stratejilerle, kâr getirmeyen ve depoda yer kaplayan atıl ürünlerden kurtulun.
            """)
        with sol2:
            st.markdown("##### 🏗️ Sermaye Yatırımı (Alternatif Yol)")
            st.markdown("""
            Mevcut operasyonel yapıyı koruyarak, fiziksel altyapıyı büyütme seçeneğidir.
            - **Depo Kapasitesini Artırın:** Tespit edilen **`{fark_ton:,.0f} ton`**'luk ek ihtiyacı karşılamak için yeni depo kiralama veya inşa etme projeleri başlatılmalıdır.
            - **Maliyet Analizi:** Bu seçeneğin getireceği sermaye yatırım maliyeti (CAPEX) ve operasyonel giderler (OPEX) ayrıca detaylı olarak analiz edilmelidir.
            """.format(fark_ton=overflow if overflow > 0 else 0))

    def _get_delta_color_and_sign(self, delta, higher_is_better):
        if abs(delta) < 1e-9: return "gray", ""
        is_positive_change = (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better)
        color = "#28a745" if is_positive_change else "#dc3545"
        sign = "▲" if delta > 0 else "▼"
        return color, sign

    def draw_monte_carlo_dashboard(self, results_data):
        st.info(f"Bu panel, çalıştırılan **{results_data['scenario_title']}** senaryosunun olasılıksal sonuçlarını detaylı olarak analiz eder.")

        mc_runs_data = results_data["mc_results"]
        if not mc_runs_data:
            st.error("Monte Carlo simülasyonu için sonuç verisi bulunamadı.")
            return
        
        results_df = pd.DataFrame(mc_runs_data)
        num_runs = len(results_df)

        st.markdown(f"### Olasılıksal Performans Karnesi ({num_runs} Tekrar)")
        kpi_defs = {
            "annual_profits": {"label": "Yıllık Net Kâr/Zarar", "format": "${x:,.0f}", "initial_key": "net_kar_aylik", "higher_is_better": True},
            "final_otifs": {"label": "Final OTIF", "format": "{x:.1%}", "initial_key": "otif", "higher_is_better": True},
            "final_flexibility": {"label": "Final Esneklik Skoru", "format": "{x:.1f}", "initial_key": "esneklik_skoru", "higher_is_better": True},
            "final_satisfaction": {"label": "Final Müşteri Memnuniyeti", "format": "{x:.1f}", "initial_key": "musteri_memnuniyeti_skoru", "higher_is_better": True}
        }
        
        col_kpi, col_avg, col_med, col_p10, col_p90 = st.columns([2.5, 2, 2, 2, 2])
        col_avg.markdown("<p style='text-align: center; font-weight: bold;'>Ortalama Sonuç</p>", unsafe_allow_html=True)
        col_med.markdown("<p style='text-align: center; font-weight: bold;'>Medyan (Beklenen)</p>", unsafe_allow_html=True)
        col_p10.markdown("<p style='text-align: center; font-weight: bold;'>Kötümser (P10)</p>", unsafe_allow_html=True)
        col_p90.markdown("<p style='text-align: center; font-weight: bold;'>İyimser (P90)</p>", unsafe_allow_html=True)
        st.markdown("<hr style='margin-top: -10px; margin-bottom: 10px;'>", unsafe_allow_html=True)

        for key, kpi in kpi_defs.items():
            if key not in results_df.columns: continue
            c_kpi, c_avg, c_med, c_p10, c_p90 = st.columns([2.5, 2, 2, 2, 2])
            data = results_df[key]
            initial_val = self.base_data['initial_kpis'][kpi['initial_key']] * (12 if key == 'annual_profits' else 1)
            mean_val, median_val, p10_val, p90_val = data.mean(), data.median(), data.quantile(0.10), data.quantile(0.90)
            
            c_kpi.markdown(f"<div style='height: 60px; display: flex; align-items: center; font-weight: bold;'>{kpi['label']}</div>", unsafe_allow_html=True)

            def create_metric_cell(value, base_value, base_text, kpi_info):
                delta = value - base_value
                color, sign = self._get_delta_color_and_sign(delta, kpi_info['higher_is_better'])
                if '$' in kpi_info['format']:
                    delta_str = f"${abs(delta):,.0f}"
                elif '%' in kpi_info['format']:
                    delta_str = f"{abs(delta):.1%}"
                else: 
                    delta_str = f"{abs(delta):.1f}"
                return f"<div style='text-align: center; line-height: 1.2;'><span style='font-size: 1.5em; font-weight: bold;'>{kpi_info['format'].format(x=value)}</span><br><span style='font-size: 0.8em; color: {color};'>{sign} {delta_str} {base_text}</span></div>"

            c_avg.markdown(create_metric_cell(mean_val, initial_val, "(vs Başlangıç)", kpi), unsafe_allow_html=True)
            c_med.markdown(f"<div style='text-align: center; font-size: 1.5em; font-weight: bold; line-height: 60px;'>{kpi['format'].format(x=median_val)}</div>", unsafe_allow_html=True)
            c_p10.markdown(create_metric_cell(p10_val, median_val, "(vs Medyan)", kpi), unsafe_allow_html=True)
            c_p90.markdown(create_metric_cell(p90_val, median_val, "(vs Medyan)", kpi), unsafe_allow_html=True)
            st.markdown("<hr style='margin-top: 10px; margin-bottom: 10px;'>", unsafe_allow_html=True)

        st.markdown("### Hedef Başarı Olasılıkları")
        with st.container(border=True):
            st.markdown("##### Olasılık Hedeflerini Ayarla")
            t_col1, t_col2, t_col3 = st.columns(3)
            with t_col1: user_target_otif = st.number_input("OTIF Hedefi (%)", min_value=0.0, max_value=100.0, value=95.0, step=1.0, format="%.1f")
            with t_col2: user_target_profit = st.number_input("Yıllık Kâr Hedefi ($M)", min_value=-20.0, value=5.0, step=0.5, format="%.1f") * 1_000_000
            with t_col3: user_target_flex = st.number_input("Esneklik Skoru Hedefi", min_value=0.0, max_value=10.0, value=7.0, step=0.1, format="%.1f")
            st.markdown("---"); g_col1, g_col2, g_col3 = st.columns(3)

        def create_gauge(col, value, title, target_display, target_val, value_suffix, range_max):
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=value,
                number={'suffix': value_suffix, 'font': {'size': 36}},
                title={'text': f"<b>{title}</b><br><span style='font-size:0.8em;color:gray'>Hedef: {target_display}</span>", 'font': {"size": 16}},
                gauge={'axis': {'range': [None, range_max], 'tickwidth': 1, 'tickcolor': "darkgray"},
                       'bar': {'color': "#00b0f0", 'thickness': 0.3},
                       'bgcolor': "rgba(0,0,0,0)", 'borderwidth': 1, 'bordercolor': "gray",
                       'steps': [{'range': [0, target_val * 0.75], 'color': 'rgba(211, 47, 47, 0.5)'}, {'range': [target_val * 0.75, target_val], 'color': 'rgba(255, 193, 7, 0.5)'}],
                       'threshold': {'line': {'color': "#4CAF50", 'width': 3}, 'thickness': 0.8, 'value': target_val}}))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, height=250, margin=dict(l=30, r=30, t=65, b=20))
            col.plotly_chart(fig, use_container_width=True)

        prob_otif = (results_df['final_otifs'] * 100 >= user_target_otif).mean() * 100
        prob_profit = (results_df['annual_profits'] >= user_target_profit).mean() * 100
        prob_flex = (results_df['final_flexibility'] >= user_target_flex).mean() * 100
        
        with g_col1: create_gauge(g_col1, prob_otif, "OTIF Başarı Olasılığı", f"{user_target_otif:.0f}%", user_target_otif, "%", 100)
        with g_col2: create_gauge(g_col2, prob_profit, "Kâr Hedefi Olasılığı", f"${user_target_profit/1e6:.1f}M", user_target_profit, "%", 100)
        with g_col3: create_gauge(g_col3, prob_flex, "Esneklik Hedefi Olasılığı", f"{user_target_flex:.1f}", user_target_flex, "%", 100)

        st.markdown("---")
        st.subheader("İlişkisel Analiz: Kâr-OTIF Dengesi")
        st.caption("Her bir nokta, bir simülasyon tekrarını temsil eder. Bu grafik, OTIF ve Kâr arasındaki değiş-tokuş ilişkisini (trade-off) ve Domino Etkisinin bu dengeyi nasıl bozduğunu gösterir.")
        
        results_df['domino_triggered'] = results_df['realized_events'].apply(
            lambda events: any(e['source'] == 'Domino Etkisi' for e in events)
        )
        
        fig_scatter = px.scatter(
            results_df,
            x='final_otifs',
            y='annual_profits',
            color='domino_triggered',
            title='Yıllık Kâr vs. Final OTIF (Domino Etkisine Göre Renklendirilmiş)',
            labels={'final_otifs': 'Final OTIF', 'annual_profits': 'Yıllık Net Kâr/Zarar ($)', 'domino_triggered': 'Domino Etkisi Tetiklendi mi?'},
            hover_data=['run_id'],
            color_discrete_map={True: '#d62728', False: '#1f77b4'},
            opacity=0.7
        )
        fig_scatter.update_xaxes(tickformat=".1%")
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Nedensellik Analizi: Başarı ve Başarısızlığın Kök Nedenleri")
        st.caption("Bu analiz, en iyi ve en kötü sonuçlara yol açan krizlerin hangileri olduğunu karşılaştırarak en büyük risk faktörlerini ortaya koyar.")
        
        profit_p10 = results_df['annual_profits'].quantile(0.10)
        profit_p90 = results_df['annual_profits'].quantile(0.90)

        worst_runs = results_df[results_df['annual_profits'] <= profit_p10]
        best_runs = results_df[results_df['annual_profits'] >= profit_p90]

        def get_event_frequencies(df_slice):
            if df_slice.empty: return Counter()
            all_events = [event['event'] for run_events in df_slice['realized_events'] for event in run_events]
            return Counter(all_events)

        worst_freq = get_event_frequencies(worst_runs)
        best_freq = get_event_frequencies(best_runs)
        
        all_event_names = sorted(list(set(worst_freq.keys()) | set(best_freq.keys())))
        
        plot_data = []
        for event in all_event_names:
            if len(worst_runs) > 0:
                plot_data.append({'Grup': 'En Kötü %10', 'Kriz Olayı': event, 'Görülme Sıklığı (%)': (worst_freq.get(event, 0) / len(worst_runs)) * 100})
            if len(best_runs) > 0:
                plot_data.append({'Grup': 'En İyi %10', 'Kriz Olayı': event, 'Görülme Sıklığı (%)': (best_freq.get(event, 0) / len(best_runs)) * 100})

        if plot_data:
            freq_df = pd.DataFrame(plot_data)
            fig_freq = px.bar(
                freq_df,
                x='Kriz Olayı',
                y='Görülme Sıklığı (%)',
                color='Grup',
                barmode='group',
                title='En İyi ve En Kötü Senaryolarda Krizlerin Görülme Sıklığı',
                labels={'Görülme Sıklığı (%)': 'Görülme Sıklığı (%)'},
                color_discrete_map={'En Kötü %10': '#d62728', 'En İyi %10': '#2ca02c'}
            )
            fig_freq.update_yaxes(ticksuffix="%")
            st.plotly_chart(fig_freq, use_container_width=True)
        else:
            st.info("Kök Neden Analizi, en iyi ve en kötü sonuçlara hangi krizlerin yol açtığını gösterir. Bu analiz için, çalıştırılan senaryonun en az bir kriz olayı içermesi gerekmektedir. Lütfen 'Ana Simülatör'den kriz içeren bir senaryo seçip Monte Carlo'yu tekrar çalıştırın.")

    def draw_dashboard_charts(self, results_df, final_tesis_df):
        with st.container():
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("##### Aylık Net Kar Değişimi")
                st.bar_chart(results_df[['Ay', 'Aylık Net Kar']].set_index('Ay'))
            with col2:
                st.markdown("##### Hizmet Seviyesi ve Memnuniyet")
                st.line_chart(results_df[['Ay', 'OTIF', 'Müşteri Memnuniyeti']].set_index('Ay'))

            st.markdown("---")

            chart_col1, chart_col2 = st.columns([2, 3])
            with chart_col1:
                st.markdown("##### Gelir Dağılımı (Vaka Verisi)")
                source = pd.DataFrame({"Segment": ["İlk 10 Müşteri", "Diğer Müşteriler"], "Gelir Payı (%)": [60, 40]})
                bar_chart = alt.Chart(source).mark_bar().encode(x=alt.X('Segment', axis=alt.Axis(title='Müşteri Segmenti', labelAngle=0)), y=alt.Y('Gelir Payı (%):Q', axis=alt.Axis(title='Gelir Payı (%)')), color=alt.Color('Segment', legend=None)).properties(height=400)
                st.altair_chart(bar_chart, use_container_width=True)
            with chart_col2:
                st.markdown("##### Üretim Dağılımı (İnteraktif Harita)")
                interactive_map = create_interactive_map(final_tesis_df)
                if interactive_map:
                    st_folium(interactive_map, use_container_width=True, height=400)
                else:
                    st.warning("Harita verisi oluşturulamadı.")

    def draw_erp_financial_analysis(self, results_data):
        initial_erp_data = st.session_state.get('erp_data')
        final_erp_data = results_data.get('final_erp_data')
        
        if initial_erp_data is None:
            st.warning("Finansal paneli görüntülemek için kenar çubuğundan ERP verisi yüklenmelidir.")
            return

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("###### Simülasyon Öncesi (As-Is)")
            render_financial_intelligence_panel(initial_erp_data, key_prefix="initial")
        with col2:
            st.markdown("###### Simülasyon Sonrası (To-Be)")
            if final_erp_data is not None and not final_erp_data.empty:
                render_financial_intelligence_panel(final_erp_data, key_prefix="final")
            else:
                st.info("Simülasyon sonrası durumu görmek için bir senaryo çalıştırın.")

    def draw_stock_demand_risk_radar(self, results_data):
        final_erp_data = results_data.get('final_erp_data')
        risk_metrics = analyze_stock_and_demand_risk(final_erp_data)

        if not risk_metrics:
            st.info("Risk analizi için veri bulunamadı.")
            return
            
        st.caption("Simülasyon sonrası envanter durumuna göre potansiyel stoksuz kalma ve atıl sermaye riskleri.")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🚨 Stok Yetersizliği Riski (SKU)", f"{risk_metrics['yetersiz_stok_sku_sayisi']} adet")
        col2.metric("💸 Kaybedilen Potansiyel Ciro", f"${risk_metrics['toplam_kaybedilen_ciro']:,.0f}")
        col3.metric("📦 Fazla Stok Riski (SKU)", f"{risk_metrics['fazla_stok_sku_sayisi']} adet")
        col4.metric("💰 Atıl Sermaye (Fazla Stok)", f"${risk_metrics['toplam_atil_sermaye']:,.0f}")
        
        st.markdown("---")
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Stoksuz Kalma Riski En Yüksek 5 Ürün**")
            st.dataframe(risk_metrics['top_yetersiz_df'], use_container_width=True)
        with col_b:
            st.markdown("**Atıl Sermaye Riski En Yüksek 5 Ürün**")
            st.dataframe(risk_metrics['top_fazla_df'], use_container_width=True)
                
    def draw_abc_analysis_section(self, results_data):
        st.caption("Simülasyon sonrası envanter durumuna göre ürünlerin ciroya katkısının yeniden analizi.")
        final_erp_data = results_data.get('final_erp_data')
        abc_df, summary_df = perform_abc_analysis(final_erp_data)
        
        if summary_df is not None and not summary_df.empty:
            fig = plot_abc_analysis(summary_df)
            st.plotly_chart(fig, use_container_width=True)
            summary_text = [
                f"**{row['ABC_Kategori']} Grubu:** Aktif SKU'ların **%{row['SKU_Yuzdesi']:.1f}**'unu oluşturup cironun **%{row['Ciro_Yuzdesi']:.1f}**'sini sağlıyor."
                for _, row in summary_df.iterrows()
            ]
            st.info(' '.join(summary_text))
        else:
            st.info("ABC Analizi için gösterilecek aktif ürün bulunamadı (Tüm stoklar tükenmiş olabilir).")

    def draw_architecture_page(self):
        """'Dijital Dönüşüm Mimarisi' sekmesini çizer.

        Mevcut ve önerilen sistem mimarisini gösteren "As-Is" ve "To-Be"
        diyagramlarını render eder.
        """
        st.title("Kimoto Solutions: Dijital Dönüşüm Yol Haritası")
        st.info("Bu bölüm, simülatörün tek başına bir araç olmadığını, daha büyük bir dijital dönüşüm stratejisinin merkezi bir bileşeni olduğunu göstermektedir.")
        
        tab1, tab2 = st.tabs(["Mevcut Durum (Sorunlu Akış)", "Önerilen Gelecek (Optimize Akış)"])
        with tab1:
            render_before_diagram()
        with tab2:
            render_after_diagram(
                params=st.session_state.get('params_main'),
                results_data=st.session_state.get('last_results')
            )
        
    def draw_rollout_page(self):
        """'Uygulama Yol Haritası' sekmesini çizer.

        Önerilen projenin aşamalı uygulama planını bir Gantt şeması ve
        detaylı faz açıklamaları ile gösterir.
        """
        render_rollout_plan()