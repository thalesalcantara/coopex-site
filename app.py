import os
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from io import BytesIO
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / 'static' / 'uploads'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'troque-esta-chave-no-render')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///' + str(BASE_DIR / 'coopex_site.db')
).replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 80 * 1024 * 1024

db = SQLAlchemy(app)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}
ALLOWED_CURRICULO_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'webp'}

# Natal/RN usa o mesmo horário de Fortaleza.
# O banco salva em UTC e o painel mostra convertido para o horário local.
FUSO_NATAL = ZoneInfo('America/Fortaleza')


def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def formatar_data_hora_br(data_hora):
    """Exibe data/hora no horário de Natal/RN."""
    if not data_hora:
        return ''

    if data_hora.tzinfo is None:
        data_hora = data_hora.replace(tzinfo=timezone.utc)

    data_local = data_hora.astimezone(FUSO_NATAL)
    return data_local.strftime('%d/%m/%Y %H:%M')


def excluir_arquivo_referencia(valor):
    """
    Exclui arquivo salvo no banco no formato db:ID.
    Também tenta excluir arquivo antigo salvo em static/uploads, caso exista.
    """
    if not valor:
        return

    valor = str(valor)

    if valor.startswith('db:'):
        try:
            file_id = int(valor.split(':', 1)[1])
            arquivo = FileUpload.query.get(file_id)
            if arquivo:
                db.session.delete(arquivo)
        except Exception:
            pass
        return

    try:
        caminho = UPLOAD_FOLDER / secure_filename(valor)
        if caminho.exists() and caminho.is_file():
            caminho.unlink()
    except Exception:
        pass


def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def salvar_upload(arquivo, prefixo, allowed):
    """
    Salva o arquivo no banco de dados para não sumir em deploy/reinício do Render.
    Retorna 'db:ID'. Mantém compatibilidade com arquivos antigos salvos em static/uploads.
    """
    if not arquivo or not arquivo.filename or not allowed_file(arquivo.filename, allowed):
        return None

    safe = secure_filename(arquivo.filename)
    filename = f"{prefixo}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{safe}"

    arquivo.stream.seek(0)
    dados = arquivo.read()

    if not dados:
        return None

    upload = FileUpload(
        filename=filename,
        original_filename=safe,
        mimetype=arquivo.mimetype or 'application/octet-stream',
        categoria=prefixo,
        data=dados
    )
    db.session.add(upload)
    db.session.flush()

    try:
        with open(UPLOAD_FOLDER / filename, 'wb') as f:
            f.write(dados)
    except Exception:
        pass

    return f"db:{upload.id}"


class FileUpload(db.Model):
    __tablename__ = 'file_upload'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    mimetype = db.Column(db.String(120), nullable=False, default='application/octet-stream')
    categoria = db.Column(db.String(80), nullable=True)
    data = db.Column(db.LargeBinary, nullable=False)
    criado_em = db.Column(db.DateTime, default=agora_utc)


class SiteConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(80), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False, default='')


class Partner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    link = db.Column(db.String(500), nullable=False, default='#')
    logo = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    cliques = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=agora_utc)





class CardLink(db.Model):
    __tablename__ = 'card_link'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(120), nullable=False)
    subtitulo = db.Column(db.String(180), nullable=True)
    url = db.Column(db.String(600), nullable=False, default='#')
    icone = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    cliques = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=agora_utc)


class SiteAccess(db.Model):
    __tablename__ = 'site_access'

    id = db.Column(db.Integer, primary_key=True)
    total_acessos = db.Column(db.Integer, default=0)
    atualizado_em = db.Column(db.DateTime, default=agora_utc, onupdate=agora_utc)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    empresa = db.Column(db.String(180), nullable=True)
    comentario = db.Column(db.Text, nullable=False)
    nota = db.Column(db.Integer, default=5)
    data_avaliacao = db.Column(db.String(40), nullable=True)
    link = db.Column(db.String(500), nullable=True)
    foto = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=agora_utc)


class Candidato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(180), nullable=False)
    data_nascimento = db.Column(db.Date, nullable=False)
    idade = db.Column(db.Integer, nullable=False)
    escolaridade = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), nullable=False)
    atividade_remunerada = db.Column(db.Boolean, default=False)
    curriculo = db.Column(db.String(255), nullable=True)
    criado_em = db.Column(db.DateTime, default=agora_utc)


class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)


