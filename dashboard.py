import streamlit as st
import requests
import pandas as pd
from tefas import Crawler
from datetime import datetime, timedelta

# --- SAYFA AYARI VE BAŞLIK ---
st.set_page_config(page_title="Sinan Invest Dashboard", layout="wide", page_icon="📈")

st.title("📊 Finansal Analiz ve Portföy Yönetim Paneli")
st.markdown("Bu panel; **BIST**, **Wall Street** ve **TEFAS Fonları** için canlı verilerle çalışır. Sol menüden pazarı ve kriterleri seçin.")

# --- SOL MENÜ: PAZAR VE DİNAMİK FİLTRELER ---
st.sidebar.header("🎯 Pazar ve Filtre Seçimi")
market_choice = st.sidebar.selectbox(
    "Hangi Piyasayı Taramak İstiyorsun?", 
    ["Borsa İstanbul (BIST)", "ABD Borsaları (Wall Street)", "TEFAS Fon Analizi"]
)

# Pazara göre sol menü filtreleri değişir
if market_choice == "Borsa İstanbul (BIST)":
    st.sidebar.subheader("BIST Filtreleri")
    pe_limit = st.sidebar.slider("Maksimum F/K", 5, 50, 12)
    roe_min = st.sidebar.slider("Minimum ROE (%)", 0, 100, 30)
    div_min = st.sidebar.slider("Minimum Temettü (%)", 0, 15, 4)
    mcap_min = st.sidebar.number_input("Min. Piyasa Değeri (Milyar TL)", value=10)

elif market_choice == "ABD Borsaları (Wall Street)":
    st.sidebar.subheader("ABD Filtreleri")
    pe_limit = st.sidebar.slider("Maksimum F/K", 5, 60, 25)
    roe_min = st.sidebar.slider("Minimum ROE (%)", 0, 100, 25)
    div_min = st.sidebar.slider("Minimum Temettü (%)", 0.0, 10.0, 3.0, step=0.5)
    mcap_min = st.sidebar.number_input("Min. Piyasa Değeri (Milyar Dolar)", value=10)

else: # TEFAS Seçildiyse
    st.sidebar.subheader("Fon Filtreleri")
    fund_return_min = st.sidebar.slider("Min. 1 Yıllık Getiri (%)", 30, 250, 80)
    fund_mcap_min = st.sidebar.number_input("Min. Fon Büyüklüğü (Milyon TL)", value=500)


# --- ARKA PLAN FONKSİYONLARI ---

@st.cache_data(ttl=600) # Veriyi 10 dk önbellekte tutar, hızı artırır
def fetch_tradingview_data(market_code, filter_ops):
    url = f'https://scanner.tradingview.com/{market_code}/scan?label-product=screener-stock'
    headers = {'Content-Type': 'application/json'}
    payload = {
        "columns": ["name", "close", "price_earnings_ttm", "return_on_equity", "dividend_yield_recent", "debt_to_equity", "market_cap_basic", "sector"],
        "sort": {"sortBy": "return_on_equity", "sortOrder": "desc"},
        "range": [0, 50],
        "markets": [market_code],
        "filter2": {
            "operator": "and",
            "operands": filter_ops + [
                {"expression": {"left": "type", "operation": "equal", "right": "stock"}},
                {"expression": {"left": "typespecs", "operation": "has", "right": ["common"]}}
            ]
        }
    }
    try:
        res = requests.post(url, headers=headers, json=payload).json()
        return res.get('data', [])
    except:
        return []

@st.cache_data(ttl=3600) # TEFAS verisi saatte 1 güncellenir
def fetch_tefas_data():
    tefas = Crawler()
    bugun = datetime.now()
    bes_gun_once = bugun - timedelta(days=5)
    bir_yil_once = bugun - timedelta(days=365)
    bir_yil_bes_gun_once = bir_yil_once - timedelta(days=5)
    
    # Güncel veri ve Eski Veri Çekimi
    guncel = tefas.fetch(start=bes_gun_once.strftime("%Y-%m-%d"), end=bugun.strftime("%Y-%m-%d"), columns=["code", "title", "price", "market_cap", "number_of_investors"], kind="YAT")
    guncel['date'] = pd.to_datetime(guncel['date'])
    guncel_df = guncel[guncel['date'] == guncel['date'].max()].copy()
    
    eski = tefas.fetch(start=bir_yil_bes_gun_once.strftime("%Y-%m-%d"), end=bir_yil_once.strftime("%Y-%m-%d"), columns=["code", "price"], kind="YAT")
    eski['date'] = pd.to_datetime(eski['date'])
    eski_df = eski[eski['date'] == eski['date'].max()].copy().rename(columns={"price": "eski_fiyat"})
    
    # Portföy Dağılımı (Hisse, Yabancı Hisse, Maden)
    dagilim = tefas.fetch(start=bes_gun_once.strftime("%Y-%m-%d"), end=bugun.strftime("%Y-%m-%d"), kind="YAT", columns=["code", "stock", "foreign_stock", "precious_metals"])
    dagilim['date'] = pd.to_datetime(dagilim['date'])
    dagilim_df = dagilim[dagilim['date'] == dagilim['date'].max()].copy()
    
    # Birleştirme ve Matematik
    df = pd.merge(guncel_df, eski_df[['code', 'eski_fiyat']], on='code', how='inner')
    final_df = pd.merge(df, dagilim_df[['code', 'stock', 'foreign_stock', 'precious_metals']], on='code', how='left')
    
    for col in ['price', 'eski_fiyat', 'market_cap', 'number_of_investors', 'stock', 'foreign_stock', 'precious_metals']:
        final_df[col] = pd.to_numeric(final_df[col], errors='coerce')
        
    final_df['1Y_Getiri_%'] = ((final_df['price'] - final_df['eski_fiyat']) / final_df['eski_fiyat']) * 100
    return final_df

