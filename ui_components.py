import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
from config import CONFIG, URETIM_STRATEJILERI, STOK_STRATEJILERI, LOCATION_COORDINATES
from event_library import EVENT_LIBRARY

def display_colored_progress(value, target):
    """Hedefe göre renkli bir progress bar gösterir."""
    if target == 0 and value == 0: ratio = 1.0
    elif target == 0: ratio = 0.0
    else: ratio = value / target
    
    color = "#F5A623" 
    if ratio < 0.8: color = "#D0021B" 
    elif ratio >= 1.0: color = "#7ED321" 

    if ratio > 1.2: color = "#4CAF50" 
    
    st.markdown(f"""
    <div style="background-color: #262730; border-radius: 5px; padding: 2px; margin-top: -10px; margin-bottom: 10px;">
        <div style="background-color: {color}; width: {min(ratio, 1.0) * 100}%; border-radius: 5px; text-align: right; color: black; font-weight: bold; padding-right: 5px; height: 20px; line-height: 20px;">
            {int(ratio*100)}%
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_before_diagram():
    st.markdown("#### Mevcut Durum: Reaktif ve Silo Halindeki Yapı")
    st.markdown("""<style>.box-bad { border: 2px solid #822828; background-color: #260e0e; border-radius: 5px; padding: 15px; text-align: center; margin: 10px 0; }.arrow-broken { text-align: center; color: #822828; font-size: 24px; line-height: 80px; }</style>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1: st.markdown('<div class="box-bad">⚠️ <strong>Excel\'de Manuel Tahmin</strong><br><small>Doğruluk: %55</small></div>', unsafe_allow_html=True); st.markdown('<p class="arrow-broken">⇣</p>', unsafe_allow_html=True); st.markdown('<div class="box-bad"><strong>Satış Departmanı</strong><br><small>(Kendi Planlaması)</small></div>', unsafe_allow_html=True)
    with col2: st.markdown('<p style="line-height: 250px; text-align:center; font-size: 20px; color: #822828;">(Veri Akışı Kopuk)</p>', unsafe_allow_html=True)
    with col3: st.markdown('<div class="box-bad"><strong>Yetersiz ERP</strong><br><small>(Gecikmeli Veri)</small></div>', unsafe_allow_html=True); st.markdown('<p class="arrow-broken">⇣</p>', unsafe_allow_html=True); st.markdown('<div class="box-bad"><strong>Üretim Planlama</strong><br><small>(Reaktif Kararlar)</small></div>', unsafe_allow_html=True)

def render_after_diagram(params=None, results_data=None):
    st.markdown("#### Önerilen Gelecek: Entegre ve Proaktif Yapı")
    st.markdown("""<style>.box-good { border: 2px solid #285182; border-radius: 5px; padding: 10px; text-align: center; margin-bottom: 10px; height: 120px; display: flex; justify-content: center; align-items: center; flex-direction: column; background-color: #0F1116; }.box-our-tool { border: 2px solid #00b0f0; background-color: #0d1e2d; border-radius: 5px; padding: 10px; text-align: center; margin-bottom: 10px; height: 120px; display: flex; justify-content: center; align-items: center; flex-direction: column; }.arrow-good { font-size: 24px; text-align: center; color: #285182; margin: 0; padding: 0; line-height: 120px; }</style>""", unsafe_allow_html=True)

    kpi_cfg = CONFIG['kpi_defaults']
    base_accuracy = kpi_cfg['talep_tahmin_dogrulugu']
    calculated_accuracy = base_accuracy 

    if params:
        model_cfg = CONFIG['strategy_impacts']['tahmin_modeli']
        tahmin_algoritmasi = params.get('tahmin_algoritmasi', list(model_cfg['algoritmalar'].keys())[0])
        bonus = model_cfg['algoritmalar'][tahmin_algoritmasi]['bonus']
        for kaynak in model_cfg['veri_kaynaklari'].keys():
            if params.get(kaynak, False):
                 bonus += model_cfg['veri_kaynaklari'][kaynak]['bonus']
        calculated_accuracy = min(0.99, base_accuracy + bonus)

    tahmin_text = f"<strong>AI Destekli Tahminleme</strong><br><small>Tahmin Doğruluğu: {base_accuracy:.0%} → <b>{calculated_accuracy:.0%}</b></small>"
    
    sim_result_text = "Strateji & Kriz Optimizasyon Motoru"
    
    if results_data and 'results_df' in results_data:
        results_df = results_data['results_df']
        summary = results_data.get('summary', {})
        yillik_kar_zarar = summary.get('annual_profit_change', 0)
        sim_result_text += f"<hr style='margin:5px 0; border-color: #285182;'><small>Senaryo Etkisi: <b>${yillik_kar_zarar:,.0f}</b></small>"
    
    col1, col2, col3, col4, col5 = st.columns([2,0.5,2,0.5,2])
    with col1: st.markdown('<div class="box-good"><strong>Veri Kaynakları</strong><br><small>Satış, Stok, Pazar</small></div>', unsafe_allow_html=True)
    with col2: st.markdown('<p class="arrow-good">→</p>', unsafe_allow_html=True)
    with col3: st.markdown(f'<div class="box-good">{tahmin_text}</div>', unsafe_allow_html=True)
    with col4: st.markdown('<p class="arrow-good">→</p>', unsafe_allow_html=True)
    with col5: st.markdown('<div class="box-good"><strong>Entegre ERP</strong><br><small>Ana Veri Yönetimi</small></div>', unsafe_allow_html=True)
    
    st.markdown('<p class="arrow-good" style="text-align:right; margin-right: 50px;">↓</p>', unsafe_allow_html=True)
    
    col6, col7, col8, col9, col10 = st.columns([2,0.5,2,0.5,2])
    with col6: st.markdown('<div class="box-good"><strong>Raporlama</strong><br><small>(Power BI / Tableau)</small></div>', unsafe_allow_html=True)
    with col7: st.markdown('<p class="arrow-good">←</p>', unsafe_allow_html=True)
    with col8: st.markdown(f'<div class="box-our-tool"><strong>Karar Destek Sistemi (Bu Simülatör)</strong><br><small>{sim_result_text}</small></div>', unsafe_allow_html=True)
    with col9: st.markdown('<p class="arrow-good">←</p>', unsafe_allow_html=True)
    with col10: st.markdown('<div class="box-good"><strong>Üretim Yürütme (MES)</strong><br><small>Operasyonel Planlama</small></div>', unsafe_allow_html=True)
    
    with st.expander("ℹ️ Karar Destek Sisteminin Rolü ve Detayları"):
        st.markdown("""**GİRDİLER (ERP ve Tahminlemeden Gelen):**\n- Anlık stok seviyeleri\n- Güncel üretim kapasiteleri\n- AI/ML modülünden gelen iyileştirilmiş talep tahminleri\n\n**İŞLEME (Bu Simülatörün Yaptığı):**\n- Seçilen uzun vadeli stratejileri ve kriz senaryolarını 12 ay boyunca simüle eder.\n- OTIF, net kâr, esneklik, müşteri memnuniyeti ve CO2 üzerindeki bütünsel etkileri hesaplar.\n- Farklı strateji kombinasyonlarının getiri ve risklerini karşılaştırır.\n\n**ÇIKTILAR (MES ve Raporlamaya Giden Karar Önerisi):**\n- **Optimal Strateji Paketi:** Belirlenen hedeflere en uygun strateji.\n- **Risk Raporu:** Seçilen stratejinin en zayıf olduğu kriz senaryoları.\n- **Finansal ve Operasyonel Projeksiyon:** 12 aylık tahmini KPI dökümü.""")

def _render_strategy_based_stakeholder_issues(params):
    """Sadece seçilen stratejilere dayalı statik paydaş etkilerini render eder."""
    any_issue_found = False
    
    if params.get('ozel_sku_modu'):
        any_issue_found = True
        st.warning("""
        **Karmaşıklık ve Müşteri İlişkileri Riski (Strateji: Özel SKU Modu)**
        - **Tespit:** Özel SKU üretimi, standart operasyonel akışları karmaşıklaştırır, planlama ve üretim ekipleri üzerinde ek yük oluşturur. Bu müşterilerle daha yakın ve hassas bir iletişim yönetimi gerektirir.
        - **Stratejik Öneri:** Özel SKU süreci için ayrı bir proje ekibi ve iletişim protokolü oluşturulmalı, standart üretim üzerindeki potansiyel gecikme etkileri önceden planlanmalıdır.
        """)
    if params.get('mevsimsellik_etkisi'):
        any_issue_found = True
        st.warning("""
        **Operasyonel Stres Riski (Strateji: Mevsimsel Zirve)**
        - **Tespit:** Zirve dönemlerde artan iş yükü, depo, lojistik ve üretim ekipleri üzerinde aşırı stres, yorgunluk ve iş güvenliği riski yaratabilir.
        - **Stratejik Öneri:** Zirve dönemler için geçici personel alımı, esnek çalışma saatleri ve ek prim gibi teşvikler planlanmalı, operasyonel hedefler gerçekçi tutulmalıdır.
        """)
    uretim_s = params.get('uretim_s')
    if uretim_s in [URETIM_STRATEJILERI[1], URETIM_STRATEJILERI[2]]:
        any_issue_found = True
        hedef_ulke = "Güney Afrika" if uretim_s == URETIM_STRATEJILERI[1] else "Türkiye"
        st.warning(f"""
        **İstihdam Etkisi Uyarısı (Strateji: {hedef_ulke} Çevik Merkezi)**
        - **Tespit:** Bu strateji, üretimin bir kısmını Hindistan'dan {hedef_ulke}'ye kaydıracaktır. Bu durum, Hindistan'daki tesislerin üretim hacmini ve mevcut iş gücü üzerindeki potansiyel etkisini gündeme getirmektedir.
        - **Stratejik Öneri (Değişim Yönetimi):** Proaktif iletişim, yeniden yeteneklendirme programları ve adil destek paketleri içeren bir değişim yönetimi planı oluşturulmalıdır.
        """)
    stok_s = params.get('stok_s')
    if stok_s == STOK_STRATEJILERI[3]: 
        any_issue_found = True
        st.warning("""
        **Müşteri ve Tedarikçi Etkisi (Strateji: SKU Optimizasyonu)**
        - **Tespit:** Yavaş hareket eden ürünlerin çıkarılması, bu niş ürünleri satın alan küçük müşteri grubunda memnuniyetsizlik yaratabilir ve ilgili tedarikçilerle olan iş ilişkilerini sonlandırabilir.
        - **Stratejik Öneri (Paydaş İlişki Yönetimi):** Etkilenecek müşterilere proaktif olarak ulaşıp alternatifler sunulmalı ve tedarikçilere makul bir geçiş süresi tanınmalıdır.
        """)
    elif stok_s == STOK_STRATEJILERI[4]: 
        any_issue_found = True
        st.warning("""
        **Hizmet Adaleti Etkisi (Strateji: Kilit Müşteri Ayrıcalığı)**
        - **Tespit:** En büyük 10 müşteriye öncelik tanımak, diğer 140 müşteriye daha düşük bir hizmet seviyesi sunulması anlamına gelir.
        - **Stratejik Öneri (Adil Hizmet Politikası):** Tüm müşteri segmentleri için net Hizmet Seviyesi Anlaşmaları (SLA) tanımlanmalıdır.
        """)
        
    return any_issue_found

def _render_dynamic_stakeholder_issues(final_row):
    """Sadece simülasyon sonuçlarına dayalı dinamik paydaş etkilerini render eder."""
    any_issue_found = False
    thresholds = CONFIG['stakeholder_analysis_thresholds']

    if final_row['OTIF'] < thresholds['otif_baski_esigi']:
        any_issue_found = True
        st.warning(f"""
        **Hizmet Seviyesi Baskısı (Satış ve Müşteri Hizmetleri)**
        - **Tespit:** Simülasyon sonundaki düşük OTIF oranı ({final_row['OTIF']:.1%}), müşteri beklentilerinin karşılanamadığını gösteriyor. Bu durum, sadece müşteri kaybı riski yaratmakla kalmaz, aynı zamanda satış ekibinin prim hedeflerine ulaşmasını zorlaştırır ve müşteri hizmetleri üzerinde sürekli bir şikayet yönetimi baskısı oluşturur.
        - **Stratejik Öneri:** Hizmet seviyesindeki düşüşün kök nedenleri (stoksuzluk, lojistik gecikme vb.) analiz edilmeli ve bu departmanların hedefleri, mevcut operasyonel gerçekliklere göre revize edilmelidir. (Hedef: >{thresholds['otif_baski_esigi']:.0%})
        """)
    if final_row['Stok Devir Hızı'] < thresholds['stok_hizi_baski_esigi']:
        any_issue_found = True
        st.warning(f"""
        **Çalışma Sermayesi Baskısı (Finans Departmanı)**
        - **Tespit:** Düşük stok devir hızı ({final_row['Stok Devir Hızı']:.1f}), depolarda atıl sermayenin biriktiği ve nakit akışının yavaşladığı anlamına gelir. Bu, Finans Departmanı'nın çalışma sermayesi yönetimi hedeflerini olumsuz etkiler.
        - **Stratejik Öneri:** Yavaş hareket eden ürünler için (bkz: Yönetim Paneli > Risk Radarı) özel kampanyalar düzenlenmeli ve satın alma departmanı ile envanter hedefleri yeniden gözden geçirilmelidir. (Hedef: >{thresholds['stok_hizi_baski_esigi']:.0f})
        """)
    if final_row['Esneklik Skoru'] < thresholds['esneklik_kriz_esigi']:
        any_issue_found = True
        st.warning(f"""
        **Reaktif Yönetim Riski (Üst Yönetim)**
        - **Tespit:** Düşük esneklik skoru ({final_row['Esneklik Skoru']:.1f}), şirketin beklenmedik piyasa şoklarına ve krizlere karşı kırılgan olduğunu gösterir. Bu durum, üst yönetimi sürekli olarak anlık krizlerle boğuşmaya iter ve uzun vadeli stratejik hedeflerden uzaklaştırır.
        - **Stratejik Öneri:** Şirketin kırılganlıklarını (bkz: Yönetim Paneli > Risk Matrisi) ortaya çıkaran senaryolar üzerinde düzenli olarak kriz masası tatbikatları yapılmalıdır. (Hedef: >{thresholds['esneklik_kriz_esigi']:.0f})
        """)
        
    return any_issue_found

def _render_crisis_stakeholder_issues(realized_events, scenario_title):
    """Sadece yaşanan krizlere dayalı paydaş etkilerini render eder."""
    if not realized_events:
        return False
        
    any_issue_found = True 
    st.markdown("##### Kriz Senaryosu Etkileri")

    if "Jüri Özel" in scenario_title:
        if "Kum Fırtınası" in scenario_title:
            st.error("""
            **Senaryo Etkisi: Kriz Yönetimi Baskısı**
            - **Tespit:** "Kum Fırtınası" senaryosu, birden fazla ve birbiriyle ilişkili krizin aynı anda yönetilmesini gerektirir. Bu durum, tedarik zinciri ve yönetim ekipleri üzerinde aşırı bir stres, karar yorgunluğu ve tükenmişlik riski yaratır.
            - **Stratejik Öneri:** Şirket, bu tür birleşik krizlere karşı bir 'Kriz Yönetim Masası' kurmalı ve farklı departmanlardan temsilcilerle düzenli olarak bu tür senaryoları simüle eden tatbikatlar yapmalıdır.
            """)
        elif "Operasyonel Kâbus" in scenario_title:
            st.error("""
            **Senaryo Etkisi: Tedarikçi Güvenilirliği**
            - **Tespit:** Kilit bir 3PL ortağın zirve sezonda çökmesi, sadece anlık bir lojistik kriz değil, aynı zamanda şirketin tedarikçi seçim ve risk yönetimi süreçlerindeki bir zafiyeti ortaya koyar.
            - **Stratejik Öneri:** Tedarikçi portföyü yeniden değerlendirilmeli, kilit hizmetler için alternatif (yedek) tedarikçilerle ön anlaşmalar yapılmalı ve 3PL performansları daha sıkı denetlenmelidir.
            """)
        elif "Stratejik İkilem" in scenario_title:
            st.warning("""
            **Senaryo Etkisi: Karar Felci Riski**
            - **Tespit:** Bir yanda yüksek kârlı bir fırsat, diğer yanda pazar payını koruma baskısı, orta ve üst yönetimi karar felcine sürükleyebilir. Yanlış önceliğe odaklanmak, her iki fırsatın da kaçırılmasına neden olabilir.
            - **Stratejik Öneri:** Şirketin, bu gibi durumlar için önceden belirlenmiş bir "stratejik oyun kitabı" (playbook) olmalıdır. Hangi koşullarda kâr marjının, hangi koşullarda pazar payının önceliklendirileceği net olarak tanımlanmalıdır.
            """)
        elif "Büyüme Fırsatı" in scenario_title:
            st.success("""
            **Senaryo Etkisi: Fırsat Yönetimi ve Ekip Motivasyonu**
            - **Tespit:** Bu senaryo, şirketin ani büyüme potansiyelini test eder. Bu süreç, satış, üretim ve lojistik ekipleri için büyük bir başarı ve motivasyon kaynağı olabileceği gibi, aşırı iş yükü ve yetersiz kaynak nedeniyle tam tersi bir etki de yaratabilir.
            - **Stratejik Öneri:** Büyüme hedefi tüm ekiplerle şeffafça paylaşılmalı, bu dönem için özel bir "hedef bonusu" sistemi düşünülmeli ve artan iş yükünü karşılamak için proaktif kaynak (fazla mesai, geçici personel) planlaması yapılmalıdır.
            """)

    if "Liman Grevi" in realized_events or "3PL İflası" in realized_events:
        st.error("""
        **Operasyonel Güvenilirlik ve İletişim Krizi**
        - **Tespit:** Lojistik altyapısındaki (liman, 3PL) bir çöküş, sadece sevkiyatları geciktirmez, aynı zamanda müşterilerin şirketin tedarik zinciri yönetimine olan güvenini sarsar.
        - **Stratejik Öneri:** Müşterilerle proaktif ve şeffaf iletişim kurulmalı, alternatif rotalar/taşıyıcılar için acil eylem planları (contingency plans) önceden hazırlanmalıdır.
        """)
    if "Hammadde Tedarikçi Krizi" in realized_events:
         st.error("""
        **Tedarikçi Bağımlılığı Riski**
        - **Tespit:** Kritik bir tedarikçide yaşanan sorun, tek kaynağa bağımlılığın ne kadar tehlikeli olduğunu gösterir. Bu durum, sadece üretimi durdurmakla kalmaz, Ar-Ge ve inovasyon süreçlerini de sekteye uğratabilir.
        - **Stratejik Öneri:** Kritik hammaddeler için en az bir alternatif (ikincil) tedarikçi belirlenmeli ve bu tedarikçiyle deneme üretimleri yapılarak onay süreçleri tamamlanmalıdır.
        """)
    if "Rakip Fiyat Kırması" in realized_events or "Stratejik İkilem (Talep & Fiyat)" in realized_events:
        st.warning("""
        **Karar Felci ve Fiyatlandırma Stratejisi Riski**
        - **Tespit:** Agresif rekabet, satış ve pazarlama ekiplerini panik halinde fiyat indirimlerine, yönetimi ise kâr marjı ile pazar payı arasında bir karar felcine sürükleyebilir.
        - **Stratejik Öneri:** Şirketin, farklı rekabet senaryoları için önceden belirlenmiş bir "fiyatlandırma oyun kitabı" (pricing playbook) olmalıdır. Hangi koşulda ne kadar marjdan feragat edilebileceği net olmalıdır.
        """)
    if "Talep Patlaması" in realized_events or "Rakip Çekilmesi (Fırsat)" in realized_events:
        st.success("""
        **Fırsat Yönetimi ve Ekip Motivasyonu**
        - **Tespit:** Ani büyüme potansiyeli, tüm operasyonel ekipler için büyük bir başarı ve motivasyon kaynağı olabileceği gibi, aşırı iş yükü ve yetersiz kaynak nedeniyle tam tersi bir etki de yaratabilir.
        - **Stratejik Öneri:** Büyüme hedefi tüm ekiplerle şeffafça paylaşılmalı, bu dönem için özel bir "hedef bonusu" sistemi düşünülmeli ve artan iş yükünü karşılamak için proaktif kaynak (fazla mesai, geçici personel) planlaması yapılmalıdır.
        """)
        
    return any_issue_found

def render_stakeholder_analysis(params, scenario_title, results_df, final_row):
    """Ana Paydaş Analizi fonksiyonu. Yardımcı fonksiyonları çağırarak analizi organize eder."""
    st.markdown("---")
    st.subheader("👥 Paydaş Etki Analizi ve Değişim Yönetimi Önerileri")
    st.caption("Seçtiğiniz stratejilerin ve yaşanan krizlerin 'insan' ve 'süreç' üzerindeki potansiyel etkileri ve proaktif yönetim önerileri.")

    st.markdown("##### Stratejiye Dayalı Öngörüler")
    strategy_issues_found = _render_strategy_based_stakeholder_issues(params)
    if not strategy_issues_found:
        st.info("Seçilen başlangıç stratejilerinin doğrudan bir negatif paydaş etkisi öngörülmemektedir.")

    st.markdown("##### Simülasyon Sonucuna Dayalı Tespitler")
    dynamic_issues_found = _render_dynamic_stakeholder_issues(final_row)
    if not dynamic_issues_found:
        st.info("Simülasyon sonuçları, operasyonel hedefler açısından önemli bir negatif paydaş etkisi göstermemektedir.")

    realized_events = set(results_df[results_df['Gerçekleşen Olay'] != 'Kriz Yok']['Gerçekleşen Olay'])
    crisis_issues_found = _render_crisis_stakeholder_issues(realized_events, scenario_title)

    any_issue_found = any([strategy_issues_found, dynamic_issues_found, crisis_issues_found])
    if not any_issue_found:
         st.success("Tebrikler! Seçilen stratejiler ve simülasyon sonuçları, paydaşlar üzerinde önemli bir negatif etki veya kriz öngörmemektedir. Dengeli ve sağlam bir yaklaşım elde edildi.")

def plot_risk_heatmap(risk_df):
    """Risk matrisini bir ısı haritası olarak çizer."""
    fig = px.imshow(risk_df,
                    labels=dict(x="Kriz Senaryoları", y="Stratejiler", color="Aylık Kâr Kaybı ($)"),
                    text_auto=".2s",
                    aspect="auto",
                    color_continuous_scale=px.colors.sequential.Reds,
                    title="Strateji-Kriz Risk Matrisi")
    fig.update_xaxes(side="top")
    return fig

def render_financial_intelligence_panel(df, key_prefix=""):
    """Verilen DataFrame'i kullanarak finansal zeka panelini oluşturur ve ekrana basar."""
    if df is None or df.empty:
        st.warning("Finansal panel için ERP verileri bulunamadı veya boş.")
        return
    try:
        toplam_envanter_degeri = (df['Birim_Maliyet'] * df['Stok_Adedi']).sum()
        potansiyel_ciro = (df['Birim_Fiyat'] * df['Stok_Adedi']).sum()
        df_copy = df.copy()
        df_copy['Kar_Marji'] = df_copy.apply(lambda row: (row['Birim_Fiyat'] - row['Birim_Maliyet']) / row['Birim_Fiyat'] if row['Birim_Fiyat'] > 0 else 0, axis=1)
        karlilik_df = df_copy.groupby('Kategori')['Kar_Marji'].mean().reset_index()
        karlilik_df['Kar_Marji'] = karlilik_df['Kar_Marji'] * 100
        stok_degeri_kategori = df_copy.groupby('Kategori').apply(lambda d: (d['Birim_Maliyet'] * d['Stok_Adedi']).sum()).reset_index(name='EnvanterDegeri')
    except KeyError as e:
        st.error(f"Finansal panel hesaplamasında hata: Gerekli sütun ({e}) ERP verisinde bulunamadı.")
        return
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Toplam Envanter Maliyeti (USD)", value=f"${toplam_envanter_degeri:,.0f}", help="Depolarda bekleyen tüm ürünlerin toplam maliyet değeri.")
        fig_karlilik = px.bar(karlilik_df, x='Kategori', y='Kar_Marji', title="Kategori Bazında Ortalama Kâr Marjı (%)", text=karlilik_df['Kar_Marji'].apply(lambda x: f'{x:.1f}%'), labels={'Kategori': 'Ürün Kategorisi', 'Kar_Marji': 'Ortalama Kâr Marjı (%)'}, color='Kategori', color_discrete_map={'A': '#1f77b4', 'B': '#ff7f0e', 'C': '#2ca02c'})
        fig_karlilik.update_layout(showlegend=False)
        st.plotly_chart(fig_karlilik, use_container_width=True, key=f"{key_prefix}_chart_karlilik") 
    with col2:
        st.metric(label="Stoktaki Potansiyel Ciro (USD)", value=f"${potansiyel_ciro:,.0f}", help="Depolardaki tüm ürünlerin mevcut fiyattan satılması durumunda elde edilecek potansiyel gelir.")
        fig_stok_dagilim = px.pie(stok_degeri_kategori, values='EnvanterDegeri', names='Kategori', title='Envanter Değerinin Kategori Dağılımı', hole=.3, color='Kategori', color_discrete_map={'A': '#1f77b4', 'B': '#ff7f0e', 'C': '#2ca02c'})
        st.plotly_chart(fig_stok_dagilim, use_container_width=True, key=f"{key_prefix}_chart_dagilim") 

def plot_abc_analysis(summary_df):
    """
    ABC analizi özet verisinden bir Pareto grafiği oluşturur.
    """
    if summary_df is None or summary_df.empty:
        return go.Figure().update_layout(title_text="ABC Analizi için veri bulunamadı.")
        
    summary_df['Kumulatif_Ciro_Yuzdesi'] = summary_df['Ciro_Yuzdesi'].cumsum()

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=summary_df['ABC_Kategori'],
        y=summary_df['SKU_Yuzdesi'],
        name='SKU Yüzdesi',
        marker_color='#1f77b4',
        text=summary_df['SKU_Yuzdesi'].apply(lambda x: f'{x:.1f}%'),
        textposition='auto'
    ))

    fig.add_trace(go.Scatter(
        x=summary_df['ABC_Kategori'],
        y=summary_df['Kumulatif_Ciro_Yuzdesi'],
        name='Kümülatif Ciro Yüzdesi',
        yaxis='y2',
        marker_color='#ff7f0e',
        line=dict(width=3)
    ))

    fig.update_layout(
        title_text='ABC (Pareto) Analizi: SKU Dağılımı ve Ciro Katkısı',
        xaxis_title='ABC Kategorisi',
        yaxis=dict(
            title=dict(
                text='SKU\'ların Yüzdesi (%)',
                font=dict(color='#1f77b4')
            ),
            tickfont=dict(color='#1f77b4')
        ),
        yaxis2=dict(
            title=dict(
                text='Kümülatif Ciro Yüzdesi (%)',
                font=dict(color='#ff7f0e')
            ),
            overlaying='y',
            side='right',
            tickfont=dict(color='#ff7f0e'),
            range=[0, 105]
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

def create_interactive_map(tesis_df):
    """Verilen tesis DataFrame'ini kullanarak interaktif bir folium haritası oluşturur."""
    if tesis_df is None or tesis_df.empty: return None
    country_summary = tesis_df.groupby('Ulke').agg(Fiili_Uretim_Ton=('Fiili_Uretim_Ton', 'sum'), Kullanim_Orani=('Kullanim_Orani', 'mean'), Tesis_Sayisi=('Tesis Yeri', 'count'), lat=('Ulke', lambda x: LOCATION_COORDINATES.get(x.iloc[0], {}).get('lat')), lon=('Ulke', lambda x: LOCATION_COORDINATES.get(x.iloc[0], {}).get('lon'))).reset_index()
    m = folium.Map(location=[15, 45], zoom_start=2.5, tiles="CartoDB dark_matter")
    max_prod = country_summary['Fiili_Uretim_Ton'].max()
    for idx, row in country_summary.iterrows():
        if pd.notna(row['lat']) and pd.notna(row['lon']):
            radius = 10 + (row['Fiili_Uretim_Ton'] / max_prod) * 20 if max_prod > 0 else 10
            popup_html = f"""<b>Ülke:</b> {row['Ulke']}<br><b>Tesis Sayısı:</b> {row['Tesis_Sayisi']}<br><hr style='margin: 5px 0;'><b>Toplam Üretim:</b> {row['Fiili_Uretim_Ton']:,.0f} ton<br><b>Ortalama Kapasite Kullanımı:</b> {row['Kullanim_Orani']:.1%}"""
            popup = folium.Popup(popup_html, max_width=300)
            folium.CircleMarker(location=[row['lat'], row['lon']], radius=radius, popup=popup, tooltip=f"<b>{row['Ulke']}</b>: {row['Fiili_Uretim_Ton']:,.0f} ton", color='#00b0f0', fill=True, fill_color='#00b0f0', fill_opacity=0.6).add_to(m)
    return m

def render_rollout_plan():
    st.title("📈 Proje Uygulama Yol Haritası (Rollout Plan)")
    st.info("Bu yol haritası, önerilen dönüşümün 'Emekle, Yürü, Koş' modeliyle nasıl yönetilebilir, riski azaltılmış ve her aşamada kazanım sağlayan adımlarla hayata geçirileceğini göstermektedir.")

    start_date = pd.to_datetime('today').date()

    tasks = [
        dict(Task="Faz 1: Pilot Proje ve Temel Atma (Emekleme)", Start=start_date, Finish=start_date + pd.Timedelta(weeks=12), Resource="Ana Faz"),
        dict(Task="Pilot Kapsam Belirleme (Türkiye, Kategori C)", Start=start_date, Finish=start_date + pd.Timedelta(weeks=2), Resource="Planlama"),
        dict(Task="Simülatör ve Süreç Entegrasyonu", Start=start_date + pd.Timedelta(weeks=2), Finish=start_date + pd.Timedelta(weeks=8), Resource="Uygulama"),
        dict(Task="Pilot Sonuç Analizi ve Raporlama", Start=start_date + pd.Timedelta(weeks=8), Finish=start_date + pd.Timedelta(weeks=12), Resource="Analiz"),
        
        dict(Task="Faz 2: Genişleme ve Ölçeklendirme (Yürüme)", Start=start_date + pd.Timedelta(weeks=13), Finish=start_date + pd.Timedelta(weeks=39), Resource="Ana Faz"),
        dict(Task="Hindistan Operasyonları Değerlendirme", Start=start_date + pd.Timedelta(weeks=13), Finish=start_date + pd.Timedelta(weeks=17), Resource="Planlama"),
        dict(Task="Standart Süreçlerin Yaygınlaştırılması", Start=start_date + pd.Timedelta(weeks=17), Finish=start_date + pd.Timedelta(weeks=35), Resource="Uygulama"),
        dict(Task="Finansal Etki ve CCC İyileştirme Takibi", Start=start_date + pd.Timedelta(weeks=35), Finish=start_date + pd.Timedelta(weeks=39), Resource="Analiz"),

        dict(Task="Faz 3: Optimizasyon ve Kurumsallaştırma (Koşma)", Start=start_date + pd.Timedelta(weeks=40), Finish=start_date + pd.Timedelta(weeks=92), Resource="Ana Faz"),
        dict(Task="Tüm IMEA Bölgesine Yayılım", Start=start_date + pd.Timedelta(weeks=40), Finish=start_date + pd.Timedelta(weeks=66), Resource="Uygulama"),
        dict(Task="Tam ERP ve Teknoloji Entegrasyonu", Start=start_date + pd.Timedelta(weeks=52), Finish=start_date + pd.Timedelta(weeks=92), Resource="Teknoloji"),
        dict(Task="Sürekli İyileştirme Kültürü Oluşturma", Start=start_date + pd.Timedelta(weeks=40), Finish=start_date + pd.Timedelta(weeks=92), Resource="Kültür")
    ]
    df = pd.DataFrame(tasks)
    
    colors = {
        "Ana Faz": 'rgb(30, 144, 255)',
        "Planlama": 'rgb(255, 165, 0)',
        "Uygulama": 'rgb(50, 205, 50)',
        "Analiz": 'rgb(218, 112, 214)',
        "Teknoloji": 'rgb(128, 0, 128)',
        "Kültür": 'rgb(255, 69, 0)'
    }

    fig = ff.create_gantt(df, colors=colors, index_col='Resource', group_tasks=True, show_colorbar=True, title="Aşamalı Uygulama Planı")
    
    initial_view_start = start_date - pd.Timedelta(days=30)
    initial_view_end = start_date + pd.Timedelta(days=365)
    
    fig.update_layout(
        xaxis_range=[initial_view_start.strftime('%Y-%m-%d'), initial_view_end.strftime('%Y-%m-%d')],
        title_text="Aşamalı Uygulama Planı (İlk Yıl Görünümü)"
    )
    
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Aşamaların Detaylı Analizi")
    with st.expander("📍 FAZ 1: Pilot Proje ve Temel Atma (İlk 3 Ay) - 'Emekleme'"):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("##### 🎯 Ana Hedefler ve Kapsam")
            st.markdown("- **Hedef:** Yeni S&OP süreci ve simülatörün gerçek veriyle etkinliğinin kanıtlanması.\n- **Hedef:** Hızlı kazanım (quick-win) ile tüm organizasyon için paydaş desteğinin ve güvenin sağlanması.\n- **Kapsam:** Kontrol edilebilir bir alan olan **Türkiye operasyonu** ve mevsimselliği en belirgin olan **Kategori C ürünleri**.")
            st.markdown("##### 🏁 Başarı Kriterleri (KPIs)")
            st.markdown("- **Tahmin Doğruluğu (C Kat.):** > %60 (Mevcut < %45)\n- **OTIF (Türkiye):** > %88 (Mevcut %85)\n- **Proje Bütçesi:** <%5 sapma")
        with col2:
            st.markdown("##### 👥 Kilit Paydaşlar")
            st.markdown("- **Sponsor:** COO\n- **Proje Lideri:** Tedarik Zinciri Direktörü\n- **Çekirdek Ekip:** Türkiye Lojistik Müdürü, Planlama Uzmanı, Satış Müdürü")
            st.markdown("##### ⚠️ Potansiyel Riskler")
            st.markdown("- **Risk:** Veri kalitesi sorunları ve entegrasyon zorlukları.\n- **Önlem:** Proje başlangıcında 1 haftalık veri temizleme ve doğrulama sprint'i.")

    with st.expander("🏃‍♂️ FAZ 2: Genişleme ve Ölçeklendirme (Sonraki 6 Ay) - 'Yürüme'"):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("##### 🎯 Ana Hedefler ve Kapsam")
            st.markdown("- **Hedef:** En büyük pazar olan Hindistan'da somut finansal ve operasyonel fayda sağlamak.\n- **Hedef:** Başarılı pilot süreçlerini standart operasyon prosedürlerine (SOP) dönüştürmek.\n- **Kapsam:** **Hindistan operasyonları** ve **tüm ürün kategorileri (A, B, C)**.")
            st.markdown("##### 🏁 Başarı Kriterleri (KPIs)")
            st.markdown("- **Genel Tahmin Doğruluğu:** > %70\n- **Nakit Döngü Süresi (CCC):** 15 gün iyileşme\n- **Stok Devir Hızı:** > 3.5")
        with col2:
            st.markdown("##### 👥 Kilit Paydaşlar")
            st.markdown("- **Ek Paydaşlar:** Hindistan Ülke Müdürü, Finans Direktörü (CFO), Satın Alma Departmanı")
            st.markdown("##### ⚠️ Potansiyel Riskler")
            st.markdown("- **Risk:** Değişime karşı direnç.\n- **Önlem:** Faz 1 başarılarının sunumu, eğitimler ve performans prim sistemine entegrasyon.")

    with st.expander("🚀 FAZ 3: Optimizasyon ve Kurumsallaştırma (1 Yıl+) - 'Koşma'"):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("##### 🎯 Ana Hedefler ve Kapsam")
            st.markdown("- **Hedef:** Yeni planlama ve karar verme modelini şirketin DNA'sına işlemek.\n- **Hedef:** Simülatör ve S&OP sürecini tam otonom ve proaktif bir yapıya kavuşturmak.\n- **Kapsam:** **Tüm IMEA bölgesi (G. Afrika dahil)** ve tam teknoloji entegrasyonu.")
            st.markdown("##### 🏁 Başarı Kriterleri (KPIs)")
            st.markdown("- **OTIF (IMEA):** > %95 (Vaka hedefi)\n- **Stratejik Kararlar:** Simülatörün, yıllık bütçe ve strateji toplantılarının zorunlu bir girdisi olması.\n- **Esneklik Skoru:** > 8.0")
        with col2:
            st.markdown("##### 👥 Kilit Paydaşlar")
            st.markdown("- **Ek Paydaşlar:** CEO, Yönetim Kurulu, tüm IMEA ülke yöneticileri")
            st.markdown("##### ⚠️ Potansiyel Riskler")
            st.markdown("""- **Risk:** Projenin bir "araç" olarak kalıp "kültür" haline gelememesi.\n- **Önlem:** Sürekli iyileştirme ekipleri (Kaizen) kurulması ve başarının kurumsal hedeflere bağlanması.""")
