# --- V14.0 FINAL: EFSANE GERI DONDU (OPENROUTER YEDEKLI SISTEM) ---
from flask import Flask, render_template, request, jsonify, send_file
import yfinance as yf
import pandas as pd
from openai import OpenAI
import os
import time

app = Flask(__name__)

# --- API AYARLARI ---
# Render'daki 'OPENROUTER_API_KEY' anahtarini alir
api_key = os.environ.get("OPENROUTER_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1"
)

# --- DENENECEK MODELLER LISTESI (HIZLIDAN YAVASA) ---
MODELS_TO_TRY = [
    "google/gemini-2.0-flash-exp:free",       # 1. En Hizli/Yeni
    "google/gemini-2.0-flash-thinking-exp:free", # 2. Dusunen Model
    "mistralai/mistral-7b-instruct:free",      # 3. Klasik
    "meta-llama/llama-3-8b-instruct:free",     # 4. Alternatif
    "microsoft/phi-3-mini-128k-instruct:free"  # 5. Yedek
]

# --- YARDIMCI FONKSİYONLAR ---
def safe_format_ratio(value):
    if value is None or not isinstance(value, (int, float)): return "-"
    if value < 0 or value > 1000: return "-"
    try: return f"{value:.2f}"
    except: return "-"

def rsi_hesapla(veri, periyot=14):
    delta = veri['Close'].diff()
    kazanc = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    kayip = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = kazanc / kayip
    return 100 - (100 / (1 + rs))

def macd_hesapla(veri, fast=12, slow=26, signal=9):
    veri['EMA_Fast'] = veri['Close'].ewm(span=fast, adjust=False).mean()
    veri['EMA_Slow'] = veri['Close'].ewm(span=26, adjust=False).mean()
    veri['MACD_Line'] = veri['EMA_Fast'] - veri['EMA_Slow']
    veri['Signal_Line'] = veri['MACD_Line'].ewm(span=signal, adjust=False).mean()
    return veri

def get_ai_summary(sembol, puan, rsi, fk, pddd):
    prompt = f"""
    Sen uzman bir Borsa ve Temel/Teknik analistsin. Sadece Türkçe, kesin, mantıklı ve tek bir paragraf halinde, 60 kelimeyi geçmeyecek şekilde şu analiz sonuçlarını yorumla:
    Hisse: {sembol}
    Algoritmik Puan (4 Üzerinden): {puan}
    RSI Değeri: {rsi:.2f}
    F/K Oranı: {fk}
    P/DD Oranı: {pddd}
    Yorum yaparken; F/K oranının 10'un altı ve P/DD oranının 2'nin altı olmasının güçlü pozitif temel sinyaller olduğunu kesinlikle belirt ve buna göre yorum yap. Eğer oranlar ' - ' ise, yorum yapma.
    """
    
    for model in MODELS_TO_TRY:
        try:
            completion = client.chat.completions.create(
                model=model, 
                messages=[
                    {"role": "system", "content": "Sen uzman bir Borsa analisti ve asistanısın. Türkçe cevap ver."},
                    {"role": "user", "content": prompt}
                ],
                extra_headers={"HTTP-Referer": "https://borsacin.com", "X-Title": "BorsaBot"}
            )
            return completion.choices[0].message.content
        except:
            time.sleep(1) # Hata alirsa 1 saniye bekle
            continue
            
    return "Otomatik analiz özeti şu an alınamıyor (Sunucular yoğun)."

# --- ROUTE'LAR ---
@app.route('/download_csv/<sembol>')
def download_csv(sembol):
    try:
        arama_kodu = sembol if ".IS" in sembol else sembol + ".IS"
        hisse = yf.Ticker(arama_kodu)
        df = hisse.history(period="1y")
        csv_path = f"{sembol}_analysis_data.csv"
        df.to_csv(csv_path)
        response = send_file(csv_path, mimetype='text/csv', as_attachment=True, download_name=f'{sembol}_Analiz_Verisi.csv')
        os.remove(csv_path)
        return response
    except Exception as e: return "Hata oluştu.", 400

