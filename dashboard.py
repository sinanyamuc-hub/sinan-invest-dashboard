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

if market_choice == "Borsa İstanbul (BIST)":
    st.sidebar.subheader("BIST Filtreleri")
    pe_limit = st.sidebar.slider("Maksimum F/K", 5, 50, 12, help="Fiyat/Kazanç Oranı: Şirketin güncel piyasa değerinin yıllık net kârına oranıdır. Şirketin kendini kaç yılda amorti edeceğini gösterir. Düşük olması hissenin 'ucuz' olabileceğine işarettir.")
    roe_min = st.sidebar.slider("Minimum ROE (%)", 0, 100, 30, help="Özkaynak Kârlılığı (Return on Equity): Şirketin kendi öz sermayesiyle ne kadar verimli kâr ürettiğini gösterir. Yüksek olması her zaman tercih sebebidir ve yönetimin kalitesini gösterir.")
    div_min = st.sidebar.slider("Minimum Temettü (%)", 0, 15, 4, help="Temettü Verimi: Şirketin dağıttığı kâr payının hisse fiyatına oranıdır. Yüksek ve düzenli temettü, nakit akışı güçlü, kârını paylaşan oturmuş şirketleri işaret eder.")
    mcap_min = st.sidebar.number_input("Min. Piyasa Değeri (Milyar TL)", value=10, help="Şirketin borsadaki toplam değeridir (Hisse Fiyatı x Toplam Hisse Adedi). Çok küçük şirketler spekülasyona açık olabilir, büyük tahtalar (şirketler) daha defansiftir.")

elif market_choice == "ABD Borsaları (Wall Street)":
    st.sidebar.subheader("ABD Filtreleri")
    pe_limit = st.sidebar.slider("Maksimum F/K", 5, 60, 25, help="Price/Earnings (P/E) Ratio: Şirketin kendini kaç yılda amorti edeceği. ABD teknoloji şirketlerinde büyüme beklentisinden dolayı BIST'e göre genelde daha yüksektir.")
    roe_min = st.sidebar.slider("Minimum ROE (%)", 0, 100, 25, help="Return on Equity: Şirketin sermayesini kullanma verimliliği. Yüksek olması rekabet avantajına sahip olduğunu gösterir.")
    div_min = st.sidebar.slider("Minimum Temettü (%)", 0.0, 10.0, 3.0, step=0.5, help="Dividend Yield: Dağıtılan nakit kâr payının hisse fiyatına oranı. ABD'de enflasyon düşük olduğundan %3-4 arası temettü verimi oldukça iyidir.")
    mcap_min = st.sidebar.number_input("Min. Piyasa Değeri (Milyar Dolar)", value=10, help="Şirketin toplam büyüklüğü (Market Cap). 10 Milyar $ ve üzeri şirketler 'Large Cap' (Büyük Ölçekli) olarak kabul edilir ve daha güvenlidir.")

else:
    st.sidebar.subheader("Fon Filtreleri")
    fund_return_min = st.sidebar.slider("Min. 1 Yıllık Getiri (%)", 30, 250, 80, help="Fonun son 1 yıl içinde (bugünden tam 365 gün geriye) yatırımcısına sağladığı net getiri oranıdır.")
    fund_mcap_min = st.sidebar.number_input("Min. Fon Büyüklüğü (Milyon TL)", value=500, help="Fonun yönettiği toplam paradır (AUM). 500 Milyon TL ve üzeri olması, tasfiye riskini düşürür ve yönetim gideri kesintilerinin yatırımcı başına düşen payını azaltır.")


# --- ARKA PLAN FONKSİYONLARI ---

@st.cache_data(ttl=600)
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

