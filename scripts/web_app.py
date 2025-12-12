from flask import Flask, request, render_template, send_file, redirect
import os
from werkzeug.utils import secure_filename
import fitz
from ebooklib import epub
from bs4 import BeautifulSoup
from pypandoc import convert_file
from piper.voice import PiperVoice
import wave
from pydub import AudioSegment
import re
from openai import OpenAI

app = Flask(__name__)

# Usa o diretório do script como base
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'epub', 'mobi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def limpar_texto(texto):
    """Remove rodapés, cabeçalhos e formatação desnecessária"""
    # Remove números de página isolados
    texto = re.sub(r'^\s*\d+\s*$', '', texto, flags=re.MULTILINE)
    # Remove linhas muito curtas que parecem rodapés
    linhas = texto.split('\n')
    linhas_filtradas = [l for l in linhas if len(l.strip()) > 10 or l.strip() == '']
    texto = '\n'.join(linhas_filtradas)
    # Remove espaços múltiplos
    texto = re.sub(r'\n\n\n+', '\n\n', texto)
    return texto.strip()

def filtrar_conteudo_com_ia(texto, api_key=None):
    """Usa IA para remover conteúdo desnecessário como rodapés, índices e publicidades"""
    if not api_key:
        # Se não houver chave, apenas faz limpeza básica
        return limpar_texto(texto)
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Você é um assistente que remove conteúdo desnecessário de textos. Remove rodapés, cabeçalhos, números de página, índices, publicidades, notas de rodapé e informações de copyright. Mantém apenas o conteúdo principal do livro. Retorna apenas o texto limpo, sem explicações."
                },
                {
                    "role": "user",
                    "content": f"Limpe este texto, removendo rodapés e conteúdo desnecessário:\n\n{texto[:2000]}"
                }
            ],
            temperature=0.3,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Erro ao usar IA: {e}")
        return limpar_texto(texto)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            ext = filename.rsplit('.', 1)[1].lower()
            if ext == 'mobi':
                epub_path = filepath.replace('.mobi', '.epub')
                convert_file(filepath, 'epub', outputfile=epub_path)
                filepath = epub_path
                ext = 'epub'
            if ext == 'pdf':
                doc = fitz.open(filepath)
                pages = [f'Página {i+1}' for i in range(len(doc))]
                doc.close()
                return render_template('select_pages.html', pages=pages, filepath=filepath, type='pdf')
            elif ext == 'epub':
                book = epub.read_epub(filepath)
                chapters = []
                for item in book.get_items():
                    if item.get_type() == epub.EpubHtml:
                        chapters.append(item.get_name())
                return render_template('select_pages.html', pages=chapters, filepath=filepath, type='epub')
    return render_template('upload.html')

@app.route('/generate', methods=['POST'])
def generate_audio():
    filepath = request.form['filepath']
    selected = request.form.getlist('pages')
    type_ = request.form['type']
    usar_ia = request.form.get('usar_ia', 'false').lower() == 'true'
    api_key = request.form.get('api_key', '')
    
    texto_completo = ""
    if type_ == 'pdf':
        doc = fitz.open(filepath)
        for sel in selected:
            page_num = int(sel.split()[1]) - 1
            texto_completo += doc[page_num].get_text() + "\n"
        doc.close()
    elif type_ == 'epub':
        book = epub.read_epub(filepath)
        for item in book.get_items():
            if item.get_type() == epub.EpubHtml and item.get_name() in selected:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text = soup.get_text()
                texto_completo += text + "\n"
    
    # Filtra conteúdo desnecessário
    if usar_ia and api_key:
        texto_completo = filtrar_conteudo_com_ia(texto_completo, api_key)
    else:
        texto_completo = limpar_texto(texto_completo)
    # Synthesize
    model = "pt_BR-faber-medium.onnx"
    voice = PiperVoice.load(model)
    
    # Sintetiza áudio e escreve em arquivo WAV
    wav_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp.wav")
    with wave.open(wav_path, "wb") as wav_file:
        voice.synthesize_wav(texto_completo, wav_file)
    
    # Tenta converter para MP3, se falhar retorna WAV
    try:
        audio = AudioSegment.from_wav(wav_path)
        mp3_path = os.path.join(app.config['UPLOAD_FOLDER'], "audiobook.mp3")
        audio.export(mp3_path, format="mp3")
        return send_file(mp3_path, as_attachment=True, download_name="audiobook.mp3", mimetype="audio/mpeg")
    except Exception as e:
        print(f"Erro ao converter para MP3: {e}")
        # Retorna arquivo WAV como fallback
        return send_file(wav_path, as_attachment=True, download_name="audiobook.wav", mimetype="audio/wav")

if __name__ == '__main__':
    app.run(debug=True)