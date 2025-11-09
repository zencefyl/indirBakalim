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
import shutil # Dosya işlemleri için shutil eklendi

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


# --- Ana Streamlit Uygulaması ---

st.set_page_config(
    page_title="indirBakalım - Web İndirici",
    layout="wide",
    initial_sidebar_state="auto"
)

st.title("▶️ indirBakalım - Web YouTube İndirici")
st.markdown("---")


# --- UI: URL Girişi ---

url = st.text_input("YouTube Video URL'sini Girin:", key="url_input")

if url:
    # --- UI: Ayarlar ---
    
    st.subheader("İndirme Ayarları")
    col1, col2 = st.columns(2)
    
    with col1:
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
    
    with col2:
        st.markdown("Zaman Aralığı (HH:MM:SS veya MM:SS):")
        time_col1, time_col2 = st.columns(2)
        start_time = time_col1.text_input("Başlangıç:", value="", key="start_time")
        end_time = time_col2.text_input("Bitiş:", value="", key="end_time")

    # --- UI: Butonlar ---
    st.markdown("---")
    
    # Önizleme butonu
    preview_button = st.button("Önizle", type="secondary")
    
    # Önizleme ve Bilgi Placeholder'ları
    preview_placeholder = st.empty()
    download_placeholder = st.empty()
    
    # Oturum durumu değişkenlerini başlat
    if 'download_ready' not in st.session_state:
        st.session_state['download_ready'] = False
    if 'video_info' not in st.session_state:
        st.session_state['video_info'] = None

    if preview_button:
        # Önizle düğmesine basıldığında formu yeniden başlatır
        if not url.strip():
            st.error("Lütfen bir URL girin!")
            st.stop()
        
        # Önizleme İşlemi (Fetching)
        with st.spinner("Video bilgileri ve thumbnail alınıyor..."):
            try:
                # yt-dlp'yi kütüphane olarak kullanma (İndirme yok)
                ydl_opts_preview = {'quiet': True, 'skip_download': True, 'force_generic_extractor': True, 'noprogress': True}
                with YoutubeDL(ydl_opts_preview) as ydl:
                    info = ydl.extract_info(url, download=False)

                title = info.get("title", "Başlık Bilinmiyor")
                duration = info.get("duration", 0)
                duration_str = format_duration(duration)
                uploader = info.get("uploader", "Bilinmiyor")
                thumb_url = info.get("thumbnail")
                
                # Önizleme Ekranı
                with preview_placeholder.container():
                    st.success("✅ Önizleme Başarılı")
                    st.subheader(title)
                    st.write(f"**Yükleyen:** {uploader} | **Süre:** {duration_str}")
                    
                    if thumb_url:
                        # Streamlit'te görselleri göstermek için doğrudan URL kullanılır
                        st.image(thumb_url, width=320)
                
                # Bilgileri session state'e kaydet (download butonu için)
                st.session_state['video_info'] = info
                st.session_state['download_ready'] = True
                
            except Exception as e:
                st.error(f"❌ Önizleme alınamadı. URL'yi kontrol edin. Hata: {e}")
                st.session_state['download_ready'] = False

    # --- UI: İndir Butonu ---
    
    if st.session_state['download_ready'] and st.session_state['video_info']:
        
        # İndirme İşlemi Başlatılıyor
        if st.button("⬇️ İndirme İşlemini Başlat", type="primary"):
            
            # --- VALIDASYONLAR ---
            if (start_time and not end_time) or (end_time and not start_time):
                st.error("Kesim yapmak için hem Başlangıç hem Bitiş zamanı girilmelidir.")
                st.stop()
            if not validate_time_format(start_time) or not validate_time_format(end_time):
                st.error("Zaman formatı hatalı. Lütfen HH:MM:SS veya MM:SS kullanın.")
                st.stop()

            # Streamlit Cloud'da /tmp klasörü kullanmak en güvenli yoldur.
            with tempfile.TemporaryDirectory() as temp_dir:
                
                # İşlem durumu göstergesi
                status_box = st.info("İndirme işlemi başlatılıyor...")
                
                try:
                    video_info = st.session_state['video_info']
                    
                    # Dosya adı ve uzantısı oluşturma (temizlenmiş)
                    base_filename = re.sub(r'[^\w\-_\. ]', '', video_info.get("title", "video"))
                    output_template = os.path.join(temp_dir, base_filename + '.%(ext)s')

                    # Format kodu
                    format_code = get_format_code(selected_format)
                    
                    ydl_opts_download = {
                        'format': format_code,
                        'outtmpl': output_template,
                        'quiet': True,
                        'noprogress': True, # Progress bar Streamlit'te zor olduğundan gizli tutulur.
                        'postprocessors': [],
                    }
                    
                    # Zaman Aralığı (Kesme) İşlemi
                    if start_time and end_time:
                        status_box.info(f"İndirme başlatıldı: Kesme aralığı {start_time}-{end_time}")
                        
                        ydl_opts_download['download_sections'] = [f"*{start_time}-{end_time}"]
                        # Kesim yapıldıktan sonra dosyanın yeniden uzantılanması için:
                        # Bu post-processor'ü kullanmak bazen karmaşık olabilir, ancak temel logic'i koruyoruz.
                    
                    # MP3 formatı için Post-Processor
                    if selected_format == "MP3 (Ses)":
                        status_box.info("İndirme başlatıldı: Ses formatına dönüştürülüyor.")
                        ydl_opts_download['postprocessors'].append({
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        })
                    
                    status_box.info("Video indiriliyor ve işleniyor. Bu işlem, videonun uzunluğuna göre zaman alabilir...")

                    # İndirme İşlemini Gerçekleştir
                    with YoutubeDL(ydl_opts_download) as ydl:
                        ydl.download([url])
                    
                    status_box.success("✅ İndirme ve İşlem Başarılı! Dosya hazırlanıyor...")
                    
                    # İndirilen dosyayı bul (temp_dir içinde)
                    downloaded_files = [f for f in os.listdir(temp_dir) if not f.endswith('.tmp')]
                    
                    if not downloaded_files:
                        raise FileNotFoundError("İndirilen dosya bulunamadı. yt-dlp hatası olabilir.")
                        
                    final_file_name = downloaded_files[0]
                    final_file_path = os.path.join(temp_dir, final_file_name)
                    
                    # Dosyayı okuyup Streamlit'in download_button'ına veriyoruz
                    with open(final_file_path, "rb") as file:
                        file_bytes = file.read()

                    # İndirme Butonunu göster
                    download_placeholder.download_button(
                        label=f"⬇️ {final_file_name} İndir",
                        data=file_bytes,
                        file_name=final_file_name,
                        mime="application/octet-stream", # Genel MIME tipi
                        type="primary"
                    )
                    status_box.empty() # Durum kutusunu temizle
                    st.balloons()
                    st.success("Dosya hazır! Yukarıdaki İndir butonuna tıklayarak dosyayı kaydedebilirsiniz.")

                except Exception as e:
                    error_message = f"İşlem sırasında bir hata oluştu: {e}"
                    status_box.error(f"❌ İşlem Başarısız. Detay: {e}")
                    st.error("Lütfen URL'yi, zaman formatını ve seçili formatı kontrol edin.")