DEFAULTS = {
    'nome_cooperativa': 'COOPEX',
    'titulo_principal': 'Entregas profissionais para empresas, restaurantes e estabelecimentos',
    'subtitulo_principal': 'Desde 2002, a COOPEX atua em Natal/RN oferecendo soluções de entrega com cooperados organizados, fardados e suporte operacional.',
    'whatsapp': '84981110706',
    'telefone': '(84) 3234-9025 / 3231-5623 / 98111-0706',
    'email': 'coopexentregas.rn@gmail.com',
    'endereco': 'Rua José Freire de Souza, 22 - Lagoa Nova, Natal/RN - CEP 59075-140',
    'instagram': 'coopex.entregas',
    'link_solicitar_entrega': 'https://escalas-2-1.onrender.com/login',
    'texto_sobre': 'A COOPEX é uma cooperativa de trabalhadores de entregas do Rio Grande do Norte, fundada em 2002, com atuação voltada para organização logística, atendimento empresarial e fortalecimento do cooperativismo.',
    'imagem_destaque': '',
    'foto_bau': '',
    'bau_dimensoes': 'Informe aqui as dimensões mínimas aceitas para o baú.',
    'bau_cor': 'Informe aqui a cor/padrão visual recomendado para o baú.',
    'documentos_entrevista': 'CNH com EAR; Documento com foto; Comprovante de residência; Documento da moto; Currículo atualizado.',
    'mapa_embed_url': 'https://www.google.com/maps?q=Rua%20Jos%C3%A9%20Freire%20de%20Souza%2022%20Lagoa%20Nova%20Natal%20RN&output=embed',
    'fardamento_info': 'Nossos cooperados atuam com apresentação organizada, fardamento da COOPEX quando disponível e identificação adequada para representar bem a cooperativa e o estabelecimento atendido.',
    'horario_atendimento': 'Atendimento administrativo de segunda a sexta, das 8h às 18h. Operação de entregas conforme demanda e escala.',
    'quadro_social': 'A COOPEX é formada por cooperados motofretistas organizados em regime cooperativo, com participação no quadro social conforme as normas internas, estatuto e regimento.',
    'anuncio_titulo': 'Anuncie aqui sua marca',
    'anuncio_texto': 'Divulgue sua empresa nos baús dos cooperados da COOPEX e fortaleça sua presença nas ruas de Natal/RN.',
    'anuncio_bau_frente': '',
    'anuncio_bau_lado': '',
    'anuncio_bau_traseira': '',
    'anuncio_dimensoes': 'Informe as dimensões disponíveis para aplicação do adesivo.',
    'anuncio_pontos_mensais': 'Informe a estimativa de pontos, bairros ou regiões por onde a marca passa mensalmente.',
    'anuncio_abrangencia': 'Informe a abrangência da propaganda, como Natal/RN, bairros atendidos, contratos e rotas de circulação.',
}


CARD_DEFAULTS = {
    'card_nome': 'COOPEX Entregas',
    'card_descricao': 'Cooperativa de Motofretistas',
    'card_bio': 'Entregas organizadas para empresas e pessoas físicas em Natal/RN.',
    'card_localizacao': 'Natal/RN',
    'card_mapa_link': 'https://www.google.com/maps?q=Rua%20Jos%C3%A9%20Freire%20de%20Souza%2022%20Lagoa%20Nova%20Natal%20RN',
    'card_cor_primaria': '#0047B8',
    'card_cor_secundaria': '#FFFFFF',
    'card_cor_texto': '#FFFFFF',
    'card_cor_botao': '#FFFFFF',
    'card_cor_texto_botao': '#0047B8',
    'card_estilo': 'ondas',
    'card_foto': '',
    'card_logo': '',
    'card_fundo_imagem': '',
    'card_video': '',
    'card_botao_whatsapp': 'Falar no WhatsApp',
    'card_link_whatsapp': '',
    'card_mostrar_video': '0',
}


def get_config(chave, default=''):
    item = SiteConfig.query.filter_by(chave=chave).first()
    return item.valor if item else default


def set_config(chave, valor):
    item = SiteConfig.query.filter_by(chave=chave).first()
    if not item:
        db.session.add(SiteConfig(chave=chave, valor=valor or ''))
    else:
        item.valor = valor or ''


def config_dict():
    return {k: get_config(k, v) for k, v in DEFAULTS.items()}


