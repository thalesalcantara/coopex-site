from datetime import datetime, date, timezone
from io import BytesIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from flask import (
    Flask, Response, abort, flash, jsonify, redirect, render_template_string,
    request, send_file, session, url_for
)
from pyodide.ffi import run_sync
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from workers import wsgi

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = 'troque-esta-chave-no-cloudflare'
app.config['MAX_CONTENT_LENGTH'] = 80 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}
ALLOWED_CURRICULO_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'webp'}
CHUNK_SIZE = 1_500_000
FUSO_NATAL = ZoneInfo('America/Fortaleza')

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


def agora_utc_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def _env():
    return request.environ['workers.env']


def _to_py(value):
    if value is None:
        return None
    try:
        return value.to_py()
    except Exception:
        return value


def _db_run(sql, *params):
    stmt = _env().DB.prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    return run_sync(stmt.run())


def _rows(sql, *params):
    result = _db_run(sql, *params)
    data = _to_py(result.results)
    if data is None:
        return []
    return list(data)


def _one(sql, *params):
    rows = _rows(sql, *params)
    return rows[0] if rows else None


def _insert(sql, *params):
    result = _db_run(sql, *params)
    meta = _to_py(result.meta) or {}
    return int(meta.get('last_row_id') or 0)


def _obj(row):
    if row is None:
        return None
    if not isinstance(row, dict):
        row = _to_py(row)
    if row is None:
        return None
    return SimpleNamespace(**row)


def _objs(rows):
    return [_obj(r) for r in rows]


def _asset_response(asset_path):
    asset = run_sync(_env().ASSETS.fetch(f'https://assets.local/{asset_path.lstrip("/")}'))
    body = run_sync(asset.bytes())
    return Response(body, status=asset.status, headers=_to_py(asset.headers) or {})


def render_cf(template_name, **context):
    asset = run_sync(_env().ASSETS.fetch(f'https://assets.local/templates/{template_name}'))
    if asset.status != 200:
        abort(500, description=f'Template não encontrado: {template_name}')
    html = run_sync(asset.text())
    return render_template_string(html, **context)