@st.cache_data(ttl=3600) 
def fetch_tefas_data():
    tefas = Crawler()
    bugun = datetime.now()
    # Hafta sonu ve resmi tatilleri atlamak için aralığı 10 güne çıkarıyoruz
    on_gun_once = bugun - timedelta(days=10)
    bir_yil_once = bugun - timedelta(days=365)
    bir_yil_on_gun_once = bir_yil_once - timedelta(days=10)
    
    try:
        # 1. Güncel Veri Çekimi
        guncel = tefas.fetch(start=on_gun_once.strftime("%Y-%m-%d"), end=bugun.strftime("%Y-%m-%d"), columns=["code", "title", "price", "market_cap", "number_of_investors"], kind="YAT")
        if guncel is None or guncel.empty or 'date' not in guncel.columns:
            raise ValueError("TEFAS şu an veri döndürmüyor (Sistem güncellemesi veya uzun tatil arası).")
            
        guncel['date'] = pd.to_datetime(guncel['date'])
        guncel_df = guncel[guncel['date'] == guncel['date'].max()].copy()
        
        # 2. Eski Veri Çekimi
        eski = tefas.fetch(start=bir_yil_on_gun_once.strftime("%Y-%m-%d"), end=bir_yil_once.strftime("%Y-%m-%d"), columns=["code", "price"], kind="YAT")
        if eski is None or eski.empty or 'date' not in eski.columns:
            raise ValueError("TEFAS 1 yıl önceki tarihi döndüremedi.")
            
        eski['date'] = pd.to_datetime(eski['date'])
        eski_df = eski[eski['date'] == eski['date'].max()].copy().rename(columns={"price": "eski_fiyat"})
        
        # 3. Portföy Dağılımı
        dagilim = tefas.fetch(start=on_gun_once.strftime("%Y-%m-%d"), end=bugun.strftime("%Y-%m-%d"), kind="YAT", columns=["code", "stock", "foreign_stock", "precious_metals"])
        if dagilim is None or dagilim.empty or 'date' not in dagilim.columns:
             dagilim_df = pd.DataFrame(columns=["code", "stock", "foreign_stock", "precious_metals"])
        else:
            dagilim['date'] = pd.to_datetime(dagilim['date'])
            dagilim_df = dagilim[dagilim['date'] == dagilim['date'].max()].copy()
        
        # 4. Birleştirme ve Matematik
        df = pd.merge(guncel_df, eski_df[['code', 'eski_fiyat']], on='code', how='inner')
        if not dagilim_df.empty:
            final_df = pd.merge(df, dagilim_df[['code', 'stock', 'foreign_stock', 'precious_metals']], on='code', how='left')
        else:
            final_df = df
            for col in ['stock', 'foreign_stock', 'precious_metals']: final_df[col] = 0
            
        for col in ['price', 'eski_fiyat', 'market_cap', 'number_of_investors', 'stock', 'foreign_stock', 'precious_metals']:
            if col in final_df.columns:
                final_df[col] = pd.to_numeric(final_df[col], errors='coerce')
                
        final_df['1Y_Getiri_%'] = ((final_df['price'] - final_df['eski_fiyat']) / final_df['eski_fiyat']) * 100
        return final_df
        
    except Exception as e:
        raise Exception(f"Sistem Hatası: {str(e)}")


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
        results = [{"Hisse": d['d'][0].replace("BIST:", ""), "Fiyat (TL)": d['d'][1], "F/K": round(d['d'][2],2) if d['d'][2] else "-", "ROE (%)": round(d['d'][3],2) if d['d'][3] else "-", "Temettü (%)": round(d['d'][4],2) if d['d'][4] else 0, "Borç/Özk.": round(d['d'][5],2) if d['d'][5] else "-", "PD (Milyar TL)": round(d['d'][6]/1e9, 2) if d['d'][6] else "-", "Sektör": d['d'][7]} for d in data]
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
        results = [{"Hisse": d['d'][0], "Fiyat ($)": d['d'][1], "F/K": round(d['d'][2],2) if d['d'][2] else "-", "ROE (%)": round(d['d'][3],2) if d['d'][3] else "-", "Temettü (%)": round(d['d'][4],2) if d['d'][4] else 0, "Borç/Özk.": round(d['d'][5],2) if d['d'][5] else "-", "PD (Milyar $)": round(d['d'][6]/1e9, 2) if d['d'][6] else "-", "Sektör": d['d'][7]} for d in data]
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