def card_config_dict():
    return {k: get_config(k, v) for k, v in CARD_DEFAULTS.items()}


def is_db_file(valor):
    return bool(valor and isinstance(valor, str) and valor.startswith('db:'))


def arquivo_url(valor):
    """Gera URL para arquivo salvo no banco ou antigo arquivo salvo em static/uploads."""
    if not valor:
        return ''

    valor = str(valor)

    if valor.startswith('db:'):
        try:
            file_id = int(valor.split(':', 1)[1])
            return url_for('arquivo_db', file_id=file_id)
        except Exception:
            return ''

    return url_for('static', filename='uploads/' + valor)


def _salvar_arquivo_local_no_banco(filename, categoria='migrado'):
    """Migra arquivo antigo de static/uploads para o banco e retorna db:ID."""
    if not filename or is_db_file(filename):
        return filename

    safe_name = secure_filename(str(filename))
    path = UPLOAD_FOLDER / safe_name

    if not path.exists() or not path.is_file():
        return filename

    try:
        dados = path.read_bytes()
        if not dados:
            return filename

        mimetype = 'application/octet-stream'
        ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
        if ext == 'png':
            mimetype = 'image/png'
        elif ext in {'jpg', 'jpeg'}:
            mimetype = 'image/jpeg'
        elif ext == 'webp':
            mimetype = 'image/webp'
        elif ext == 'gif':
            mimetype = 'image/gif'
        elif ext == 'pdf':
            mimetype = 'application/pdf'
        elif ext == 'doc':
            mimetype = 'application/msword'
        elif ext == 'docx':
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        upload = FileUpload(
            filename=safe_name,
            original_filename=safe_name,
            mimetype=mimetype,
            categoria=categoria,
            data=dados
        )
        db.session.add(upload)
        db.session.flush()
        return f"db:{upload.id}"

    except Exception:
        db.session.rollback()
        return filename


def migrar_uploads_antigos_para_banco():
    """Converte referências antigas de static/uploads para arquivos persistentes no banco."""
    try:
        chaves_upload = {
            'imagem_destaque',
            'foto_bau',
            'anuncio_bau_frente',
            'anuncio_bau_lado',
            'anuncio_bau_traseira',
        }

        for chave in chaves_upload:
            item = SiteConfig.query.filter_by(chave=chave).first()
            if item and item.valor and not is_db_file(item.valor):
                item.valor = _salvar_arquivo_local_no_banco(item.valor, chave)

        for parceiro in Partner.query.all():
            if parceiro.logo and not is_db_file(parceiro.logo):
                parceiro.logo = _salvar_arquivo_local_no_banco(parceiro.logo, 'parceiro')

        for avaliacao in Review.query.all():
            if avaliacao.foto and not is_db_file(avaliacao.foto):
                avaliacao.foto = _salvar_arquivo_local_no_banco(avaliacao.foto, 'avaliacao')

        for candidato in Candidato.query.all():
            if candidato.curriculo and not is_db_file(candidato.curriculo):
                candidato.curriculo = _salvar_arquivo_local_no_banco(candidato.curriculo, 'curriculo')

        db.session.commit()
    except Exception:
        db.session.rollback()


def calcular_idade(nascimento):
    hoje = date.today()
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def garantir_colunas_extras():
    """Garante compatibilidade com bancos já criados antes das novas colunas existirem."""
    try:
        engine_name = db.engine.url.get_backend_name()

        if engine_name.startswith('sqlite'):
            colunas_review = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(review)")).fetchall()]
            if 'foto' not in colunas_review:
                db.session.execute(db.text("ALTER TABLE review ADD COLUMN foto VARCHAR(255)"))
                db.session.commit()

            colunas_partner = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(partner)")).fetchall()]
            if 'cliques' not in colunas_partner:
                db.session.execute(db.text("ALTER TABLE partner ADD COLUMN cliques INTEGER DEFAULT 0"))
                db.session.commit()

        elif engine_name.startswith('postgresql'):
            colunas_review = {
                row[0] for row in db.session.execute(db.text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'review'"
                )).fetchall()
            }
            if 'foto' not in colunas_review:
                db.session.execute(db.text("ALTER TABLE review ADD COLUMN foto VARCHAR(255)"))
                db.session.commit()

            colunas_partner = {
                row[0] for row in db.session.execute(db.text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'partner'"
                )).fetchall()
            }
            if 'cliques' not in colunas_partner:
                db.session.execute(db.text("ALTER TABLE partner ADD COLUMN cliques INTEGER DEFAULT 0"))
                db.session.commit()

    except Exception:
        db.session.rollback()


