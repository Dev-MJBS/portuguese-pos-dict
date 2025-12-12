import fitz  # Isso é o PyMuPDF
from piper.voice import PiperVoice
import wave
from pydub import AudioSegment
from pydub.playback import play  # Opcional: pra tocar direto

# Caminho do seu PDF
pdf_path = "seu_livro.pdf"  # Mude pro nome do seu arquivo

# Extrai todo o texto do PDF
doc = fitz.open(pdf_path)
texto_completo = ""
for pagina in doc:
    texto_completo += pagina.get_text() + "\n"

print(f"Texto extraído: {len(texto_completo)} caracteres")

# Carrega uma voz PT-BR do Piper (baixa automático na primeira vez)
# Opções boas: "pt_BR-faber-medium.onnx", "pt_BR-jeff-medium.onnx", "pt_BR-cadu-medium.onnx"
model = "pt_BR-faber-medium.onnx"  # Mude pra testar outras
voice = PiperVoice.load(model)

# Gera áudio WAV
with wave.open("livro.wav", "wb") as wav_file:
    voice.synthesize_wav(texto_completo, wav_file)

# Tenta converter pra MP3 (mais prático pra ouvir)
try:
    audio = AudioSegment.from_wav("livro.wav")
    audio.export("livro.mp3", format="mp3")
    print("Audiobook gerado: livro.mp3")
except Exception as e:
    print(f"Erro ao converter para MP3: {e}")
    print("Audiobook salvo como WAV: livro.wav")

# Opcional: toca direto (pode ser longo!)
# play(audio)