# --- V5.0 FINAL SÜRÜM: KESİN ÇÖZÜM ---
from flask import Flask, render_template, request, jsonify, send_file
import yfinance as yf
import pandas as pd
from openai import OpenAI
import os

app = Flask(__name__)

# --- API AYARLARI (ZORUNLU OPENAI ADRESİ) ---
# Burada sadece OpenAI anahtarını alıyoruz.
api_key = os.environ.get("OPENAI_API_KEY")

# İŞTE ÇÖZÜM BURASI:
# base_url'i elle 'https://api.openai.com/v1' olarak girdik.
# Artık kod istese de OpenRouter'a gidemez.
client = OpenAI(
    api_key=api_key,
    base_url="https://api.openai.com/v1"
)

# --- YARDIMCI FONKSİYONLAR ---

def safe_format_ratio(value):
    """F/K, P/DD için güvenli formatlama yapar."""
    if value is None or not isinstance(value, (int, float)): return "-"
    if value < 0 or value > 1000: return "-"
    try: return f"{value:.2f}"
    except: return "-"

def rsi_hesapla(veri, periyot=14):
    """RSI hesaplar."""
    delta = veri['Close'].diff()
    kazanc = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    kayip = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = kazanc / kayip
    return 100 - (100 / (1 + rs))

def macd_hesapla(veri, fast=12, slow=26, signal=9):
    """MACD hesaplar."""
    veri['EMA_Fast'] = veri['Close'].ewm(span=fast, adjust=False).mean()
    veri['EMA_Slow'] = veri['Close'].ewm(span=26, adjust=False).mean()
    veri['MACD_Line'] = veri['EMA_Fast'] - veri['EMA_Slow']
    veri['Signal_Line'] = veri['MACD_Line'].ewm(span=signal, adjust=False).mean()
    return veri

def get_ai_summary(sembol, puan, rsi, fk, pddd):
    """Analiz sonuçlarını Yapay Zekaya yorumlatır."""
    prompt = f"""
    Sen uzman bir Borsa ve Temel/Teknik analistsin. Sadece Türkçe, kesin, mantıklı ve tek bir paragraf halinde, 60 kelimeyi geçmeyecek şekilde şu analiz sonuçlarını yorumla:
    Hisse: {sembol}
    Algoritmik Puan (4 Üzerinden): {puan}
    RSI Değeri: {rsi:.2f}
    F/K Oranı: {fk}
    P/DD Oranı: {pddd}
    Yorum yaparken; F/K oranının 10'un altı ve P/DD oranının 2'nin altı olmasının güçlü pozitif temel sinyaller olduğunu kesinlikle belirt ve buna göre yorum yap. Eğer oranlar ' - ' ise, yorum yapma.
    """
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": "Sen uzman bir Borsa analisti ve asistanısın. Türkçe, **dilbilgisi ve yazım kurallarına %100 uygun** cevap ver."},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Otomatik AI Özeti Hatası: {e}")
        return "Otomatik analiz özeti alınamadı (API Hatası)."


# --- CSV İNDİRME ROUTE'U ---
@app.route('/download_csv/<sembol>')
def download_csv(sembol):
    try:
        arama_kodu = sembol if ".IS" in sembol else sembol + ".IS"
        hisse = yf.Ticker(arama_kodu)
        df = hisse.history(period="1y")

        csv_path = f"{sembol}_analysis_data.csv"
        df.to_csv(csv_path)

        response = send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{sembol}_Analiz_Verisi.csv'
        )
        os.remove(csv_path)
        return response

    except Exception as e:
        print(f"CSV İndirme Hatası: {e}")
        return "Veri indirilirken bir hata oluştu.", 400