def init_db():
    with app.app_context():
        db.create_all()
        garantir_colunas_extras()

        for chave, valor in DEFAULTS.items():
            item = SiteConfig.query.filter_by(chave=chave).first()
            if not item:
                db.session.add(SiteConfig(chave=chave, valor=valor))
            elif chave in DEFAULTS and item.valor is None:
                item.valor = valor

        for chave, valor in CARD_DEFAULTS.items():
            item = SiteConfig.query.filter_by(chave=chave).first()
            if not item:
                db.session.add(SiteConfig(chave=chave, valor=valor))
            elif item.valor is None:
                item.valor = valor

        admin_user = os.getenv('SITE_ADMIN_USER', 'coopex')
        admin_pass = os.getenv('SITE_ADMIN_PASS', 'coopex05289')
        admin = AdminUser.query.filter_by(usuario=admin_user).first()
        if not admin:
            db.session.add(AdminUser(usuario=admin_user, senha_hash=generate_password_hash(admin_pass)))
        elif os.getenv('FORCAR_SENHA_ADMIN_SITE', '1') == '1':
            admin.senha_hash = generate_password_hash(admin_pass)

        if Partner.query.count() == 0:
            db.session.add_all([
                Partner(nome='Parceiro COOPEX', link='#', logo=None, ativo=True, ordem=1),
                Partner(nome='Solicite sua entrega', link=get_config('link_solicitar_entrega', DEFAULTS['link_solicitar_entrega']), logo=None, ativo=True, ordem=2),
            ])

        if Review.query.count() == 0:
            db.session.add_all([
                Review(nome='Cliente COOPEX', empresa='Restaurante parceiro', comentario='Atendimento organizado, entregadores bem apresentados e suporte rápido quando precisamos.', nota=5, data_avaliacao='há 2 semanas', link='#', ativo=True, ordem=1),
                Review(nome='Empresa parceira', empresa='Delivery local', comentario='A operação ficou mais segura com a COOPEX. Sempre que precisamos, conseguimos falar com a equipe.', nota=5, data_avaliacao='há 1 mês', link='#', ativo=True, ordem=2),
                Review(nome='Estabelecimento cliente', empresa='Farmácia', comentario='Equipe responsável, boa comunicação e entregadores fardados. Recomendo para operação fixa.', nota=5, data_avaliacao='há 2 meses', link='#', ativo=True, ordem=3),
            ])


        if CardLink.query.count() == 0:
            db.session.add_all([
                CardLink(titulo='Solicitar entrega', subtitulo='Atendimento COOPEX', url=get_config('link_solicitar_entrega', DEFAULTS['link_solicitar_entrega']), ativo=True, ordem=1),
                CardLink(titulo='Instagram', subtitulo='Acompanhe a COOPEX', url='https://instagram.com/coopex.entregas', ativo=True, ordem=2),
                CardLink(titulo='Contato', subtitulo='Fale conosco', url='https://wa.me/5584981110706', ativo=True, ordem=3),
            ])

        db.session.commit()


@app.context_processor
def inject_global():
    return {
        'cfg': config_dict(),
        'card_cfg': card_config_dict(),
        'arquivo_url': arquivo_url,
        'formatar_data_hora_br': formatar_data_hora_br
    }


def login_required():
    return session.get('site_admin_logado') is True


@app.route('/arquivo/<int:file_id>')
def arquivo_db(file_id):
    arquivo = FileUpload.query.get_or_404(file_id)
    return send_file(
        BytesIO(arquivo.data),
        mimetype=arquivo.mimetype or 'application/octet-stream',
        download_name=arquivo.original_filename or arquivo.filename
    )


@app.route('/')
def index():
    if not session.get('site_visitou'):
        contador = SiteAccess.query.first()
        if not contador:
            contador = SiteAccess(total_acessos=0)
            db.session.add(contador)

        contador.total_acessos = (contador.total_acessos or 0) + 1
        session['site_visitou'] = True
        db.session.commit()

    parceiros = Partner.query.filter_by(ativo=True).order_by(Partner.ordem.asc(), Partner.nome.asc()).all()
    avaliacoes = Review.query.filter_by(ativo=True).order_by(Review.ordem.asc(), Review.criado_em.desc()).all()
    return render_template('index.html', parceiros=parceiros, avaliacoes=avaliacoes)


