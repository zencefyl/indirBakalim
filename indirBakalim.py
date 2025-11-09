import streamlit as st
from yt_dlp import YoutubeDL
import requests
from PIL import Image
from io import BytesIO
import tempfile
import os
from datetime import timedelta
import re
import time
import shutil

# --- Yardımcı Fonksiyonlar ---

def format_duration(seconds):
    """Saniyeyi okunabilir formata çevirir (HH:MM:SS)"""
    if not seconds:
        return "Bilinmiyor"
    td = timedelta(seconds=int(seconds))
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def validate_time_format(time_str):
    """Zaman formatını HH:MM:SS veya MM:SS olarak kontrol et"""
    if not time_str:
        return True
    pattern = r'^(\d{1,2}:)?\d{1,2}:\d{2}$'
    return bool(re.match(pattern, time_str))

def get_format_code(display_name):
    """Görünen adı yt-dlp format koduna eşler"""
    format_map = {
        "En İyi Kalite (Video+Ses)": "bestvideo+bestaudio/best",
        "MP4 (Video)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
        "MP3 (Ses)": "bestaudio[ext=m4a]/bestaudio",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    }
    return format_map.get(display_name, "best")

def fetch_and_display_preview(url):
    """Video bilgilerini alır ve state'i günceller."""
    # State'i sıfırla
    st.session_state['download_ready'] = False
    st.session_state['video_info'] = None
    
    if not url.strip():
        st.error("Lütfen bir URL girin!")
        return

    with st.spinner("Video bilgileri alınıyor..."):
        try:
            ydl_opts_preview = {'quiet': True, 'skip_download': True, 'force_generic_extractor': True, 'noprogress': True}
            with YoutubeDL(ydl_opts_preview) as ydl:
                info = ydl.extract_info(url, download=False)

            title = info.get("title", "Başlık Bilinmiyor")
            duration = info.get("duration", 0)
            duration_str = format_duration(duration)
            uploader = info.get("uploader", "Bilinmiyor")
            thumb_url = info.get("thumbnail")
            
            # Bilgileri session state'e kaydet
            st.session_state['video_info'] = info
            st.session_state['download_ready'] = True
            
            # Önizleme Alanı
            st.success("✅ Video Bilgileri Başarılı")
            st.subheader(title)
            st.write(f"**Yükleyen:** {uploader} | **Süre:** {duration_str}")
            
            if thumb_url:
                st.image(thumb_url, width=320)
            
        except Exception as e:
            st.error(f"❌ Video bilgisi alınamadı. URL'yi kontrol edin. Hata: {e}")
            st.session_state['download_ready'] = False

# --- Ana Streamlit Uygulaması ---

st.set_page_config(
    page_title="indirBakalım - Web YouTube İndirici",
    layout="wide", # Geniş ekran düzeni için
    initial_sidebar_state="auto"
)

st.title("▶️ indirBakalım - Web YouTube İndirici")
st.markdown("---")

# Oturum Durumu Değişkenlerini Başlat
if 'download_ready' not in st.session_state:
    st.session_state['download_ready'] = False
if 'video_info' not in st.session_state:
    st.session_state['video_info'] = None
if 'url_input' not in st.session_state:
    st.session_state['url_input'] = ""
if 'start_time' not in st.session_state:
    st.session_state['start_time'] = ""
if 'end_time' not in st.session_state:
    st.session_state['end_time'] = ""
    
# --- UI: URL Girişi ve Buton ---

url_input = st.text_input(
    "YouTube Video URL'sini Girin:", 
    key="url_input_widget",
    value=st.session_state.url_input,
    placeholder="https://youtu.be/..."
)

# URL değiştiğinde veya Enter'a basıldığında state'i güncelle
if url_input != st.session_state.url_input:
    st.session_state.url_input = url_input
    # URL değiştiğinde önizleme otomatik tetiklenebilir veya butona basılması beklenebilir.
    # Şimdilik, sadece URL değişince önizleme durumunu sıfırlayalım.
    st.session_state['download_ready'] = False
    st.session_state['video_info'] = None
    
# 'Video Bilgilerini Getir' Butonu (Önizle yerine daha açıklayıcı)
if st.button("🔎 Video Bilgilerini Getir", type="secondary"):
    fetch_and_display_preview(st.session_state.url_input)

st.markdown("---")

# --- UI: Ayarlar (Önizleme Başarılıysa Görüntülenir) ---