def allowed_file(filename, allowed):
    return bool(filename and '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed)


def salvar_upload(arquivo, prefixo, allowed):
    if not arquivo or not arquivo.filename or not allowed_file(arquivo.filename, allowed):
        return None

    safe = secure_filename(arquivo.filename)
    filename = f'{prefixo}_{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")}_{safe}'
    arquivo.stream.seek(0)
    dados = arquivo.read()
    if not dados:
        return None

    file_id = _insert(
        '''INSERT INTO file_upload
           (filename, original_filename, mimetype, categoria, tamanho, criado_em)
           VALUES (?, ?, ?, ?, ?, ?)''',
        filename, safe, arquivo.mimetype or 'application/octet-stream', prefixo,
        len(dados), agora_utc_iso()
    )

    for parte, inicio in enumerate(range(0, len(dados), CHUNK_SIZE)):
        pedaco = dados[inicio:inicio + CHUNK_SIZE]
        _db_run(
            'INSERT INTO file_chunk (file_id, parte, data) VALUES (?, ?, ?)',
            file_id, parte, pedaco
        )

    return f'db:{file_id}'


def excluir_arquivo_referencia(valor):
    if not valor or not str(valor).startswith('db:'):
        return
    try:
        file_id = int(str(valor).split(':', 1)[1])
    except Exception:
        return
    _db_run('DELETE FROM file_chunk WHERE file_id = ?', file_id)
    _db_run('DELETE FROM file_upload WHERE id = ?', file_id)


def get_config(chave, default=''):
    row = _one('SELECT valor FROM site_config WHERE chave = ? LIMIT 1', chave)
    return row['valor'] if row else default


def set_config(chave, valor):
    _db_run(
        '''INSERT INTO site_config (chave, valor) VALUES (?, ?)
           ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor''',
        chave, valor or ''
    )


def config_dict():
    rows = _rows('SELECT chave, valor FROM site_config')
    valores = {r['chave']: r['valor'] for r in rows}
    return {k: valores.get(k, v) for k, v in DEFAULTS.items()}


def card_config_dict():
    rows = _rows('SELECT chave, valor FROM site_config')
    valores = {r['chave']: r['valor'] for r in rows}
    return {k: valores.get(k, v) for k, v in CARD_DEFAULTS.items()}


def arquivo_url(valor):
    if not valor:
        return ''
    valor = str(valor)
    if valor.startswith('db:'):
        try:
            return url_for('arquivo_db', file_id=int(valor.split(':', 1)[1]))
        except Exception:
            return ''
    return url_for('static_asset', path='uploads/' + valor)


def calcular_idade(nascimento):
    hoje = date.today()
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def formatar_data_hora_br(data_hora):
    if not data_hora:
        return ''
    if isinstance(data_hora, str):
        try:
            data_hora = datetime.fromisoformat(data_hora.replace('Z', '+00:00'))
        except Exception:
            return data_hora
    if data_hora.tzinfo is None:
        data_hora = data_hora.replace(tzinfo=timezone.utc)
    return data_hora.astimezone(FUSO_NATAL).strftime('%d/%m/%Y %H:%M')


def login_required():
    return session.get('site_admin_logado') is True


def ensure_seed():
    for chave, valor in {**DEFAULTS, **CARD_DEFAULTS}.items():
        _db_run('INSERT OR IGNORE INTO site_config (chave, valor) VALUES (?, ?)', chave, valor)

    admin = _one('SELECT id FROM admin_user LIMIT 1')
    if not admin:
        usuario = getattr(_env(), 'SITE_ADMIN_USER', 'coopex')
        senha = getattr(_env(), 'SITE_ADMIN_PASS', 'coopex05289')
        _db_run(
            'INSERT INTO admin_user (usuario, senha_hash) VALUES (?, ?)',
            usuario, generate_password_hash(senha)
        )

    if not _one('SELECT id FROM site_access LIMIT 1'):
        _db_run('INSERT INTO site_access (total_acessos, atualizado_em) VALUES (0, ?)', agora_utc_iso())

    if not _one('SELECT id FROM partner LIMIT 1'):
        _db_run('INSERT INTO partner (nome, link, ativo, ordem, cliques, criado_em) VALUES (?, ?, 1, 1, 0, ?)', 'Parceiro COOPEX', '#', agora_utc_iso())
        _db_run('INSERT INTO partner (nome, link, ativo, ordem, cliques, criado_em) VALUES (?, ?, 1, 2, 0, ?)', 'Solicite sua entrega', get_config('link_solicitar_entrega', DEFAULTS['link_solicitar_entrega']), agora_utc_iso())

    if not _one('SELECT id FROM review LIMIT 1'):
        reviews = [
            ('Cliente COOPEX', 'Restaurante parceiro', 'Atendimento organizado, entregadores bem apresentados e suporte rápido quando precisamos.', 'há 2 semanas', 1),
            ('Empresa parceira', 'Delivery local', 'A operação ficou mais segura com a COOPEX. Sempre que precisamos, conseguimos falar com a equipe.', 'há 1 mês', 2),
            ('Estabelecimento cliente', 'Farmácia', 'Equipe responsável, boa comunicação e entregadores fardados. Recomendo para operação fixa.', 'há 2 meses', 3),
        ]
        for nome, empresa, comentario, data_avaliacao, ordem in reviews:
            _db_run('''INSERT INTO review
                       (nome, empresa, comentario, nota, data_avaliacao, link, ativo, ordem, criado_em)
                       VALUES (?, ?, ?, 5, ?, '#', 1, ?, ?)''',
                    nome, empresa, comentario, data_avaliacao, ordem, agora_utc_iso())

    if not _one('SELECT id FROM card_link LIMIT 1'):
        links = [
            ('Solicitar entrega', 'Atendimento COOPEX', get_config('link_solicitar_entrega', DEFAULTS['link_solicitar_entrega']), 1),
            ('Instagram', 'Acompanhe a COOPEX', 'https://instagram.com/coopex.entregas', 2),
            ('Contato', 'Fale conosco', 'https://wa.me/5584981110706', 3),
        ]
        for titulo, subtitulo, url, ordem in links:
            _db_run('''INSERT INTO card_link
                       (titulo, subtitulo, url, ativo, ordem, cliques, criado_em)
                       VALUES (?, ?, ?, 1, ?, 0, ?)''', titulo, subtitulo, url, ordem, agora_utc_iso())


@app.before_request
def _bootstrap():
    if request.path.startswith('/static/'):
        return None
    ensure_seed()
    return None


@app.context_processor
def inject_global():
    return {
        'cfg': config_dict(),
        'card_cfg': card_config_dict(),
        'arquivo_url': arquivo_url,
        'formatar_data_hora_br': formatar_data_hora_br,
    }


@app.route('/static/<path:path>')
def static_asset(path):
    return _asset_response('static/' + path)


@app.route('/arquivo/<int:file_id>')
def arquivo_db(file_id):
    arquivo = _one('SELECT * FROM file_upload WHERE id = ? LIMIT 1', file_id)
    if not arquivo:
        abort(404)

    chunks = _rows('SELECT data FROM file_chunk WHERE file_id = ? ORDER BY parte ASC', file_id)
    partes = []
    for row in chunks:
        data = row.get('data')
        data = _to_py(data)
        if isinstance(data, list):
            data = bytes(data)
        elif isinstance(data, bytearray):
            data = bytes(data)
        partes.append(data or b'')

    return send_file(
        BytesIO(b''.join(partes)),
        mimetype=arquivo.get('mimetype') or 'application/octet-stream',
        download_name=arquivo.get('original_filename') or arquivo.get('filename')
    )


@app.route('/')
def index():
    if not session.get('site_visitou'):
        _db_run('UPDATE site_access SET total_acessos = COALESCE(total_acessos, 0) + 1, atualizado_em = ? WHERE id = (SELECT id FROM site_access LIMIT 1)', agora_utc_iso())
        session['site_visitou'] = True

    parceiros = _objs(_rows('SELECT * FROM partner WHERE ativo = 1 ORDER BY ordem ASC, nome ASC'))
    avaliacoes = _objs(_rows('SELECT * FROM review WHERE ativo = 1 ORDER BY ordem ASC, criado_em DESC'))
    return render_cf('index.html', parceiros=parceiros, avaliacoes=avaliacoes)


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

    _db_run('''INSERT INTO candidato
               (nome_completo, data_nascimento, idade, escolaridade, email,
                atividade_remunerada, curriculo, criado_em)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?)''',
            nome, nascimento.isoformat(), idade, escolaridade, email, curriculo, agora_utc_iso())
    flash('Currículo enviado com sucesso. A COOPEX analisará as informações.', 'ok')
    return redirect(url_for('index') + '#trabalhe')


@app.route('/politica-de-privacidade')
def politica_privacidade():
    return render_cf('politica_privacidade.html')


@app.route('/admin-coopex', methods=['GET', 'POST'])
@app.route('/admin-site', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '')
        admin = _one('SELECT * FROM admin_user WHERE usuario = ? LIMIT 1', usuario)
        if admin and check_password_hash(admin['senha_hash'], senha):
            session['site_admin_logado'] = True
            session['site_admin_usuario'] = usuario
            return redirect(url_for('admin_dashboard'))
        flash('Usuário ou senha inválidos.', 'erro')
    return render_cf('admin_login.html')


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

    parceiros = _objs(_rows('SELECT * FROM partner ORDER BY ordem ASC, nome ASC'))
    avaliacoes = _objs(_rows('SELECT * FROM review ORDER BY ordem ASC, criado_em DESC'))
    candidatos = _objs(_rows('SELECT * FROM candidato ORDER BY criado_em DESC LIMIT 100'))
    contador = _one('SELECT total_acessos FROM site_access LIMIT 1')
    total_acessos_site = int(contador['total_acessos'] or 0) if contador else 0

    return render_cf(
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
    candidato = _one('SELECT * FROM candidato WHERE id = ? LIMIT 1', candidato_id)
    if not candidato:
        abort(404)
    excluir_arquivo_referencia(candidato.get('curriculo'))
    _db_run('DELETE FROM candidato WHERE id = ?', candidato_id)
    flash('Currículo excluído com sucesso.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/instagram')
@app.route('/card-instagram')
def card_instagram():
    links = _objs(_rows('SELECT * FROM card_link WHERE ativo = 1 ORDER BY ordem ASC, criado_em ASC'))
    return render_cf('instagram_card.html', card=card_config_dict(), links=links)


@app.route('/card-link/<int:link_id>/ir')
def card_link_ir(link_id):
    link = _one('SELECT * FROM card_link WHERE id = ? LIMIT 1', link_id)
    if not link:
        abort(404)
    _db_run('UPDATE card_link SET cliques = COALESCE(cliques, 0) + 1 WHERE id = ?', link_id)
    if link.get('url') and link['url'] != '#':
        return redirect(link['url'])
    return redirect(url_for('card_instagram'))


@app.route('/admin-coopex/card')
@app.route('/admin-site/card')
def admin_card():
    if not login_required():
        return redirect(url_for('admin_login'))
    links = _objs(_rows('SELECT * FROM card_link ORDER BY ordem ASC, criado_em ASC'))
    return render_cf('admin_card.html', card=card_config_dict(), links=links)


@app.route('/admin-coopex/card/salvar', methods=['POST'])
@app.route('/admin-site/card/salvar', methods=['POST'])
def salvar_card_configuracoes():
    if not login_required():
        return redirect(url_for('admin_login'))

    campos_texto = [
        'card_nome', 'card_descricao', 'card_bio', 'card_localizacao', 'card_mapa_link',
        'card_cor_primaria', 'card_cor_secundaria', 'card_cor_texto', 'card_cor_botao',
        'card_cor_texto_botao', 'card_estilo', 'card_botao_whatsapp', 'card_link_whatsapp'
    ]
    for chave in campos_texto:
        set_config(chave, request.form.get(chave, CARD_DEFAULTS.get(chave, '')))
    set_config('card_mostrar_video', '1' if request.form.get('card_mostrar_video') == 'on' else '0')

    for campo, prefixo, allowed in [
        ('card_foto', 'card_foto', ALLOWED_IMAGE_EXTENSIONS),
        ('card_logo', 'card_logo', ALLOWED_IMAGE_EXTENSIONS),
        ('card_fundo_imagem', 'card_fundo', ALLOWED_IMAGE_EXTENSIONS),
        ('card_video', 'card_video', ALLOWED_VIDEO_EXTENSIONS),
    ]:
        valor = salvar_upload(request.files.get(campo), prefixo, allowed)
        if valor:
            antigo = get_config(campo, '')
            if antigo:
                excluir_arquivo_referencia(antigo)
            set_config(campo, valor)

    flash('Card do Instagram atualizado com sucesso.', 'ok')
    return redirect(url_for('admin_card'))


@app.route('/admin-coopex/card/link/novo', methods=['POST'])
@app.route('/admin-site/card/link/novo', methods=['POST'])
def card_link_novo():
    if not login_required():
        return redirect(url_for('admin_login'))
    titulo = request.form.get('titulo', '').strip()
    if not titulo:
        flash('Informe o título do botão/link.', 'erro')
        return redirect(url_for('admin_card'))
    subtitulo = request.form.get('subtitulo', '').strip()
    url = request.form.get('url', '').strip() or '#'
    ativo = 1 if request.form.get('ativo') == 'on' else 0
    ordem = int(request.form.get('ordem') or 0)
    icone = salvar_upload(request.files.get('icone'), 'card_icone', ALLOWED_IMAGE_EXTENSIONS)
    _db_run('''INSERT INTO card_link
               (titulo, subtitulo, url, icone, ativo, ordem, cliques, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?)''',
            titulo, subtitulo, url, icone, ativo, ordem, agora_utc_iso())
    flash('Link cadastrado no card.', 'ok')
    return redirect(url_for('admin_card'))


@app.route('/admin-coopex/card/link/<int:link_id>/editar', methods=['POST'])
@app.route('/admin-site/card/link/<int:link_id>/editar', methods=['POST'])
def card_link_editar(link_id):
    if not login_required():
        return redirect(url_for('admin_login'))
    link = _one('SELECT * FROM card_link WHERE id = ? LIMIT 1', link_id)
    if not link:
        abort(404)

    titulo = request.form.get('titulo', link['titulo']).strip()
    subtitulo = request.form.get('subtitulo', link.get('subtitulo') or '').strip()
    url = request.form.get('url', link['url']).strip() or '#'
    ordem = int(request.form.get('ordem') or 0)
    ativo = 1 if request.form.get('ativo') == 'on' else 0
    icone = salvar_upload(request.files.get('icone'), 'card_icone', ALLOWED_IMAGE_EXTENSIONS)
    if icone:
        excluir_arquivo_referencia(link.get('icone'))
    else:
        icone = link.get('icone')

    _db_run('''UPDATE card_link SET titulo = ?, subtitulo = ?, url = ?, icone = ?,
               ativo = ?, ordem = ? WHERE id = ?''',
            titulo, subtitulo, url, icone, ativo, ordem, link_id)
    flash('Link atualizado.', 'ok')
    return redirect(url_for('admin_card'))


@app.route('/admin-coopex/card/link/<int:link_id>/excluir', methods=['POST'])
@app.route('/admin-site/card/link/<int:link_id>/excluir', methods=['POST'])
def card_link_excluir(link_id):
    if not login_required():
        return redirect(url_for('admin_login'))
    link = _one('SELECT * FROM card_link WHERE id = ? LIMIT 1', link_id)
    if not link:
        abort(404)
    excluir_arquivo_referencia(link.get('icone'))
    _db_run('DELETE FROM card_link WHERE id = ?', link_id)
    flash('Link excluído do card.', 'ok')
    return redirect(url_for('admin_card'))


@app.route('/admin-coopex/configuracoes', methods=['POST'])
@app.route('/admin-site/configuracoes', methods=['POST'])
def salvar_configuracoes():
    if not login_required():
        return redirect(url_for('admin_login'))

    upload_config_keys = {
        'imagem_destaque', 'foto_bau', 'anuncio_bau_frente',
        'anuncio_bau_lado', 'anuncio_bau_traseira'
    }
    for chave in DEFAULTS:
        if chave not in upload_config_keys:
            set_config(chave, request.form.get(chave, DEFAULTS[chave]))

    for campo, prefixo in [
        ('imagem_destaque', 'destaque'),
        ('foto_bau', 'bau'),
        ('anuncio_bau_frente', 'anuncio_frente'),
        ('anuncio_bau_lado', 'anuncio_lado'),
        ('anuncio_bau_traseira', 'anuncio_traseira'),
    ]:
        valor = salvar_upload(request.files.get(campo), prefixo, ALLOWED_IMAGE_EXTENSIONS)
        if valor:
            antigo = get_config(campo, '')
            if antigo:
                excluir_arquivo_referencia(antigo)
            set_config(campo, valor)

    flash('Informações do site atualizadas com sucesso.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-coopex/parceiros/novo', methods=['POST'])
@app.route('/admin-site/parceiros/novo', methods=['POST'])
def parceiro_novo():
    if not login_required():
        return redirect(url_for('admin_login'))
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Informe o nome do parceiro.', 'erro')
        return redirect(url_for('admin_dashboard'))
    link = request.form.get('link', '').strip() or '#'
    ordem = int(request.form.get('ordem') or 0)
    ativo = 1 if request.form.get('ativo') == 'on' else 0
    logo = salvar_upload(request.files.get('logo'), 'parceiro', ALLOWED_IMAGE_EXTENSIONS)
    _db_run('''INSERT INTO partner
               (nome, link, logo, ativo, ordem, cliques, criado_em)
               VALUES (?, ?, ?, ?, ?, 0, ?)''',
            nome, link, logo, ativo, ordem, agora_utc_iso())
    flash('Parceiro cadastrado com sucesso.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-coopex/parceiros/<int:partner_id>/editar', methods=['POST'])
@app.route('/admin-site/parceiros/<int:partner_id>/editar', methods=['POST'])
def parceiro_editar(partner_id):
    if not login_required():
        return redirect(url_for('admin_login'))
    parceiro = _one('SELECT * FROM partner WHERE id = ? LIMIT 1', partner_id)
    if not parceiro:
        abort(404)

    nome = request.form.get('nome', parceiro['nome']).strip()
    link = request.form.get('link', parceiro['link']).strip() or '#'
    ordem = int(request.form.get('ordem') or 0)
    ativo = 1 if request.form.get('ativo') == 'on' else 0
    logo = salvar_upload(request.files.get('logo'), 'parceiro', ALLOWED_IMAGE_EXTENSIONS)
    if logo:
        excluir_arquivo_referencia(parceiro.get('logo'))
    else:
        logo = parceiro.get('logo')

    _db_run('UPDATE partner SET nome = ?, link = ?, logo = ?, ativo = ?, ordem = ? WHERE id = ?',
            nome, link, logo, ativo, ordem, partner_id)
    flash('Parceiro atualizado.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/parceiro/<int:partner_id>/ir')
def parceiro_ir(partner_id):
    parceiro = _one('SELECT * FROM partner WHERE id = ? LIMIT 1', partner_id)
    if not parceiro:
        abort(404)
    _db_run('UPDATE partner SET cliques = COALESCE(cliques, 0) + 1 WHERE id = ?', partner_id)
    if parceiro.get('link') and parceiro['link'] != '#':
        return redirect(parceiro['link'])
    return redirect(url_for('index') + '#parceiros')


@app.route('/admin-coopex/parceiros/<int:partner_id>/excluir', methods=['POST'])
@app.route('/admin-site/parceiros/<int:partner_id>/excluir', methods=['POST'])
def parceiro_excluir(partner_id):
    if not login_required():
        return redirect(url_for('admin_login'))
    parceiro = _one('SELECT * FROM partner WHERE id = ? LIMIT 1', partner_id)
    if not parceiro:
        abort(404)
    excluir_arquivo_referencia(parceiro.get('logo'))
    _db_run('DELETE FROM partner WHERE id = ?', partner_id)
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
    ativo = 1 if request.form.get('ativo') == 'on' else 0
    foto = salvar_upload(request.files.get('foto'), 'avaliacao', ALLOWED_IMAGE_EXTENSIONS)
    try:
        nota = max(1, min(5, int(request.form.get('nota') or 5)))
    except ValueError:
        nota = 5

    if not nome or not comentario:
        flash('Informe o nome e o comentário da avaliação.', 'erro')
        return redirect(url_for('admin_dashboard'))

    _db_run('''INSERT INTO review
               (nome, empresa, comentario, nota, data_avaliacao, link, foto, ativo, ordem, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            nome, empresa, comentario, nota, data_avaliacao, link, foto, ativo, ordem, agora_utc_iso())
    flash('Avaliação cadastrada com sucesso.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-coopex/avaliacoes/<int:review_id>/editar', methods=['POST'])
@app.route('/admin-site/avaliacoes/<int:review_id>/editar', methods=['POST'])
def avaliacao_editar(review_id):
    if not login_required():
        return redirect(url_for('admin_login'))
    avaliacao = _one('SELECT * FROM review WHERE id = ? LIMIT 1', review_id)
    if not avaliacao:
        abort(404)

    nome = request.form.get('nome', avaliacao['nome']).strip()
    empresa = request.form.get('empresa', avaliacao.get('empresa') or '').strip()
    comentario = request.form.get('comentario', avaliacao['comentario']).strip()
    data_avaliacao = request.form.get('data_avaliacao', avaliacao.get('data_avaliacao') or '').strip()
    link = request.form.get('link', avaliacao.get('link') or '#').strip() or '#'
    ordem = int(request.form.get('ordem') or 0)
    ativo = 1 if request.form.get('ativo') == 'on' else 0
    try:
        nota = max(1, min(5, int(request.form.get('nota') or avaliacao.get('nota') or 5)))
    except ValueError:
        nota = 5
    foto = salvar_upload(request.files.get('foto'), 'avaliacao', ALLOWED_IMAGE_EXTENSIONS)
    if foto:
        excluir_arquivo_referencia(avaliacao.get('foto'))
    else:
        foto = avaliacao.get('foto')

    _db_run('''UPDATE review SET nome = ?, empresa = ?, comentario = ?, nota = ?,
               data_avaliacao = ?, link = ?, foto = ?, ativo = ?, ordem = ? WHERE id = ?''',
            nome, empresa, comentario, nota, data_avaliacao, link, foto, ativo, ordem, review_id)
    flash('Avaliação atualizada.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-coopex/avaliacoes/<int:review_id>/excluir', methods=['POST'])
@app.route('/admin-site/avaliacoes/<int:review_id>/excluir', methods=['POST'])
def avaliacao_excluir(review_id):
    if not login_required():
        return redirect(url_for('admin_login'))
    avaliacao = _one('SELECT * FROM review WHERE id = ? LIMIT 1', review_id)
    if not avaliacao:
        abort(404)
    excluir_arquivo_referencia(avaliacao.get('foto'))
    _db_run('DELETE FROM review WHERE id = ?', review_id)
    flash('Avaliação excluída.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/api/site/parceiros')
def api_parceiros():
    parceiros = _rows('SELECT * FROM partner WHERE ativo = 1 ORDER BY ordem ASC, nome ASC')
    return jsonify({
        'ok': True,
        'parceiros': [
            {
                'nome': p['nome'],
                'link': p['link'],
                'logo': arquivo_url(p.get('logo')) if p.get('logo') else None,
            }
            for p in parceiros
        ]
    })


Default = wsgi.entrypoint(app)