@app.route('/trabalhe-conosco/enviar', methods=['POST'])
def enviar_curriculo():
    nome = request.form.get('nome_completo', '').strip()
    data_nascimento_str = request.form.get('data_nascimento', '').strip()
    escolaridade = request.form.get('escolaridade', '').strip()
    email = request.form.get('email', '').strip()
    atividade = request.form.get('atividade_remunerada') == 'on'
    arquivo = request.files.get('curriculo')

    if not nome or not data_nascimento_str or not escolaridade or not email:
        flash('Preencha todos os campos obrigatórios para enviar o currículo.', 'erro')
        return redirect(url_for('index') + '#trabalhe')

    try:
        nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Data de nascimento inválida.', 'erro')
        return redirect(url_for('index') + '#trabalhe')

    idade = calcular_idade(nascimento)
    if idade < 21:
        flash('O cadastro só pode ser enviado por candidatos com 21 anos ou mais.', 'erro')
        return redirect(url_for('index') + '#trabalhe')

    if not atividade:
        flash('Para enviar, marque que possui atividade remunerada na CNH.', 'erro')
        return redirect(url_for('index') + '#trabalhe')

    curriculo = salvar_upload(arquivo, 'curriculo', ALLOWED_CURRICULO_EXTENSIONS)
    if not curriculo:
        flash('Envie o currículo em PDF, DOC, DOCX ou imagem.', 'erro')
        return redirect(url_for('index') + '#trabalhe')

    candidato = Candidato(
        nome_completo=nome,
        data_nascimento=nascimento,
        idade=idade,
        escolaridade=escolaridade,
        email=email,
        atividade_remunerada=True,
        curriculo=curriculo
    )
    db.session.add(candidato)
    db.session.commit()
    flash('Currículo enviado com sucesso. A COOPEX analisará as informações.', 'ok')
    return redirect(url_for('index') + '#trabalhe')


@app.route('/politica-de-privacidade')
def politica_privacidade():
    return render_template('politica_privacidade.html')


@app.route('/admin-coopex', methods=['GET', 'POST'])
@app.route('/admin-site', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '')
        admin = AdminUser.query.filter_by(usuario=usuario).first()
        if admin and check_password_hash(admin.senha_hash, senha):
            session['site_admin_logado'] = True
            session['site_admin_usuario'] = usuario
            return redirect(url_for('admin_dashboard'))
        flash('Usuário ou senha inválidos.', 'erro')
    return render_template('admin_login.html')


@app.route('/admin-coopex/sair')
@app.route('/admin-site/sair')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/admin-coopex/painel')
@app.route('/admin-site/painel')
def admin_dashboard():
    if not login_required():
        return redirect(url_for('admin_login'))
    parceiros = Partner.query.order_by(Partner.ordem.asc(), Partner.nome.asc()).all()
    avaliacoes = Review.query.order_by(Review.ordem.asc(), Review.criado_em.desc()).all()
    candidatos = Candidato.query.order_by(Candidato.criado_em.desc()).limit(100).all()

    contador_site = SiteAccess.query.first()
    total_acessos_site = contador_site.total_acessos if contador_site else 0

    return render_template(
        'admin_dashboard.html',
        parceiros=parceiros,
        avaliacoes=avaliacoes,
        candidatos=candidatos,
        configs=config_dict(),
        total_acessos_site=total_acessos_site
    )



@app.route('/admin-coopex/candidatos/<int:candidato_id>/excluir', methods=['POST'])
@app.route('/admin-site/candidatos/<int:candidato_id>/excluir', methods=['POST'])
def candidato_excluir(candidato_id):
    if not login_required():
        return redirect(url_for('admin_login'))

    candidato = Candidato.query.get_or_404(candidato_id)

    try:
        excluir_arquivo_referencia(candidato.curriculo)
        db.session.delete(candidato)
        db.session.commit()
        flash('Currículo excluído com sucesso.', 'ok')
    except Exception:
        db.session.rollback()
        flash('Erro ao excluir o currículo. Tente novamente.', 'erro')

    return redirect(url_for('admin_dashboard'))


@app.route('/instagram')
@app.route('/card-instagram')
def card_instagram():
    links = CardLink.query.filter_by(ativo=True).order_by(CardLink.ordem.asc(), CardLink.criado_em.asc()).all()
    return render_template('instagram_card.html', card=card_config_dict(), links=links)