if st.session_state['download_ready'] and st.session_state['video_info']:
    
    st.subheader("İndirme Ayarları")
    
    # 3 Sütunlu Düzen (Format + Başlangıç + Bitiş)
    col_format, col_start_time, col_end_time = st.columns(3)
    
    # Sütun 1: Format Seçimi
    with col_format:
        format_options = [
            "En İyi Kalite (Video+Ses)", 
            "MP4 (Video)", 
            "MP3 (Ses)",
            "720p",
            "480p"
        ]
        selected_format = st.selectbox(
            "Format Seçimi:",
            options=format_options,
            index=0,
            key="format_select"
        )
        
    # Sütun 2: Başlangıç Zamanı
    with col_start_time:
        st.markdown("Başlangıç (HH:MM:SS veya MM:SS):")
        # Text Input'a bir key vererek state'ini koruyoruz.
        st.session_state.start_time = st.text_input(
            " ",
            value=st.session_state.start_time, 
            key="start_time_widget", 
            label_visibility="collapsed",
            placeholder="00:00:00"
        )
        
    # Sütun 3: Bitiş Zamanı
    with col_end_time:
        st.markdown("Bitiş (HH:MM:SS veya MM:SS):")
        # Text Input'a bir key vererek state'ini koruyoruz.
        st.session_state.end_time = st.text_input(
            "  ",
            value=st.session_state.end_time,
            key="end_time_widget", 
            label_visibility="collapsed",
            placeholder="00:01:30"
        )

    st.markdown("---")

    # --- UI: İndir Butonu ---

    if st.button("⬇️ İndirmeyi Başlat", type="primary"):
        
        # --- VALIDASYONLAR ---
        start = st.session_state.start_time
        end = st.session_state.end_time
        
        if (start and not end) or (end and not start):
            st.error("Kesim yapmak için hem Başlangıç hem Bitiş zamanı girilmelidir.")
            st.stop()
        if not validate_time_format(start) or not validate_time_format(end):
            st.error("Zaman formatı hatalı. Lütfen HH:MM:SS veya MM:SS kullanın.")
            st.stop()

        # Streamlit Cloud'da /tmp klasörü kullanmak en güvenli yoldur.
        with tempfile.TemporaryDirectory() as temp_dir:
            
            status_box = st.info("İndirme işlemi başlatılıyor...")
            
            try:
                video_info = st.session_state['video_info']
                
                # Dosya adı temizlenmiş
                base_filename = re.sub(r'[^\w\-_\. ]', '', video_info.get("title", "video"))
                output_template = os.path.join(temp_dir, base_filename + '.%(ext)s')

                format_code = get_format_code(selected_format)
                
                ydl_opts_download = {
                    'format': format_code,
                    'outtmpl': output_template,
                    'quiet': True,
                    'noprogress': True,
                    'postprocessors': [],
                }
                
                # Zaman Aralığı (Kesme)
                if start and end:
                    status_box.info(f"İndirme başlatıldı: Kesim aralığı {start}-{end}")
                    ydl_opts_download['download_sections'] = [f"*{start}-{end}"]
                
                # MP3 formatı için Post-Processor
                if selected_format == "MP3 (Ses)":
                    status_box.info("İndirme başlatıldı: Ses formatına dönüştürülüyor (MP3).")
                    ydl_opts_download['postprocessors'].append({
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    })
                
                status_box.info("Video indiriliyor ve işleniyor. Bu işlem, videonun uzunluğuna göre zaman alabilir...")

                # İndirme İşlemini Gerçekleştir
                with YoutubeDL(ydl_opts_download) as ydl:
                    ydl.download([st.session_state.url_input])
                
                status_box.success("✅ İndirme ve İşlem Başarılı! Dosya hazırlanıyor...")
                
                # İndirilen dosyayı bul (temp_dir içinde)
                # ffmpeg/post-processor uzantıyı değiştirebilir, bu yüzden klasörü kontrol etmeliyiz.
                downloaded_files = [f for f in os.listdir(temp_dir) if not f.endswith('.tmp')]
                
                if not downloaded_files:
                    raise FileNotFoundError("İndirilen dosya bulunamadı. Lütfen indirme loglarını kontrol edin.")
                    
                final_file_name = downloaded_files[0]
                final_file_path = os.path.join(temp_dir, final_file_name)
                
                # Dosyayı okuyup Streamlit'in download_button'ına veriyoruz
                with open(final_file_path, "rb") as file:
                    file_bytes = file.read()

                # İndirme Butonunu göster
                st.download_button(
                    label=f"⬇️ {final_file_name} İndir",
                    data=file_bytes,
                    file_name=final_file_name,
                    mime="application/octet-stream",
                    type="primary"
                )
                status_box.empty()
                st.balloons()
                st.success("Dosya hazır! Yukarıdaki İndir butonuna tıklayarak dosyayı kaydedebilirsiniz.")

            except Exception as e:
                error_message = f"İşlem sırasında bir hata oluştu: {e}"
                status_box.error(f"❌ İşlem Başarısız. Detay: {e}")
                st.error("Lütfen URL'yi, zaman formatını veya seçili formatı kontrol edin. Loglar için uygulamanın ayarlarını kontrol edin.")
