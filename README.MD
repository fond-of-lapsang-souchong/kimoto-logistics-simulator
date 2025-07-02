# Kimoto Solutions - Entegre Karar Destek Sistemi

Bu proje, 22. Üniversiteler Arası Lojistik Vaka Yarışması için geliştirilmiş, Python ve Streamlit tabanlı interaktif bir tedarik zinciri simülasyon ve optimizasyon aracıdır. Uygulama, karmaşık tedarik zinciri kararlarının finansal, operasyonel ve stratejik sonuçlarını görselleştirmek ve en uygun stratejiyi bulmak için tasarlanmıştır.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://senin-streamlit-cloud-linkin.streamlit.app) 

---

## 🚀 Ana Özellikler

- **Çoklu Simülasyon Modları:**
  - **Tekil ve Karşılaştırmalı Analiz:** Belirlenen stratejilerin veya iki farklı stratejinin 12 aylık dönemdeki performansını detaylı olarak inceler.
  - **🎲 Olasılıksal Risk Analizi (Monte Carlo):** Stratejilerin belirsizlikler ve olasılıksal krizler (Domino Etkisi vb.) karşısındaki dayanıklılığını yüzlerce senaryo çalıştırarak test eder ve başarı olasılıklarını hesaplar.
  - **🤖 Strateji Optimizasyon Motoru:** Kullanıcının belirlediği bir hedefi (Kâr, OTIF, CO2 Tasarrufu vb.) maksimize edecek en iyi strateji kombinasyonunu `Optuna` kütüphanesi ile bulur.

- **📊 İnteraktif Yönetim Paneli:** Simülasyon sonuçlarını, Power BI benzeri bir arayüzde derinlemesine analiz eder:
  - Finansal Zeka ve Kârlılık Analizi
  - Stok & Talep Risk Radarı (Stoksuz Kalma vs. Atıl Sermaye)
  - Dinamik ABC (Pareto) Analizi
  - Lojistik Depo Kapasite Fizibilitesi

- **⚙️ Dinamik Modelleme Motoru:**
  - `event_library.py` üzerinden yönetilen, etkileri ve müdahaleleri tanımlanmış 10+ kriz senaryosu.
  - Krizlerin birbirini tetikleyebildiği **Domino Etkisi** mantığı.
  - Stratejilerin başlangıç yatırım maliyetlerini (CAPEX) ve operasyonel etkilerini (OPEX) doğru şekilde ayıran finansal modelleme.
  - Vaka metnine dayalı, **kategori öncelikli akıllı stok optimizasyonu algoritması.**

---

## 🛠️ Kurulum ve Çalıştırma

Bu proje, bir sanal ortam içinde çalıştırılmak üzere tasarlanmıştır.

1.  **Projeyi Klonlayın:**
    ```bash
    git clone https://github.com/kullanici-adiniz/proje-adiniz.git
    cd proje-adiniz
    ```

2.  **Sanal Ortam Oluşturun ve Aktif Edin (Önerilir):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    # .\.venv\Scripts\activate # Windows
    ```

3.  **Gerekli Kütüphaneleri Yükleyin:**
    `requirements.txt` dosyası tüm bağımlılıkları içerir.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Uygulamayı Başlatın:**
    ```bash
    streamlit run app.py
    ```
    Uygulama, tarayıcınızda yerel bir adreste açılacaktır.

---

## 📁 Proje Mimarisi (Sorumlulukların Ayrışması)

Proje, bakımı ve geliştirmesi kolay, modüler bir yapıya sahiptir:

-   **`app.py`**: Ana uygulama, orkestratör. UI ve simülasyon motoru arasındaki veri akışını yönetir.
-   **`simulation_engine.py`**: Simülasyonun kalbi. Tüm hesaplama mantığı ve analitik fonksiyonlar burada yer alır. Streamlit'ten tamamen bağımsızdır.
-   **`ui_manager.py`**: Arayüzü (sidebar, ana paneller, sonuç görselleri) çizen ana sınıf.
-   **`ui_components.py`**: Yeniden kullanılabilir arayüz bileşenlerini (grafikler, diyagramlar) içerir.
-   **`config.py`**: Tüm sayısal parametreler, strateji etkileri ve KPI hedefleri gibi genel yapılandırmayı merkezileştirir.
-   **`event_library.py`**: Kriz senaryoları, müdahaleleri ve Domino Etkisi kurallarını tanımlar.
-   **`erp_module.py`**: ERP veri yükleme ve doğrulama mantığını içerir.
-   **`test/`**: Projenin temel fonksiyonlarının doğruluğunu garanti eden birim ve entegrasyon testlerini içerir (`pytest`).