# --- ANA EKRAN GÖSTERİMLERİ ---

if market_choice == "Borsa İstanbul (BIST)":
    st.subheader("🇹🇷 BIST Kalite ve Değer Taraması")
    filters = [
        {"expression": {"left": "price_earnings_ttm", "operation": "in_range", "right": [0.1, pe_limit]}},
        {"expression": {"left": "return_on_equity", "operation": "egreater", "right": roe_min}},
        {"expression": {"left": "dividend_yield_recent", "operation": "egreater", "right": div_min}},
        {"expression": {"left": "market_cap_basic", "operation": "egreater", "right": mcap_min * 1_000_000_000}}
    ]
    
    with st.spinner('TradingView üzerinden BIST canlı verileri çekiliyor...'):
        data = fetch_tradingview_data("turkey", filters)
        
    if data:
        results = [{"Hisse": d['d'][0].replace("BIST:", ""), "Fiyat (TL)": d['d'][1], "F/K": round(d['d'][2],2), "ROE (%)": round(d['d'][3],2), "Temettü (%)": round(d['d'][4],2), "Borç/Özk.": round(d['d'][5],2), "PD (Milyar TL)": round(d['d'][6]/1e9, 2), "Sektör": d['d'][7]} for d in data]
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("Bu kriterlere uygun BIST hissesi bulunamadı. Lütfen sol menüden filtreleri esnetin.")

elif market_choice == "ABD Borsaları (Wall Street)":
    st.subheader("🇺🇸 Wall Street Büyüme ve Temettü Taraması")
    filters = [
        {"expression": {"left": "price_earnings_ttm", "operation": "in_range", "right": [0.1, pe_limit]}},
        {"expression": {"left": "return_on_equity", "operation": "egreater", "right": roe_min}},
        {"expression": {"left": "dividend_yield_recent", "operation": "egreater", "right": div_min}},
        {"expression": {"left": "market_cap_basic", "operation": "egreater", "right": mcap_min * 1_000_000_000}}
    ]
    
    with st.spinner('Wall Street canlı verileri taranıyor...'):
        data = fetch_tradingview_data("america", filters)
        
    if data:
        results = [{"Hisse": d['d'][0], "Fiyat ($)": d['d'][1], "F/K": round(d['d'][2],2), "ROE (%)": round(d['d'][3],2), "Temettü (%)": round(d['d'][4],2) if d['d'][4] else 0, "Borç/Özk.": round(d['d'][5],2), "PD (Milyar $)": round(d['d'][6]/1e9, 2), "Sektör": d['d'][7]} for d in data]
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("Bu kriterlere uygun ABD hissesi bulunamadı. Lütfen sol menüden filtreleri esnetin.")

else:
    st.subheader("🏆 TEFAS Fon Performans ve İçerik Analizi")
    st.info("💡 Not: TEFAS altyapısından geçmiş veriler ve portföy dağılımları işlendiği için bu işlem 10-15 saniye sürebilir.")
    
    with st.spinner('300+ Yatırım fonu taranıyor...'):
        try:
            tefas_df = fetch_tefas_data()
            filtreli_df = tefas_df[(tefas_df['market_cap'] > fund_mcap_min * 1_000_000) & (tefas_df['1Y_Getiri_%'] > fund_return_min)].copy()
            
            if not filtreli_df.empty:
                filtreli_df['Büyüklük (Milyon TL)'] = (filtreli_df['market_cap'] / 1_000_000).round(0)
                filtreli_df['1Y Getiri (%)'] = filtreli_df['1Y_Getiri_%'].round(2)
                filtreli_df['Yerli Hisse (%)'] = filtreli_df['stock'].round(2).fillna(0)
                filtreli_df['Yab. Hisse (%)'] = filtreli_df['foreign_stock'].round(2).fillna(0)
                filtreli_df['Maden (%)'] = filtreli_df['precious_metals'].round(2).fillna(0)
                
                sonuc = filtreli_df[['code', 'title', '1Y Getiri (%)', 'Büyüklük (Milyon TL)', 'number_of_investors', 'Yerli Hisse (%)', 'Yab. Hisse (%)', 'Maden (%)']]
                sonuc = sonuc.rename(columns={"code": "Kodu", "title": "Fon Adı", "number_of_investors": "Yatırımcı Sayısı"})
                sonuc = sonuc.sort_values(by='1Y Getiri (%)', ascending=False)
                
                st.dataframe(sonuc, use_container_width=True)
            else:
                st.warning("Bu kriterlere uygun fon bulunamadı. Lütfen getiri veya büyüklük filtresini düşürün.")
        except Exception as e:
            st.error(f"Veri çekilirken bir hata oluştu: {e}")