@app.route('/card-link/<int:link_id>/ir')
def card_link_ir(link_id):
    link = CardLink.query.get_or_404(link_id)
    link.cliques = (link.cliques or 0) + 1
    db.session.commit()
    if link.url and link.url != '#':
        return redirect(link.url)
    return redirect(url_for('card_instagram'))


@app.route('/admin-coopex/card')
@app.route('/admin-site/card')
def admin_card():
    if not login_required():
        return redirect(url_for('admin_login'))
    links = CardLink.query.order_by(CardLink.ordem.asc(), CardLink.criado_em.asc()).all()
    return render_template('admin_card.html', card=card_config_dict(), links=links)


@app.route('/admin-coopex/card/salvar', methods=['POST'])
@app.route('/admin-site/card/salvar', methods=['POST'])
def salvar_card_configuracoes():
    if not login_required():
        return redirect(url_for('admin_login'))

    campos_texto = [
        'card_nome', 'card_descricao', 'card_bio', 'card_localizacao', 'card_mapa_link', 'card_cor_primaria', 'card_cor_secundaria',
        'card_cor_texto', 'card_cor_botao', 'card_cor_texto_botao', 'card_estilo',
        'card_botao_whatsapp', 'card_link_whatsapp'
    ]
    for chave in campos_texto:
        set_config(chave, request.form.get(chave, CARD_DEFAULTS.get(chave, '')))

    set_config('card_mostrar_video', '1' if request.form.get('card_mostrar_video') == 'on' else '0')

    foto = salvar_upload(request.files.get('card_foto'), 'card_foto', ALLOWED_IMAGE_EXTENSIONS)
    if foto:
        set_config('card_foto', foto)

    logo = salvar_upload(request.files.get('card_logo'), 'card_logo', ALLOWED_IMAGE_EXTENSIONS)
    if logo:
        set_config('card_logo', logo)

    fundo = salvar_upload(request.files.get('card_fundo_imagem'), 'card_fundo', ALLOWED_IMAGE_EXTENSIONS)
    if fundo:
        set_config('card_fundo_imagem', fundo)

    video = salvar_upload(request.files.get('card_video'), 'card_video', ALLOWED_VIDEO_EXTENSIONS)
    if video:
        set_config('card_video', video)

    db.session.commit()
    flash('Card do Instagram atualizado com sucesso.', 'ok')
    return redirect(url_for('admin_card'))


@app.route('/admin-coopex/card/link/novo', methods=['POST'])
@app.route('/admin-site/card/link/novo', methods=['POST'])
def card_link_novo():
    if not login_required():
        return redirect(url_for('admin_login'))

    titulo = request.form.get('titulo', '').strip()
    subtitulo = request.form.get('subtitulo', '').strip()
    url = request.form.get('url', '').strip() or '#'
    ativo = request.form.get('ativo') == 'on'
    ordem = int(request.form.get('ordem') or 0)

    if not titulo:
        flash('Informe o título do botão/link.', 'erro')
        return redirect(url_for('admin_card'))

    icone = salvar_upload(request.files.get('icone'), 'card_icone', ALLOWED_IMAGE_EXTENSIONS)
    db.session.add(CardLink(titulo=titulo, subtitulo=subtitulo, url=url, icone=icone, ativo=ativo, ordem=ordem))
    db.session.commit()
    flash('Link cadastrado no card.', 'ok')
    return redirect(url_for('admin_card'))


@app.route('/admin-coopex/card/link/<int:link_id>/editar', methods=['POST'])
@app.route('/admin-site/card/link/<int:link_id>/editar', methods=['POST'])
def card_link_editar(link_id):
    if not login_required():
        return redirect(url_for('admin_login'))

    link = CardLink.query.get_or_404(link_id)
    link.titulo = request.form.get('titulo', link.titulo).strip()
    link.subtitulo = request.form.get('subtitulo', link.subtitulo or '').strip()
    link.url = request.form.get('url', link.url).strip() or '#'
    link.ordem = int(request.form.get('ordem') or 0)
    link.ativo = request.form.get('ativo') == 'on'

    icone = salvar_upload(request.files.get('icone'), 'card_icone', ALLOWED_IMAGE_EXTENSIONS)
    if icone:
        link.icone = icone

    db.session.commit()
    flash('Link atualizado.', 'ok')
    return redirect(url_for('admin_card'))