@app.route('/market_summary', methods=['GET'])
def market_summary():
    tickers = ['XU100.IS', 'AKBNK.IS', 'ARCLK.IS', 'ASELS.IS', 'BIMAS.IS', 'EKGYO.IS', 'EREGL.IS', 'FROTO.IS', 'GARAN.IS', 'GOLTS.IS', 'HEKTS.IS', 'ISCTR.IS', 'KCHOL.IS', 'KOZAL.IS', 'KRDMD.IS', 'MGROS.IS', 'ODAS.IS', 'PETKM.IS', 'PGSUS.IS', 'SAHOL.IS', 'SASA.IS', 'SISE.IS', 'TAVHL.IS', 'TCELL.IS', 'THYAO.IS', 'TOASO.IS', 'TUPRS.IS', 'YKBNK.IS', 'HALKB.IS', 'VAKBN.IS']
    summary_data = []
    try:
        data = yf.download(tickers, period="2d", interval="1h")
        for ticker_code in tickers:
            if ticker_code in data['Close']:
                close_data = data['Close'][ticker_code].dropna()
                if len(close_data) >= 2: latest_close, prev_close = close_data.iloc[-1], close_data.iloc[0]
                else: latest_close, prev_close = close_data.iloc[-1] if not close_data.empty else 0
                change_percent = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                symbol_display = ticker_code.replace('.IS', '').replace('XU100', 'BIST100')
                summary_data.append({'symbol': symbol_display, 'price': f"{latest_close:,.2f}", 'change': f"{change_percent:+.2f}%", 'color': 'green' if change_percent > 0 else ('red' if change_percent < 0 else 'gray')})
        return jsonify(summary_data)
    except: return jsonify([{'symbol': 'HATA', 'price': '-', 'change': '-', 'color': 'red'}])

def get_top_list_data(reverse_sort=True, sort_by='change'):
    bist100_tickers = ['AKBNK.IS', 'ARCLK.IS', 'ASELS.IS', 'BIMAS.IS', 'EKGYO.IS', 'EREGL.IS', 'FROTO.IS', 'GARAN.IS', 'GOLTS.IS', 'HEKTS.IS', 'ISCTR.IS', 'KCHOL.IS', 'KOZAL.IS', 'KRDMD.IS', 'MGROS.IS', 'ODAS.IS', 'PETKM.IS', 'PGSUS.IS', 'SAHOL.IS', 'SASA.IS', 'SISE.IS', 'TAVHL.IS', 'TCELL.IS', 'THYAO.IS', 'TOASO.IS', 'TUPRS.IS', 'YKBNK.IS', 'HALKB.IS', 'VAKBN.IS', 'CCOLA.IS', 'DOHOL.IS']
    final_list = []
    try:
        data_price = yf.download(bist100_tickers, period="2d", interval="1d")
        data_volume = yf.download(bist100_tickers, period="1d", interval="1h")
        for ticker_code in bist100_tickers:
            if ticker_code in data_price['Close']:
                close_data = data_price['Close'][ticker_code].dropna()
                volume_data = data_volume['Volume'][ticker_code].dropna()
                latest_close = close_data.iloc[-1] if not close_data.empty else 0
                prev_close = close_data.iloc[-2] if len(close_data) >=2 else latest_close
                change_percent = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                latest_volume = volume_data.iloc[-1] if not volume_data.empty else 0
                hisse_info = yf.Ticker(ticker_code).info
                price = hisse_info.get('regularMarketPrice', latest_close)
                volume_tl = latest_volume * price if latest_volume > 0 else 0
                final_list.append({'symbol': ticker_code.replace('.IS', ''), 'price': f"{latest_close:,.2f}", 'change': change_percent, 'change_display': f"{change_percent:+.2f}%", 'volume_value': volume_tl, 'volume_display': f"{volume_tl / 1000000:,.2f} M ₺"})
        if sort_by == 'change': sorted_list = sorted(final_list, key=lambda x: x['change'], reverse=reverse_sort)
        else: sorted_list = sorted(final_list, key=lambda x: x['volume_value'], reverse=reverse_sort)
        return sorted_list[:15]
    except: return []

