# --- V14.5 FINAL: EFSANE GERİ DÖNDÜ (AKBNK & GERÇEK FAILOVER) ---
from flask import Flask, render_template, request, jsonify, send_file
import yfinance as yf
import pandas as pd
from openai import OpenAI
import os
import time

app = Flask(__name__)

# --- API AYARLARI ---
api_key = os.environ.get("OPENROUTER_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1"
)

# --- DENENECEK MODELLER (Sıralama Kararlılığa Göre Yapıldı) ---
MODELS_TO_TRY = [
    "google/gemini-2.0-flash-exp:free",      # 1. En Hızlı [cite: 53]
    "google/gemini-2.0-flash-thinking-exp:free", # 2. Düşünen Model [cite: 53]
    "qwen/qwen-2.5-72b-instruct:free",       # 3. Çok Kararlı Yedek
    "mistralai/mistral-7b-instruct:free",      # 4. Klasik Yedek [cite: 53]
    "meta-llama/llama-3-8b-instruct:free",     # 5. Alternatif [cite: 35]
    "microsoft/phi-3-mini-128k-instruct:free"  # 6. Son Çare
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
    # AKBNK Odaklı ve Kesin Talimatlı Prompt [cite: 38, 66]
    prompt = f"""
    Sen uzman bir borsa analistisin. (AKBNK stilinde analiz yap).
    Sadece Türkçe, kesin ve tek bir paragraf (max 60 kelime) olarak yorumla:
    Hisse: {sembol}, Puan: {puan}/4, RSI: {rsi:.2f}, F/K: {fk}, P/DD: {pddd}.
    F/K < 10 ve P/DD < 2 ise güçlü pozitif olduğunu belirt. Oranlar '-' ise yorum yapma. [cite: 66]
    """
    
    for model in MODELS_TO_TRY:
        try:
            print(f"📡 {model} deneniyor...")
            completion = client.chat.completions.create(
                model=model, 
                messages=[
                    {"role": "system", "content": "Sen profesyonel bir borsa asistanısın. Kısa ve öz cevap ver."},
                    {"role": "user", "content": prompt}
                ],
                timeout=15, # 15 saniye kuralı: Cevap yoksa diğer modele geç!
                extra_headers={"HTTP-Referer": "https://borsacin.com", "X-Title": "BorsaBot"}
            )
            if completion.choices[0].message.content:
                return completion.choices[0].message.content
        except Exception as e:
            print(f"⚠️ {model} hatası: {str(e)}")
            time.sleep(1) # Hata toleransı beklemesi [cite: 35]
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
    except: return "Hata oluştu.", 400

@app.route('/market_summary', methods=['GET'])
def market_summary():
    # AKBNK en başta!
    tickers = ['XU100.IS', 'AKBNK.IS', 'GARAN.IS', 'THYAO.IS', 'ISCTR.IS', 'YKBNK.IS', 'SISE.IS', 'EREGL.IS']
    summary_data = []
    try:
        data = yf.download(tickers, period="2d", interval="1h")
        for ticker_code in tickers:
            if ticker_code in data['Close']:
                close_data = data['Close'][ticker_code].dropna()
                latest_close = close_data.iloc[-1] if not close_data.empty else 0
                prev_close = close_data.iloc[0] if len(close_data) >= 2 else latest_close
                change_percent = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                symbol_display = ticker_code.replace('.IS', '').replace('XU100', 'BIST100')
                summary_data.append({
                    'symbol': symbol_display, 
                    'price': f"{latest_close:,.2f}", 
                    'change': f"{change_percent:+.2f}%", 
                    'color': 'green' if change_percent > 0 else 'red'
                })
        return jsonify(summary_data)
    except: return jsonify([])

@app.route('/', methods=['GET', 'POST'])
def home():
    sonuc, chart_data, ai_summary = None, None, None
    if request.method == 'POST' and 'sembol' in request.form:
        try:
            sembol = request.form.get('sembol').upper()
            if not sembol: sembol = "AKBNK" # Boş bırakılırsa AKBNK yap
            arama_kodu = sembol if ".IS" in sembol else sembol + ".IS"
            
            hisse = yf.Ticker(arama_kodu)
            df = hisse.history(period="6mo")
            if df.empty: raise ValueError()
            
            guncel_fiyat = df['Close'].iloc[-1]
            df['RSI'] = rsi_hesapla(df)
            guncel_rsi = df['RSI'].iloc[-1]
            macd_data = macd_hesapla(df)
            
            bilgi = hisse.info
            fk = bilgi.get('trailingPE')
            pddd = bilgi.get('priceToBook')
            
            puan = 0
            if guncel_rsi < 30: puan += 1
            if macd_data['MACD_Line'].iloc[-1] > macd_data['Signal_Line'].iloc[-1]: puan += 1
            if fk and fk < 10: puan += 1
            if pddd and pddd < 2: puan += 1
            
            sinyal_yorum = ["SAT 🔴", "SAT 🔴", "NÖTR 🟠", "AL 🟡", "GÜÇLÜ AL 🟢"][puan]
            ai_summary = get_ai_summary(sembol, puan, guncel_rsi, safe_format_ratio(fk), safe_format_ratio(pddd))
            
            sonuc = {
                'isim': sembol, 'fiyat': f"{guncel_fiyat:.2f}", 
                'fk': safe_format_ratio(fk), 'pddd': safe_format_ratio(pddd), 
                'rsi': f"{guncel_rsi:.2f}", 'puan': puan, 'sinyal_yorum': sinyal_yorum
            }
        except:
            sonuc = {'hata': "Hisse bulunamadı."}
            
    return render_template('index.html', veri=sonuc, ai_summary=ai_summary)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    msg = data.get('message', '')
    
    # AKBNK bağlamı eklenmiş sistem mesajı [cite: 38]
    sys_msg = "Sen uzman borsa asistanısın. AKBNK ve bankacılık hisselerinde çok bilgilisin. Türkçe cevap ver."
    
    for model in MODELS_TO_TRY:
        try:
            print(f"💬 Sohbet deneniyor: {model}")
            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": msg}],
                timeout=15,
                extra_headers={"HTTP-Referer": "https://borsacin.com", "X-Title": "BorsaBot"}
            )
            if res.choices[0].message.content:
                return jsonify({'reply': res.choices[0].message.content})
        except:
            time.sleep(1)
            continue

    return jsonify({'reply': "⚠️ AI şu an yoğun. Lütfen 30 sn sonra tekrar dene."})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')