@app.route('/admin-coopex/card/link/<int:link_id>/excluir', methods=['POST'])
@app.route('/admin-site/card/link/<int:link_id>/excluir', methods=['POST'])
def card_link_excluir(link_id):
    if not login_required():
        return redirect(url_for('admin_login'))

    link = CardLink.query.get_or_404(link_id)
    db.session.delete(link)
    db.session.commit()
    flash('Link excluído do card.', 'ok')
    return redirect(url_for('admin_card'))


@app.route('/admin-coopex/configuracoes', methods=['POST'])
@app.route('/admin-site/configuracoes', methods=['POST'])
def salvar_configuracoes():
    if not login_required():
        return redirect(url_for('admin_login'))

    upload_config_keys = {
        'imagem_destaque',
        'foto_bau',
        'anuncio_bau_frente',
        'anuncio_bau_lado',
        'anuncio_bau_traseira',
    }

    for chave in DEFAULTS.keys():
        if chave not in upload_config_keys:
            set_config(chave, request.form.get(chave, DEFAULTS[chave]))

    imagem_destaque = salvar_upload(request.files.get('imagem_destaque'), 'destaque', ALLOWED_IMAGE_EXTENSIONS)
    if imagem_destaque:
        set_config('imagem_destaque', imagem_destaque)

    foto_bau = salvar_upload(request.files.get('foto_bau'), 'bau', ALLOWED_IMAGE_EXTENSIONS)
    if foto_bau:
        set_config('foto_bau', foto_bau)

    anuncio_bau_frente = salvar_upload(request.files.get('anuncio_bau_frente'), 'anuncio_frente', ALLOWED_IMAGE_EXTENSIONS)
    if anuncio_bau_frente:
        set_config('anuncio_bau_frente', anuncio_bau_frente)

    anuncio_bau_lado = salvar_upload(request.files.get('anuncio_bau_lado'), 'anuncio_lado', ALLOWED_IMAGE_EXTENSIONS)
    if anuncio_bau_lado:
        set_config('anuncio_bau_lado', anuncio_bau_lado)

    anuncio_bau_traseira = salvar_upload(request.files.get('anuncio_bau_traseira'), 'anuncio_traseira', ALLOWED_IMAGE_EXTENSIONS)
    if anuncio_bau_traseira:
        set_config('anuncio_bau_traseira', anuncio_bau_traseira)

    db.session.commit()
    flash('Informações do site atualizadas com sucesso.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-coopex/parceiros/novo', methods=['POST'])
@app.route('/admin-site/parceiros/novo', methods=['POST'])
def parceiro_novo():
    if not login_required():
        return redirect(url_for('admin_login'))

    nome = request.form.get('nome', '').strip()
    link = request.form.get('link', '').strip() or '#'
    ordem = int(request.form.get('ordem') or 0)
    ativo = request.form.get('ativo') == 'on'

    if not nome:
        flash('Informe o nome do parceiro.', 'erro')
        return redirect(url_for('admin_dashboard'))

    filename = salvar_upload(request.files.get('logo'), 'parceiro', ALLOWED_IMAGE_EXTENSIONS)
    db.session.add(Partner(nome=nome, link=link, logo=filename, ativo=ativo, ordem=ordem))
    db.session.commit()
    flash('Parceiro cadastrado com sucesso.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-coopex/parceiros/<int:partner_id>/editar', methods=['POST'])
@app.route('/admin-site/parceiros/<int:partner_id>/editar', methods=['POST'])
def parceiro_editar(partner_id):
    if not login_required():
        return redirect(url_for('admin_login'))

    parceiro = Partner.query.get_or_404(partner_id)
    parceiro.nome = request.form.get('nome', parceiro.nome).strip()
    parceiro.link = request.form.get('link', parceiro.link).strip() or '#'
    parceiro.ordem = int(request.form.get('ordem') or 0)
    parceiro.ativo = request.form.get('ativo') == 'on'

    filename = salvar_upload(request.files.get('logo'), 'parceiro', ALLOWED_IMAGE_EXTENSIONS)
    if filename:
        parceiro.logo = filename

    db.session.commit()
    flash('Parceiro atualizado.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/parceiro/<int:partner_id>/ir')