# --- PİYASA ÖZETİ ÇEKME ROUTE'U ---
@app.route('/market_summary', methods=['GET'])
def market_summary():
    """BIST 100 ve BIST 30 hisselerinin anlık özetini tek sorguyla çeker."""
    
    tickers = [
        'XU100.IS', 'AKBNK.IS', 'ARCLK.IS', 'ASELS.IS', 'BIMAS.IS', 'EKGYO.IS', 'EREGL.IS', 'FROTO.IS', 
        'GARAN.IS', 'GOLTS.IS', 'HEKTS.IS', 'ISCTR.IS', 'KCHOL.IS', 'KOZAL.IS', 'KRDMD.IS', 'MGROS.IS', 
        'ODAS.IS', 'PETKM.IS', 'PGSUS.IS', 'SAHOL.IS', 'SASA.IS', 'SISE.IS', 'TAVHL.IS', 'TCELL.IS', 
        'THYAO.IS', 'TOASO.IS', 'TUPRS.IS', 'YKBNK.IS', 'HALKB.IS', 'VAKBN.IS'
    ]
    summary_data = []

    try:
        data = yf.download(tickers, period="2d", interval="1h")

        for ticker_code in tickers:
            if ticker_code in data['Close']:
                close_data = data['Close'][ticker_code].dropna()

                if len(close_data) >= 2:
                    latest_close = close_data.iloc[-1]
                    prev_close = close_data.iloc[0] 
                else:
                    latest_close = close_data.iloc[-1] if not close_data.empty else 0
                    prev_close = close_data.iloc[-1] if not close_data.empty else 0

                change_percent = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 and prev_close != latest_close else 0
                
                symbol_display = ticker_code.replace('.IS', '').replace('XU100', 'BIST100')
                
                summary_data.append({
                    'symbol': symbol_display,
                    'price': f"{latest_close:,.2f}",
                    'change': f"{change_percent:+.2f}%", 
                    'color': 'green' if change_percent > 0 else ('red' if change_percent < 0 else 'gray')
                })
        
        return jsonify(summary_data)

    except Exception as e:
        print(f"Piyasa Özeti Hatası: {e}")
        return jsonify([{'symbol': 'BIST100', 'price': 'HATA', 'change': 'Kontrol', 'color': 'red'}])

