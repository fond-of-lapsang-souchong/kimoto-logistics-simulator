import pandas as pd
import streamlit as st
import logging

logger = logging.getLogger(__name__)

def normalize_and_validate_data(df):
    """Yüklenen ERP DataFrame'ini normalize eder ve temel iş kurallarına göre doğrular.

    Bu fonksiyon, veri kalitesini sağlamak için kritik bir adımdır.
    Metin sütunlarındaki boşlukları temizler, gerekli sütunların varlığını
    kontrol eder, kategorik verilerin geçerliliğini ve sayısal sütunlardaki
    negatif değerleri denetler. Hatalı veri durumunda kullanıcıya
    Streamlit arayüzü üzerinden uyarılar gösterir.

    Args:
        df (pd.DataFrame): Doğrulanacak ham ERP verisi.

    Returns:
        pd.DataFrame or None: Doğrulanmış ve temizlenmiş DataFrame.
                              Eğer kritik bir hata (örn: eksik sütun) varsa
                              `None` döndürür.
    """
    if df.empty:
        return df 

    validated_df = df.copy()
    error_messages = []

    for col in validated_df.select_dtypes(include=['object']).columns:
        validated_df[col] = validated_df[col].str.strip()

    required_columns = ['SKU', 'Kategori', 'Stok_Adedi', 'Birim_Maliyet', 'Birim_Fiyat', 'Tedarik_Suresi_Hafta']
    for col in required_columns:
        if col not in validated_df.columns:
            msg = f"Kritik Hata: CSV dosyasında '{col}' sütunu bulunamadı."
            error_messages.append(msg)
            logger.error(msg)
            st.error(msg)
            return None 

    valid_categories = ['A', 'B', 'C']
    if 'Kategori' in validated_df.columns and not validated_df['Kategori'].dropna().empty:
        if not set(validated_df['Kategori'].unique()).issubset(set(valid_categories)):
            error_messages.append("Veri Hatası: 'Kategori' sütununda 'A', 'B', 'C' dışında geçersiz değerler var.")

    numeric_cols_to_check = ['Stok_Adedi', 'Siparis_Bekleyen', 'Birim_Maliyet', 'Birim_Fiyat', 'Talep_Tahmini', 'Tedarik_Suresi_Hafta']
    
    cols_to_validate = [col for col in numeric_cols_to_check if col in validated_df.columns]

    for col in cols_to_validate:
        if validated_df[col].dropna().empty:
            continue
        if not pd.api.types.is_numeric_dtype(validated_df[col]):
             error_messages.append(f"Veri Hatası: '{col}' sütunu sayısal olmayan değerler içeriyor.")
             continue 
        if (validated_df[col] < 0).any():
            error_messages.append(f"Veri Hatası: '{col}' sütununda negatif değerler bulunmamalıdır.")

    if error_messages:
        st.warning("Veri Doğrulama Uyarısı:")
        for msg in error_messages:
            logger.warning(f"Veri doğrulama uyarısı: {msg}")
            st.markdown(f"- {msg}")
    
    return validated_df

def load_erp_data(file_path="erp_data_300_sku.csv"):
    """Belirtilen CSV dosyasından ERP verisini okur, doğrular ve temel dönüşümleri yapar.

    Bu fonksiyon, ERP entegrasyonunu simüle eder. Dosyayı okur,
    `normalize_and_validate_data` fonksiyonu ile veriyi temizler ve doğrular,
    ve 'Tedarik_Suresi_Gun' gibi ek bir sütun oluşturur.
    Dosya bulunamazsa veya bozuksa, uygulamayı durdurur (`st.stop`).

    Args:
        file_path (str, optional): Okunacak CSV dosyasının yolu.
                                   Varsayılan: "erp_data_300_sku.csv".

    Returns:
        pd.DataFrame or None: Başarıyla yüklenen ve işlenen ERP verisi.
                              Hata durumunda `None` döner ve uygulama durur.
    """
    try:
        df = pd.read_csv(file_path)
        
        df = normalize_and_validate_data(df)
        if df is None:
            st.stop() 

        if not df.empty and 'Tedarik_Suresi_Hafta' in df.columns:
            df['Tedarik_Suresi_Gun'] = df['Tedarik_Suresi_Hafta'] * 7
        
        logger.info(f"'{file_path}' başarıyla yüklendi, {len(df)} SKU bulundu.")
        return df
        
    except pd.errors.EmptyDataError:
        logger.error(f"HATA: Veri dosyası '{file_path}' boş veya bozuk.")
        st.error(f"HATA: Veri dosyası '{file_path}' boş veya bozuk.")
        st.stop()
        return None
    except FileNotFoundError:
        logger.error(f"HATA: Veri dosyası bulunamadı. Lütfen '{file_path}' dosyasının doğru dizinde olduğundan emin olun.")
        st.error(f"HATA: Veri dosyası bulunamadı. Lütfen '{file_path}' dosyasının doğru dizinde olduğundan emin olun.")
        st.stop()
        return None
    except Exception as e:
        logger.error(f"Veri okunurken bir hata oluştu: {e}")
        st.error(f"Veri okunurken bir hata oluştu: {e}")
        st.stop()
        return None