def parceiro_ir(partner_id):
    parceiro = Partner.query.get_or_404(partner_id)

    parceiro.cliques = (parceiro.cliques or 0) + 1
    db.session.commit()

    if parceiro.link and parceiro.link != '#':
        return redirect(parceiro.link)

    return redirect(url_for('index') + '#parceiros')


@app.route('/admin-coopex/parceiros/<int:partner_id>/excluir', methods=['POST'])
@app.route('/admin-site/parceiros/<int:partner_id>/excluir', methods=['POST'])
def parceiro_excluir(partner_id):
    if not login_required():
        return redirect(url_for('admin_login'))

    parceiro = Partner.query.get_or_404(partner_id)
    db.session.delete(parceiro)
    db.session.commit()
    flash('Parceiro excluído.', 'ok')
    return redirect(url_for('admin_dashboard'))



@app.route('/admin-coopex/avaliacoes/nova', methods=['POST'])
@app.route('/admin-site/avaliacoes/nova', methods=['POST'])
def avaliacao_nova():
    if not login_required():
        return redirect(url_for('admin_login'))

    nome = request.form.get('nome', '').strip()
    empresa = request.form.get('empresa', '').strip()
    comentario = request.form.get('comentario', '').strip()
    data_avaliacao = request.form.get('data_avaliacao', '').strip()
    link = request.form.get('link', '').strip() or '#'
    ordem = int(request.form.get('ordem') or 0)
    ativo = request.form.get('ativo') == 'on'
    foto = salvar_upload(request.files.get('foto'), 'avaliacao', ALLOWED_IMAGE_EXTENSIONS)

    try:
        nota = int(request.form.get('nota') or 5)
    except ValueError:
        nota = 5
    nota = max(1, min(5, nota))

    if not nome or not comentario:
        flash('Informe o nome e o comentário da avaliação.', 'erro')
        return redirect(url_for('admin_dashboard'))

    db.session.add(Review(
        nome=nome,
        empresa=empresa,
        comentario=comentario,
        nota=nota,
        data_avaliacao=data_avaliacao,
        link=link,
        foto=foto,
        ativo=ativo,
        ordem=ordem
    ))
    db.session.commit()
    flash('Avaliação cadastrada com sucesso.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-coopex/avaliacoes/<int:review_id>/editar', methods=['POST'])
@app.route('/admin-site/avaliacoes/<int:review_id>/editar', methods=['POST'])
def avaliacao_editar(review_id):
    if not login_required():
        return redirect(url_for('admin_login'))

    avaliacao = Review.query.get_or_404(review_id)
    avaliacao.nome = request.form.get('nome', avaliacao.nome).strip()
    avaliacao.empresa = request.form.get('empresa', avaliacao.empresa or '').strip()
    avaliacao.comentario = request.form.get('comentario', avaliacao.comentario).strip()
    avaliacao.data_avaliacao = request.form.get('data_avaliacao', avaliacao.data_avaliacao or '').strip()
    avaliacao.link = request.form.get('link', avaliacao.link or '#').strip() or '#'
    foto = salvar_upload(request.files.get('foto'), 'avaliacao', ALLOWED_IMAGE_EXTENSIONS)
    if foto:
        avaliacao.foto = foto
    avaliacao.ordem = int(request.form.get('ordem') or 0)
    avaliacao.ativo = request.form.get('ativo') == 'on'

    try:
        nota = int(request.form.get('nota') or avaliacao.nota or 5)
    except ValueError:
        nota = 5
    avaliacao.nota = max(1, min(5, nota))

    db.session.commit()
    flash('Avaliação atualizada.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-coopex/avaliacoes/<int:review_id>/excluir', methods=['POST'])
@app.route('/admin-site/avaliacoes/<int:review_id>/excluir', methods=['POST'])
def avaliacao_excluir(review_id):
    if not login_required():
        return redirect(url_for('admin_login'))

    avaliacao = Review.query.get_or_404(review_id)
    db.session.delete(avaliacao)
    db.session.commit()
    flash('Avaliação excluída.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/api/site/parceiros')
def api_parceiros():
    parceiros = Partner.query.filter_by(ativo=True).order_by(Partner.ordem.asc(), Partner.nome.asc()).all()
    return jsonify({
        'ok': True,
        'parceiros': [
            {
                'nome': p.nome,
                'link': p.link,
                'logo': arquivo_url(p.logo) if p.logo else None,
            }
            for p in parceiros
        ]
    })


init_db()

if __name__ == '__main__':
    app.run(debug=True)