# --- TOP LİSTELER İÇİN YARDIMCI FONKSİYON ---
def get_top_list_data(reverse_sort=True, sort_by='change'):
    bist100_tickers = [
        'AKBNK.IS', 'ARCLK.IS', 'ASELS.IS', 'BIMAS.IS', 'EKGYO.IS', 'EREGL.IS', 'FROTO.IS', 
        'GARAN.IS', 'GOLTS.IS', 'HEKTS.IS', 'ISCTR.IS', 'KCHOL.IS', 'KOZAL.IS', 'KRDMD.IS', 
        'MGROS.IS', 'ODAS.IS', 'PETKM.IS', 'PGSUS.IS', 'SAHOL.IS', 'SASA.IS', 'SISE.IS', 
        'TAVHL.IS', 'TCELL.IS', 'THYAO.IS', 'TOASO.IS', 'TUPRS.IS', 'YKBNK.IS', 'HALKB.IS', 'VAKBN.IS',
        'CCOLA.IS', 'DOHOL.IS' 
    ]
    
    final_list = []
    
    try:
        data_price = yf.download(bist100_tickers, period="2d", interval="1d")
        data_volume = yf.download(bist100_tickers, period="1d", interval="1h")

        for ticker_code in bist100_tickers:
            if ticker_code in data_price['Close']:
                close_data = data_price['Close'][ticker_code].dropna()
                volume_data = data_volume['Volume'][ticker_code].dropna()
                
                if len(close_data) >= 2:
                    latest_close = close_data.iloc[-1]
                    prev_close = close_data.iloc[-2]
                    change_percent = ((latest_close - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                else:
                    latest_close, change_percent = 0, 0
                
                latest_volume = volume_data.iloc[-1] if not volume_data.empty else 0
                
                # Hacim hesaplama (Basit yaklaşım)
                hisse_info = yf.Ticker(ticker_code).info
                current_price_for_vol_calc = hisse_info.get('regularMarketPrice', latest_close)
                volume_tl = latest_volume * current_price_for_vol_calc if latest_volume > 0 else 0


                final_list.append({
                    'symbol': ticker_code.replace('.IS', ''),
                    'price': f"{latest_close:,.2f}",
                    'change': change_percent, 
                    'change_display': f"{change_percent:+.2f}%", 
                    'volume_value': volume_tl,
                    'volume_display': f"{volume_tl / 1000000:,.2f} M ₺",
                })

        if sort_by == 'change':
            sorted_list = sorted(final_list, key=lambda x: x['change'], reverse=reverse_sort)
        elif sort_by == 'volume':
            sorted_list = sorted(final_list, key=lambda x: x['volume_value'], reverse=reverse_sort)
        
        return sorted_list[:15] 

    except Exception as e:
        print(f"Top List Çekim Hatası: {e}")
        return []


# --- TOP LİSTELERİN ROUTE'LARI ---
@app.route('/top_gainers')
def top_gainers():
    data = get_top_list_data(reverse_sort=True, sort_by='change')
    return render_template('gainers.html', gainers=data)

@app.route('/top_losers')
def top_losers():
    data = get_top_list_data(reverse_sort=False, sort_by='change')
    return render_template('losers.html', losers=data)

@app.route('/top_volume')
def top_volume():
    data = get_top_list_data(reverse_sort=True, sort_by='volume')
    return render_template('volume.html', volumes=data)


# --- ANA ROUTE ---
@app.route('/', methods=['GET', 'POST'])
def home():
    sonuc = None
    chart_data = None
    ai_summary = None 
    
    if request.method == 'POST' and 'sembol' in request.form:
        try:
            sembol = request.form.get('sembol').upper()
            try:
                lot_sayisi = int(request.form.get('adet'))
            except:
                lot_sayisi = 1

            arama_kodu = sembol if ".IS" in sembol else sembol + ".IS"
            
            hisse = yf.Ticker(arama_kodu)
            df = hisse.history(period="6mo") 
            guncel_fiyat = df['Close'].iloc[-1]
            
            # TEKNİK ANALİZ
            df['RSI'] = rsi_hesapla(df)
            guncel_rsi = df['RSI'].iloc[-1]
            macd_data = macd_hesapla(df)
            
            # TEMEL ANALİZ
            bilgi = hisse.info
            fk_val = bilgi.get('trailingPE') 
            pddd_val = bilgi.get('priceToBook')
            
            # --- ALGORİTMİK PUANLAMA ---
            puan = 0
            if guncel_rsi < 30: puan += 1
            if macd_data['MACD_Line'].iloc[-1] > macd_data['Signal_Line'].iloc[-1]: puan += 1
            if fk_val is not None and fk_val < 10 and fk_val > 0: puan += 1
            if pddd_val is not None and pddd_val < 2 and pddd_val > 0: puan += 1

            
            # Nihai Puan Yorumu
            sinyal_yorum = ""
            if puan == 4: sinyal_yorum = "MÜKEMMEL AL 🟢"
            elif puan >= 3: sinyal_yorum = "GÜÇLÜ AL 🟡"
            elif puan == 2: sinyal_yorum = "NÖTR / İNCELE 🟠"
            else: sinyal_yorum = "DİKKATLİ OL 🔴"
            
            # AI ÖZETİNİ ÇEKME
            ai_summary = get_ai_summary(
                sembol, 
                puan, 
                guncel_rsi,
                safe_format_ratio(fk_val),
                safe_format_ratio(pddd_val)
            )

            # GRAFİK VERİSİNİ HAZIRLA
            chart_data_list = []
            for index, row in df.iterrows():
                chart_data_list.append({
                    'x': index.value // 10**6, 
                    'y': [row['Open'], row['High'], row['Low'], row['Close']] 
                })
            chart_data = chart_data_list

            sonuc = {
                'isim': sembol,
                'fiyat': f"{guncel_fiyat:.2f}",
                'toplam_tutar': f"{guncel_fiyat * lot_sayisi:,.2f}",
                'fk': safe_format_ratio(fk_val), 
                'pddd': safe_format_ratio(pddd_val), 
                'rsi': f"{guncel_rsi:.2f}",
                'sinyal_rsi_renk': "#28a745" if guncel_rsi < 30 else ("#dc3545" if guncel_rsi > 70 else "#666"),
                'macd_line': f"{macd_data['MACD_Line'].iloc[-1]:.2f}",
                'signal_line': f"{macd_data['Signal_Line'].iloc[-1]:.2f}",
                'sinyal_macd_renk': "#007bff" if macd_data['MACD_Line'].iloc[-1] > macd_data['Signal_Line'].iloc[-1] else "#dc3545",
                'puan': puan,
                'sinyal_yorum': sinyal_yorum,
            }
        except Exception as e:
            print(f"Borsa Veri Hatası: {e}")
            sonuc = {'hata': "Hisse bulunamadı veya veri çekilemedi. Lütfen kodu kontrol edin."}
            ai_summary = "Veri hatası."
    
    return render_template('index.html', veri=sonuc, chart_data=chart_data, ai_summary=ai_summary)

# --- YAPAY ZEKA ROUTE'U (CHATBOT) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message')
    
    try:
        completion = client.chat.completions.create(
            # MODEL: OpenAI gpt-4o-mini
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen uzman bir Borsa asistanısın. Türkçe, **dilbilgisi ve yazım kurallarına %100 uygun** cevap ver."},
                {"role": "user", "content": user_message}
            ]
        )
        return jsonify({'reply': completion.choices[0].message.content})
    except Exception as e:
        print(f"AI Chat Hatası: {e}")
        # Hata mesajını kullanıcıya daha tatlı gösterelim
        if "401" in str(e):
             return jsonify({'reply': "⚠️ Hata: OPENAI_API_KEY hatalı veya bakiyesi yok. Lütfen OpenAI panelini kontrol et."})
        
        # Eğer para yoksa (Quota hatası)
        if "insufficient_quota" in str(e):
             return jsonify({'reply': "⚠️ Hata: OpenAI hesabında kredi (bakiye) yok. Minimum 5$ yükleme yapılması gerekiyor."})
             
        return jsonify({'reply': f"Bağlantı hatası: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')