@app.route('/top_gainers')
def top_gainers(): return render_template('gainers.html', gainers=get_top_list_data(reverse_sort=True, sort_by='change'))
@app.route('/top_losers')
def top_losers(): return render_template('losers.html', losers=get_top_list_data(reverse_sort=False, sort_by='change'))
@app.route('/top_volume')
def top_volume(): return render_template('volume.html', volumes=get_top_list_data(reverse_sort=True, sort_by='volume'))

@app.route('/', methods=['GET', 'POST'])
def home():
    sonuc, chart_data, ai_summary = None, None, None
    if request.method == 'POST' and 'sembol' in request.form:
        try:
            sembol = request.form.get('sembol').upper()
            arama_kodu = sembol if ".IS" in sembol else sembol + ".IS"
            hisse = yf.Ticker(arama_kodu)
            df = hisse.history(period="6mo")
            if df.empty: raise ValueError("Veri yok")
            guncel_fiyat = df['Close'].iloc[-1]
            df['RSI'] = rsi_hesapla(df)
            guncel_rsi = df['RSI'].iloc[-1]
            macd_data = macd_hesapla(df)
            bilgi = hisse.info
            fk_val = bilgi.get('trailingPE')
            pddd_val = bilgi.get('priceToBook')
            puan = 0
            if guncel_rsi < 30: puan += 1
            if macd_data['MACD_Line'].iloc[-1] > macd_data['Signal_Line'].iloc[-1]: puan += 1
            if fk_val and fk_val < 10: puan += 1
            if pddd_val and pddd_val < 2: puan += 1
            sinyal_yorum = ["SAT 🔴", "SAT 🔴", "NÖTR 🟠", "AL 🟡", "GÜÇLÜ AL 🟢"][puan]
            ai_summary = get_ai_summary(sembol, puan, guncel_rsi, safe_format_ratio(fk_val), safe_format_ratio(pddd_val))
            chart_data_list = [{'x': index.value // 10**6, 'y': [row['Open'], row['High'], row['Low'], row['Close']]} for index, row in df.iterrows()]
            sonuc = {
                'isim': sembol, 
                'fiyat': f"{guncel_fiyat:.2f}", 
                'fk': safe_format_ratio(fk_val), 
                'pddd': safe_format_ratio(pddd_val), 
                'rsi': f"{guncel_rsi:.2f}", 
                'puan': puan, 
                'sinyal_yorum': sinyal_yorum, 
                'sinyal_rsi_renk': 'green' if guncel_rsi < 30 else 'red', 
                'macd_line': f"{macd_data['MACD_Line'].iloc[-1]:.2f}", 
                'signal_line': f"{macd_data['Signal_Line'].iloc[-1]:.2f}", 
                'sinyal_macd_renk': 'green' if macd_data['MACD_Line'].iloc[-1] > macd_data['Signal_Line'].iloc[-1] else 'red'
            }
        except Exception: 
            sonuc = {'hata': "Veri çekilemedi."}
            ai_summary = "Hata."
    return render_template('index.html', veri=sonuc, chart_data=chart_data, ai_summary=ai_summary)

# --- CHATBOT ROUTE (YEDEKLI SISTEM) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message')
    
    for model_name in MODELS_TO_TRY:
        try:
            print(f"Denenen Model: {model_name}") 
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": "Sen borsa asistanısın. Türkçe konuş."}, {"role": "user", "content": user_message}],
                extra_headers={"HTTP-Referer": "https://borsacin.com", "X-Title": "BorsaBot"}
            )
            return jsonify({'reply': completion.choices[0].message.content})
        except Exception as e:
            error_msg = str(e)
            print(f"HATA ({model_name}): {error_msg}")
            
            if "401" in error_msg:
                 return jsonify({'reply': "⚠️ HATA: Render'daki ŞİFRE YANLIŞ! Kontrol et."})
            
            time.sleep(1) # Spam olmamasi icin bekle
            continue

    return jsonify({'reply': "⚠️ Şu an tüm AI modelleri aşırı yoğun. Lütfen 30 saniye sonra tekrar deneyin."})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')