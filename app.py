from datetime import datetime, date, timezone, timedelta
from io import BytesIO
from types import SimpleNamespace

from flask import (
    Flask, Response, abort, flash, jsonify, redirect, render_template_string,
    request, send_file, session, url_for, render_template, make_response
)
from pyodide.ffi import run_sync
import hashlib
import hmac
import secrets
from werkzeug.utils import secure_filename
from workers import wsgi
from templates_cf import TEMPLATES
from jinja2 import DictLoader

app = Flask(__name__, static_folder=None)
# SEO: expose the existing COOPEX icon at a stable crawlable URL.
import re as _seo_re
from urllib.parse import unquote as _seo_unquote

_SEO_FAVICON_MATCH = _seo_re.search(r'href="data:image/svg\+xml,([^"]+)"', TEMPLATES["index.html"])
_SEO_FAVICON_SVG = _seo_unquote(_SEO_FAVICON_MATCH.group(1)) if _SEO_FAVICON_MATCH else ""
_SEO_FAVICON_URL = "https://www.coopexentregas.com.br/favicon.svg"
for _seo_name, _seo_html in list(TEMPLATES.items()):
    if _SEO_FAVICON_SVG:
        _seo_html = _seo_re.sub(r'href="data:image/svg\+xml,[^"]+"', 'href="' + _SEO_FAVICON_URL + '"', _seo_html)
    if _seo_name == "index.html":
        _seo_html = _seo_html.replace('"@type":"Organization","name":"COOPEX Entregas"', '"@type":"Organization","logo":"https://www.coopexentregas.com.br/static/img/coopex-oficial-v2.webp","sameAs":["https://www.instagram.com/coopex.entregas/"],"name":"COOPEX Entregas"', 1)
        _seo_html = _seo_html.replace('</head>', '<meta property="og:image" content="https://www.coopexentregas.com.br/static/img/coopex-oficial-v2.webp"></head>', 1)
    if _seo_name == "instagram_card.html" or "privacidade" in _seo_name:
        _seo_path = "/card-instagram" if _seo_name == "instagram_card.html" else "/politica-de-privacidade"
        if not _seo_re.search(r'rel=["\']canonical["\']', _seo_html):
            _seo_html = _seo_html.replace('</head>', '<link rel="canonical" href="https://www.coopexentregas.com.br' + _seo_path + '"></head>', 1)
    TEMPLATES[_seo_name] = _seo_html

@app.route('/favicon.svg')
def favicon_publico():
    if not _SEO_FAVICON_SVG:
        abort(404)
    return Response(_SEO_FAVICON_SVG, mimetype='image/svg+xml', headers={'Cache-Control': 'public, max-age=86400'})


# Pre-render a square transparent icon using standard-library PNG encoding.
# The artwork is the same six curves and four circles as the existing SVG.
def _coopex_png():
    import struct, zlib
    n = 96
    scale = 64 / n
    curves = [(7,18,17,8,30,19,'00194A','09A9F5'),(34,19,46,8,57,18,'003322','00D66B'),(7,45,17,56,30,45,'00194A','09A9F5'),(34,45,46,56,57,45,'003322','00D66B'),(30,19,25,30,31,44,'00417D','078FF0'),(34,19,39,30,33,44,'005B30','00D66B')]
    pixels = bytearray(n*n*4)
    def stamp(x,y,r,c):
        rgb=bytes.fromhex(c)
        for iy in range(max(0,int((y-r-1)/scale)),min(n,int((y+r+1)/scale)+1)):
            for ix in range(max(0,int((x-r-1)/scale)),min(n,int((x+r+1)/scale)+1)):
                d=((ix*scale+scale/2-x)**2+(iy*scale+scale/2-y)**2)**.5
                alpha=max(0,min(255,int((r+scale/2-d)*255/scale)))
                if alpha:
                    k=(iy*n+ix)*4
                    old=pixels[k+3]
                    out=alpha+old*(255-alpha)//255
                    for j in range(3):
                        pixels[k+j]=(rgb[j]*alpha+pixels[k+j]*old*(255-alpha)//255)//out
                    pixels[k+3]=out
    for x,y,cx,cy,ex,ey,dark,light in curves:
        for radius,color in ((6,dark),(4.5,light)):
            for i in range(81):
                t=i/80; q=1-t
                stamp(q*q*x+2*q*t*cx+t*t*ex,q*q*y+2*q*t*cy+t*t*ey,radius,color)
    for x,y in ((32,5.8),(32,58.2),(18.5,32),(45.5,32)):
        stamp(x,y,5.9,'193252'); stamp(x,y,4.5,'ffffff')
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    raw=b''.join(b'\x00'+pixels[y*n*4:(y+1)*n*4] for y in range(n))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',n,n,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')

from functools import lru_cache
_coopex_png = lru_cache(maxsize=1)(_coopex_png)

@app.route('/favicon.png')
def favicon_png():
    return Response(_coopex_png(), mimetype='image/png', headers={'Cache-Control':'public, max-age=86400'})

@app.route('/favicon.ico')
def favicon_ico():
    import struct
    png=_coopex_png()
    data=struct.pack('<HHHBBBBHHII',0,1,1,96,96,0,0,1,32,len(png),22)+png
    return Response(data,mimetype='image/x-icon',headers={'Cache-Control':'public, max-age=86400'})

for _seo_name, _seo_html in list(TEMPLATES.items()):
    if '</head>' in _seo_html:
        _seo_html = _seo_html.replace('</head>', '<link rel="icon" type="image/png" sizes="96x96" href="https://www.coopexentregas.com.br/favicon.png"><link rel="shortcut icon" href="https://www.coopexentregas.com.br/favicon.ico"></head>', 1)
    if _seo_name == 'index.html':
        _seo_html = _seo_html.replace('</head>', '<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"COOPEX Entregas","alternateName":"COOPEX","url":"https://www.coopexentregas.com.br/"}</script><meta property="og:site_name" content="COOPEX Entregas"></head>',1)
    TEMPLATES[_seo_name] = _seo_html

app.jinja_loader = DictLoader(TEMPLATES)
app.config['SECRET_KEY'] = 'troque-esta-chave-no-cloudflare'
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
app.config['MAX_FORM_MEMORY_SIZE'] = 512 * 1024

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}
ALLOWED_CURRICULO_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'webp'}
CHUNK_SIZE = 1_500_000
FUSO_NATAL = timezone(timedelta(hours=-3))

DEFAULTS = {
    'nome_cooperativa': 'COOPEX',
    'titulo_principal': 'Entregas profissionais para empresas, restaurantes e estabelecimentos',
    'subtitulo_principal': 'Desde 2002, a COOPEX atua em Natal/RN oferecendo soluções de entrega com cooperados organizados, fardados e suporte operacional.',
    'whatsapp': '84981110706',
    'telefone': '(84) 3234-9025 / 3231-5623 / 98111-0706',
    'email': 'contato@coopexentregas.com.br',
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
    'card_estilo': 'vidro',
    'card_colunas': '2',
    'card_raio': '19',
    'card_altura_botao': '68',
    'card_avatar_tamanho': '118',
    'card_intensidade_vidro': '78',
    'card_rodape': '',
    'card_mostrar_logo': '1',
    'card_mostrar_localizacao': '1',
    'card_mostrar_avatar': '1',
    'card_mostrar_rodape': '1',
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


def gerar_hash_senha(senha, salt=None):
    """
    Hash compatível com Cloudflare Python Workers sem depender de
    hashlib.scrypt ou hashlib.pbkdf2_hmac.
    """
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{senha}".encode("utf-8")).hexdigest()
    return f"sha256${salt}${digest}"


def verificar_senha(hash_salvo, senha):
    try:
        metodo, salt, digest_salvo = str(hash_salvo).split("$", 2)
    except ValueError:
        return False

    if metodo != "sha256":
        return False

    digest_atual = hashlib.sha256(
        f"{salt}:{senha}".encode("utf-8")
    ).hexdigest()

    return hmac.compare_digest(digest_salvo, digest_atual)


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
    asset = run_sync(
        _env().ASSETS.fetch(
            f'https://assets.local/{asset_path.lstrip("/")}'
        )
    )
    body = run_sync(asset.bytes())
    return Response(
        body,
        status=asset.status,
        headers=asset.headers
    )


SITE_CSS = r''':root{
  --azul:#0047b8;
  --azul-royal:#0057d9;
  --azul-escuro:#062a59;
  --verde:#00b86b;
  --verde-escuro:#008f53;
  --branco:#ffffff;
  --cinza:#f4f8fd;
  --texto:#132238;
  --muted:#64748b;
  --borda:#dbe5f1;
  --sombra:0 18px 45px rgba(3,37,92,.14);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:Arial,Helvetica,sans-serif;color:var(--texto);background:#eaf6ff;min-height:100vh}
a{text-decoration:none;color:inherit}
button{font-family:inherit}
.container{width:min(1360px,94%);margin:0 auto}

.topo{
  position:sticky;
  top:0;
  z-index:50;
  background:linear-gradient(90deg,#003c9e,var(--azul-royal));
  box-shadow:0 10px 24px rgba(0,45,120,.18);
}

.nav{
  position:relative;
  display:flex;
  align-items:center;
  min-height:98px;
  gap:18px;
  padding-right:8px;
}

.brand{
  border:0;
  background:transparent;
  padding:0;
  cursor:pointer;
  display:flex;
  align-items:center;
  justify-content:flex-start;
  min-width:280px;
  z-index:3;
}

.brand img{
  height:82px;
  width:auto;
  max-width:250px;
  object-fit:contain;
  display:block;
  filter:drop-shadow(0 4px 0 rgba(255,255,255,.16)) drop-shadow(0 10px 14px rgba(0,0,0,.32));
}

.somos-wrap{
  position:absolute;
  left:50%;
  top:50%;
  transform:translate(-50%, -50%);
  display:flex;
  align-items:center;
  justify-content:center;
  pointer-events:none;
  z-index:2;
}

.somos-wrap img{
  height:72px;
  width:auto;
  max-width:360px;
  object-fit:contain;
  display:block;
  filter:drop-shadow(0 3px 8px rgba(0,0,0,.20));
}

.links{
  margin-left:auto;
  margin-right:0;
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap:8px;
  white-space:nowrap;
  padding-left:420px;
  position:relative;
  z-index:3;
}

.links :is(button,a){
  border:1px solid rgba(255,255,255,.30);
  background:rgba(255,255,255,.10);
  color:#fff;
  padding:9px 13px;
  border-radius:999px;
  cursor:pointer;
  font-weight:800;
  font-size:14px;
  line-height:1.1;
  white-space:nowrap;
}

.links :is(button,a):hover,
.links :is(button,a).active{
  background:#fff;
  color:#0b4bbb;
}

.menu-btn{
  display:none;
  border:1px solid rgba(255,255,255,.45);
  background:rgba(255,255,255,.13);
  color:#fff;
  border-radius:14px;
  font-size:22px;
  padding:8px 12px;
}

.page-section{display:none;min-height:calc(100vh - 92px)}
.page-section.active{display:block}
.hero{background:radial-gradient(circle at top right,rgba(0,169,92,.18),transparent 34%),linear-gradient(180deg,#dff2ff 0%,#eef8ff 100%);padding:34px 0 30px}
.hero-container{width:min(1360px,94%)}
.hero-banner{position:relative;min-height:640px;border:1px solid var(--borda);border-radius:32px;overflow:hidden;box-shadow:0 24px 58px rgba(3,37,92,.16);background:#eef4fa}
.hero-bg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
.hero-placeholder-bg{display:flex;flex-direction:column;align-items:flex-end;justify-content:center;text-align:center;padding:36px 70px;background:linear-gradient(135deg,#eef5fb,#dfeefa);color:#0b315f}
.hero-placeholder-bg strong{font-size:28px}
.hero-placeholder-bg span{max-width:460px;margin-top:10px;color:#52667f;line-height:1.5}
.hero-shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(241,248,255,.98) 0%,rgba(241,248,255,.95) 32%,rgba(241,248,255,.68) 48%,rgba(241,248,255,.16) 68%,rgba(241,248,255,0) 100%)}
.hero-copy{position:relative;z-index:2;width:min(590px,48%);min-height:640px;padding:56px 46px;display:flex;flex-direction:column;justify-content:center}
.hero-copy h1{font-size:clamp(36px,4.15vw,62px);line-height:1.02;margin:16px 0 18px;color:var(--azul-escuro);letter-spacing:-1.8px;max-width:100%;overflow-wrap:break-word}
.hero-copy p{font-size:18px;line-height:1.62;color:#36506e;margin:0 0 26px;max-width:520px}
.tag{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;background:#e8f2ff;color:#0b4bbb;font-weight:900;font-size:13px;width:max-content;max-width:100%}
.tag.verde{background:#e6fff2;color:#008747}
.tag.azul{background:#e8f2ff;color:#0b4bbb}
.actions{display:flex;gap:12px;flex-wrap:wrap}
.btn{border:0;border-radius:999px;padding:13px 20px;font-weight:900;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px}
.btn.primary{background:linear-gradient(135deg,var(--verde),#00c777);color:#fff;box-shadow:0 10px 24px rgba(0,169,92,.25)}
.btn.secondary{background:#fff;color:#0b4bbb;border:1px solid #cfe0f5}
.btn.danger{background:#ffe8e8;color:#b10000}
.btn.small{padding:9px 13px;font-size:13px}
.btn.full{width:100%}

.secao{padding:72px 0}
.secao.soft{background:#eaf6ff}
.two-col{display:grid;grid-template-columns:1.1fr .9fr;gap:32px;align-items:center}
.two-col h2,.center h2,.contato h2,.work-info h2{font-size:clamp(28px,4vw,44px);line-height:1.1;margin:14px 0;color:var(--azul-escuro)}
.two-col p,.center p,.contato p,.work-info p{font-size:18px;line-height:1.65;color:#40546f}
.stats{display:grid;grid-template-columns:1fr;gap:14px}
.stats div{background:#fff;border:1px solid var(--borda);border-radius:22px;padding:24px;box-shadow:0 10px 26px rgba(3,37,92,.08)}
.stats strong{display:block;font-size:32px;color:var(--azul)}
.stats span{color:var(--muted);font-weight:700}
.center{text-align:center;max-width:760px;margin:0 auto 28px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.card{background:#fff;border:1px solid var(--borda);border-radius:24px;padding:24px;box-shadow:0 10px 26px rgba(3,37,92,.08)}
.card.destaque{border-color:rgba(0,169,92,.35)}
.card-icon{font-size:34px;margin-bottom:12px}
.card h3{font-size:22px;color:var(--azul-escuro)}
.card ul{padding-left:18px;color:#40546f;line-height:1.8}

.carousel-shell{overflow:hidden;background:#fff;border:1px solid var(--borda);border-radius:26px;padding:22px;box-shadow:var(--sombra)}
.partner-track{display:flex;gap:18px;width:max-content;animation:scrollPartners 28s linear infinite}
.carousel-shell:hover .partner-track{animation-play-state:paused}
.partner{width:190px;min-height:140px;background:#fff;border:1px solid #e3edf8;border-radius:22px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:16px;box-shadow:0 8px 18px rgba(3,37,92,.06)}
.partner img{max-width:150px;max-height:78px;width:auto;height:auto;object-fit:contain}
.partner span{font-size:13px;font-weight:800;color:#334155;text-align:center}
.partner-placeholder{width:70px;height:70px;border-radius:20px;background:#e8f2ff;color:#0b4bbb;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:24px}
@keyframes scrollPartners{from{transform:translateX(0)}to{transform:translateX(-50%)}}

.trabalhe-grid{display:grid;grid-template-columns:.95fr 1.05fr;gap:28px;align-items:start}
.work-info,.work-form{background:#fff;border:1px solid var(--borda);border-radius:28px;padding:26px;box-shadow:var(--sombra)}
.bau-box,.docs-box{margin-top:18px;border:1px solid #dbeafe;background:#f8fbff;border-radius:22px;padding:18px}
.bau-box h3,.docs-box h3,.work-form h3{margin:0 0 14px;color:var(--azul-escuro)}
.bau-img{width:100%;max-height:280px;object-fit:contain;border-radius:18px;background:#fff;border:1px solid var(--borda);display:block}
.bau-placeholder{height:220px;border:2px dashed #bdd7f5;border-radius:18px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-weight:800;background:#fff}
.bau-details p{font-size:15px;margin:10px 0;color:#40546f}
.work-form label{display:block;font-weight:800;color:#334155;margin-bottom:14px}
.work-form input,.work-form select{width:100%;margin-top:7px;border:1px solid #cdd9ea;border-radius:14px;padding:12px 13px;font-size:15px;background:#fff}
.check-line{display:flex!important;gap:10px;align-items:flex-start;font-weight:700!important}
.check-line input{width:auto!important;margin-top:3px!important}
.form-note{display:block;margin-top:12px;color:var(--muted);line-height:1.4}

.contato{background:#eaf6ff}
.contato-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:22px;align-items:start}
.contact-list{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:18px}
.contact-list a,.contact-list div{background:#f7fbff;border:1px solid #dbeafe;border-radius:20px;padding:16px;display:grid;grid-template-columns:36px 1fr;column-gap:10px;align-items:center}
.contact-list span{width:36px;height:36px;border-radius:50%;background:var(--azul);color:#fff;display:flex;align-items:center;justify-content:center}
.contact-list strong{color:var(--azul-escuro)}
.contact-list small{grid-column:2;color:#475569;word-break:break-word}
.contato-card{background:linear-gradient(135deg,var(--azul),var(--azul-royal));color:#fff;border-radius:28px;padding:28px;box-shadow:var(--sombra)}
.contato-card p{color:#eaf3ff}

.floating-delivery{position:fixed;right:22px;bottom:22px;z-index:70;border:0;border-radius:999px;background:linear-gradient(135deg,var(--verde),#00c777);color:#fff;padding:11px 16px;display:flex;align-items:center;gap:9px;box-shadow:0 16px 35px rgba(0,100,60,.35);cursor:pointer}
.floating-delivery span{width:42px;height:42px;border-radius:50%;background:rgba(255,255,255,.22);display:flex;align-items:center;justify-content:center;font-size:22px}
.floating-delivery strong{font-size:14px}

.modal-solicitacao{display:none;position:fixed;inset:0;background:rgba(0,20,50,.68);z-index:90;padding:22px}
.modal-solicitacao.aberto{display:flex;align-items:center;justify-content:center}
.modal-card{background:#fff;border-radius:24px;width:min(1180px,100%);height:90vh;overflow:hidden;box-shadow:0 25px 70px rgba(0,0,0,.35);display:flex;flex-direction:column}
.iframe-top{height:58px;padding:0 16px;background:var(--azul);color:#fff;display:flex;align-items:center;justify-content:space-between;gap:12px}
.iframe-top div{display:flex;align-items:center;gap:8px}
.mini-link,.mini-btn{background:#fff;color:var(--azul);border:0;border-radius:999px;padding:8px 12px;font-weight:800;cursor:pointer}
.modal-card iframe{border:0;width:100%;height:100%;background:#fff}

footer{border-top:1px solid var(--borda);background:#f8fbff;padding:18px 0;color:#64748b}
.footer-grid{display:flex;align-items:center;justify-content:space-between;gap:12px}

.site-flashes{padding-top:16px}
.flash{padding:12px 14px;border-radius:14px;margin-bottom:12px;font-weight:800}
.flash.ok{background:#e8fff2;color:#00713d;border:1px solid #b7f0d0}
.flash.erro{background:#fff0f0;color:#a00000;border:1px solid #ffcaca}

.admin-bg{background:linear-gradient(135deg,#e8f2ff,#fff)}
.login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.login-card{width:min(420px,94vw);background:#fff;border:1px solid var(--borda);border-radius:28px;padding:30px;box-shadow:var(--sombra)}
.login-card img{height:110px;width:auto;object-fit:contain;display:block;margin:0 auto 10px}
.login-card h1{text-align:center;color:var(--azul-escuro)}
.login-card p{text-align:center;color:var(--muted)}
.login-card label{font-weight:800;color:#334155}
.login-card input{width:100%;border:1px solid #cdd9ea;border-radius:14px;padding:13px;margin:7px 0 15px}
.voltar{display:block;text-align:center;margin-top:14px;color:var(--azul);font-weight:800}

.admin-page{background:#f4f7fb}
.admin-top{position:sticky;top:0;z-index:30;background:#fff;border-bottom:1px solid var(--borda);padding:16px 4%;display:flex;align-items:center;justify-content:space-between}
.admin-top strong{display:block;color:var(--azul-escuro);font-size:20px}
.admin-top span{color:var(--muted)}
.admin-actions{display:flex;gap:10px}
.admin-container{width:min(1180px,94%);margin:24px auto}
.admin-box{background:#fff;border:1px solid var(--borda);border-radius:24px;padding:22px;margin-bottom:18px;box-shadow:0 8px 22px rgba(3,37,92,.06)}
.admin-box h2{margin-top:0;color:var(--azul-escuro)}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.form-grid label{font-weight:800;color:#334155}
.form-grid input,.form-grid textarea,.partner-form input,.edit-row input{width:100%;margin-top:7px;border:1px solid #cdd9ea;border-radius:13px;padding:11px;font-size:14px}
.form-grid textarea{min-height:90px;resize:vertical}
.form-grid small{display:block;color:var(--muted);margin-top:6px}
.admin-subtitle{grid-column:1/-1;margin-top:12px;padding-top:16px;border-top:1px solid var(--borda);font-size:20px;font-weight:900;color:var(--azul-escuro)}
.partner-form{display:grid;grid-template-columns:1.2fr 1.8fr .6fr .8fr 1.1fr auto;gap:10px;align-items:center}
.check{display:flex;align-items:center;gap:7px;font-weight:800}
.check input{width:auto!important}
.admin-list{display:grid;gap:12px}
.admin-partner{display:grid;grid-template-columns:80px 1fr auto;gap:12px;align-items:center;border:1px solid #e3edf8;border-radius:18px;padding:12px;background:#fbfdff}
.admin-thumb{width:72px;height:72px;border-radius:16px;background:#eef6ff;display:flex;align-items:center;justify-content:center;overflow:hidden;color:var(--azul);font-weight:900}
.admin-thumb img{max-width:100%;max-height:100%;object-fit:contain}
.edit-row{display:grid;grid-template-columns:1.1fr 1.6fr .5fr .7fr 1fr auto;gap:10px;align-items:center}
.candidate-row{border:1px solid #e3edf8;background:#fbfdff;border-radius:18px;padding:14px;display:flex;justify-content:space-between;gap:14px;align-items:center}
.candidate-row strong,.candidate-row span,.candidate-row small{display:block}
.candidate-row span{color:#40546f;margin-top:4px}
.candidate-row small{color:var(--muted);margin-top:4px}

@media(max-width:1180px){
  .nav{grid-template-columns:220px 1fr auto}
  .brand img{height:68px;max-width:220px}
  .somos-wrap{display:none}
  .links :is(button,a){font-size:13px;padding:9px 10px}
}
@media(max-width:980px){
  .container{width:min(94%,94%)}
  .nav{display:grid;grid-template-columns:190px 1fr auto;min-height:82px}
  .brand img{height:58px;max-width:190px}
  .menu-btn{display:block;justify-self:end}
  .links{display:none;position:absolute;left:4%;right:4%;top:82px;background:#fff;border:1px solid var(--borda);border-radius:18px;padding:16px;box-shadow:var(--sombra);flex-direction:column;align-items:stretch;gap:10px}
  .links :is(button,a){color:#0b3c88;background:#f3f8ff;border-color:#dbeafe;font-size:14px}
  .menu-open .links{display:flex}
  .hero{padding:24px 0 34px}
  .hero-banner{min-height:560px}
  .hero-shade{background:linear-gradient(90deg,rgba(241,248,255,.98) 0%,rgba(241,248,255,.92) 54%,rgba(241,248,255,.35) 100%)}
  .hero-copy{width:min(620px,80%);min-height:560px;padding:38px 30px}
  .hero-copy h1{font-size:clamp(32px,8vw,52px)}
  .two-col,.contato-grid,.trabalhe-grid{grid-template-columns:1fr}
  .cards{grid-template-columns:1fr}
  .contact-list{grid-template-columns:1fr}
  .footer-grid{flex-direction:column;gap:8px;text-align:center}
  .form-grid,.partner-form,.admin-partner,.edit-row{grid-template-columns:1fr}
  .admin-top{position:static;align-items:flex-start;gap:12px;flex-direction:column}
  .admin-actions{width:100%;justify-content:space-between}
  .modal-card{height:94vh}
  .floating-delivery{right:14px;bottom:14px;padding:8px}
  .floating-delivery strong{display:none}
  .carousel-shell{padding:16px}
  .partner{width:158px}
  .candidate-row{flex-direction:column;align-items:flex-start}
}
@media(max-width:620px){
  .nav{grid-template-columns:150px 1fr auto;gap:8px}
  .brand img{height:48px;max-width:150px}
  .hero-banner{min-height:auto;border-radius:24px}
  .hero-bg{position:absolute}
  .hero-shade{background:linear-gradient(180deg,rgba(241,248,255,.98) 0%,rgba(241,248,255,.94) 58%,rgba(241,248,255,.54) 100%)}
  .hero-copy{width:100%;min-height:520px;padding:34px 22px}
  .hero-copy h1{font-size:clamp(30px,10vw,44px);letter-spacing:-1px}
  .hero-copy p{font-size:16px;max-width:100%}
  .actions{flex-direction:column}
  .btn{width:100%}
}


.home-reviews{
  background:#eaf6ff;
  padding:0 0 34px;
}
.reviews-grid{
  display:grid;
  grid-template-columns:330px 1fr;
  gap:20px;
  align-items:stretch;
}
.reviews-title{
  background:#fff;
  border:1px solid #dbeafe;
  border-radius:26px;
  padding:24px;
  box-shadow:0 12px 26px rgba(3,37,92,.08);
}
.reviews-title h2{
  color:var(--azul-escuro);
  font-size:30px;
  margin:14px 0 8px;
  line-height:1.08;
}
.reviews-title p{
  margin:0;
  color:#49617d;
  line-height:1.55;
}
.google-pill{
  display:inline-flex;
  align-items:center;
  gap:8px;
  border:1px solid #dbeafe;
  background:#f8fbff;
  color:#0b315f;
  border-radius:999px;
  padding:8px 12px;
  font-weight:900;
  font-size:13px;
}
.google-pill strong,
.g-mark{
  width:24px;
  height:24px;
  border-radius:50%;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  background:#fff;
  color:#4285f4;
  box-shadow:0 2px 8px rgba(3,37,92,.12);
  font-weight:900;
}
.reviews-cards{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:16px;
}
.review-card{
  background:#fff;
  border:1px solid #dbeafe;
  border-radius:24px;
  padding:18px;
  box-shadow:0 12px 26px rgba(3,37,92,.08);
  min-height:210px;
  display:flex;
  flex-direction:column;
  transition:.2s ease;
}
.review-card:hover{
  transform:translateY(-3px);
  box-shadow:0 18px 34px rgba(3,37,92,.14);
}
.review-top{
  display:grid;
  grid-template-columns:42px 1fr 30px;
  gap:10px;
  align-items:center;
}
.avatar-google{
  width:42px;
  height:42px;
  border-radius:50%;
  background:linear-gradient(135deg,#0b57d0,#00a95c);
  color:#fff;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:900;
}
.review-top strong{
  display:block;
  color:#182b45;
}
.review-top small{
  display:block;
  color:#6b7f99;
  font-size:12px;
  margin-top:2px;
}
.stars{
  color:#fbbc04;
  font-size:18px;
  letter-spacing:1px;
  margin:14px 0 8px;
}
.review-card p{
  color:#40546f;
  line-height:1.55;
  margin:0 0 12px;
  flex:1;
}
.review-date{
  color:#7a8ba0;
  font-weight:800;
}

.mapa-card{
  grid-column:1 / -1;
  background:#fff;
  border:1px solid #dbeafe;
  border-radius:24px;
  padding:10px;
  box-shadow:var(--sombra);
  overflow:hidden;
}
.mapa-card iframe{
  width:100%;
  height:360px;
  border:0;
  display:block;
  border-radius:18px;
}

.admin-help{
  color:#64748b;
  margin-top:-6px;
}
.review-form-admin{
  display:grid;
  grid-template-columns:1.1fr 1.1fr .4fr .8fr 1.4fr .45fr .6fr;
  gap:10px;
  align-items:center;
  margin-bottom:16px;
}
.review-form-admin input,
.review-form-admin textarea,
.review-edit-row input,
.review-edit-row textarea{
  width:100%;
  border:1px solid #cdd9ea;
  border-radius:13px;
  padding:11px;
  font-size:14px;
}
.review-form-admin textarea{
  grid-column:1 / -2;
  min-height:70px;
  resize:vertical;
}
.admin-review{
  border:1px solid #e3edf8;
  border-radius:18px;
  padding:12px;
  background:#fbfdff;
  display:grid;
  grid-template-columns:1fr auto;
  gap:10px;
  align-items:start;
}
.review-edit-row{
  display:grid;
  grid-template-columns:1fr 1fr .35fr .7fr 1.2fr .4fr .55fr;
  gap:10px;
  align-items:center;
}
.review-edit-row textarea{
  grid-column:1 / -2;
  min-height:70px;
  resize:vertical;
}

@media(max-width:980px){
  .reviews-grid{
    grid-template-columns:1fr;
  }
  .reviews-cards{
    grid-template-columns:1fr;
  }
  .review-form-admin,
  .review-edit-row,
  .admin-review{
    grid-template-columns:1fr;
  }
  .review-form-admin textarea,
  .review-edit-row textarea{
    grid-column:auto;
  }
  .mapa-card iframe{
    height:300px;
  }
}


/* AJUSTE FINAL DO CABEÇALHO */
@media(min-width:1181px){
  .topo .container.nav{
    width:98%;
    max-width:none;
    margin-left:auto;
    margin-right:4px;
  }

  .somos-wrap{
    left:50%;
    transform:translate(-50%, -50%);
  }

  .links{
    margin-left:auto;
    margin-right:0;
    padding-left:420px;
    justify-content:flex-end;
  }
}

@media(max-width:1180px){
  .nav{
    display:grid;
    grid-template-columns:220px 1fr auto;
  }

  .brand{
    min-width:auto;
  }

  .brand img{
    height:68px;
    max-width:220px;
  }

  .somos-wrap{
    display:none;
  }

  .links{
    padding-left:0;
  }

  .links :is(button,a){
    font-size:13px;
    padding:9px 10px;
  }
}


/* Ajustes adicionados sem alterar o layout principal */
.avatar-google-img{
  width:56px;
  height:56px;
  min-width:56px;
  max-width:56px;
  border-radius:50%;
  object-fit:cover;
  display:block;
  border:2px solid #fff;
  box-shadow:0 2px 8px rgba(3,37,92,.18);
}

.review-top{
  grid-template-columns:56px minmax(0,1fr) 30px;
  gap:14px;
}

.review-top > div:nth-child(2){
  min-width:0;
  overflow:hidden;
}

.review-top strong,
.review-top small{
  overflow-wrap:break-word;
  line-height:1.2;
}

.info-grid-site{
  margin-top:28px;
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:18px;
}

.info-grid-site article,
.anuncio-info-grid article,
.anuncio-cta{
  background:#fff;
  border:1px solid #dbeafe;
  border-radius:24px;
  padding:22px;
  box-shadow:0 10px 26px rgba(3,37,92,.08);
}

.info-grid-site h3,
.anuncio-info-grid h3,
.anuncio-cta h3{
  margin:0 0 10px;
  color:var(--azul-escuro);
}

.info-grid-site p,
.anuncio-info-grid p,
.anuncio-cta p{
  margin:0;
  color:#40546f;
  line-height:1.6;
}

.docs-list{
  display:grid;
  gap:10px;
  list-style:none;
  padding:0;
  margin:0;
}

.docs-list li{
  background:#fff;
  border:1px solid #dbeafe;
  border-radius:14px;
  padding:12px 14px;
  color:#40546f;
  font-weight:700;
}

.bau-ads-grid{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:18px;
  margin-top:28px;
}

.bau-ad-card{
  background:#fff;
  border:1px solid #dbeafe;
  border-radius:24px;
  padding:18px;
  box-shadow:0 10px 26px rgba(3,37,92,.08);
  text-align:center;
}

.bau-ad-card img{
  width:100%;
  height:260px;
  object-fit:contain;
  display:block;
  border-radius:18px;
  background:#f8fbff;
  border:1px solid #e3edf8;
  margin-bottom:12px;
}

.bau-ad-card strong{
  color:var(--azul-escuro);
}

.bau-ad-placeholder{
  height:260px;
  border:2px dashed #bdd7f5;
  border-radius:18px;
  display:flex;
  align-items:center;
  justify-content:center;
  color:#64748b;
  font-weight:900;
  background:#fff;
  margin-bottom:12px;
}

.anuncio-info-grid{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:18px;
  margin-top:18px;
}

.anuncio-cta{
  margin-top:18px;
  text-align:center;
}

.foto-atual-avaliacao{
  display:flex;
  align-items:center;
  gap:8px;
  color:#64748b;
  font-size:12px;
  font-weight:800;
}

.foto-atual-avaliacao img{
  width:42px;
  height:42px;
  border-radius:50%;
  object-fit:cover;
  border:2px solid #fff;
  box-shadow:0 2px 8px rgba(3,37,92,.18);
}

@media(max-width:980px){
  .info-grid-site,
  .bau-ads-grid,
  .anuncio-info-grid{
    grid-template-columns:1fr;
  }

  .bau-ad-card img,
  .bau-ad-placeholder{
    height:220px;
  }
}


/* COOPEX DESIGN SYSTEM 2026 — glass editorial refinement */
:root{
  --azul:#0751ba;--azul-royal:#1258c7;--azul-escuro:#0b2d59;
  --verde:#08af70;--verde-escuro:#087d58;--texto:#183459;
  --borda:rgba(160,193,224,.52);
  --sombra:0 14px 38px rgba(19,64,120,.095);
}
html{scroll-behavior:smooth}
body{
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
  color:var(--texto);background:linear-gradient(135deg,#f7fbff,#ecf6ff 58%,#eefbf6);
  overflow-x:hidden;
  -webkit-font-smoothing:antialiased;
}
button,a,input,select{ -webkit-tap-highlight-color:transparent }
button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{
  outline:3px solid #20aaf0;outline-offset:3px
}
.container{width:min(1430px,calc(100% - 64px))}
.topo{
  background:rgba(245,250,255,.88);
  border-bottom:1px solid rgba(255,255,255,.72);
  box-shadow:0 6px 26px rgba(12,61,117,.08);
  -webkit-backdrop-filter:blur(22px) saturate(155%);
  backdrop-filter:blur(22px) saturate(155%);
}
.nav{
  min-height:76px;gap:18px;padding:8px 0;
  display:grid;grid-template-columns:minmax(170px,240px) minmax(90px,130px) minmax(0,1fr);
  align-items:center;
}
.brand{min-width:0;justify-content:flex-start}
.brand img{
  width:auto;height:57px;max-width:218px;object-fit:contain;
  filter:none; /* Logos do projeto permanecem intactas */
}
.somos-wrap{
  position:static;left:auto;top:auto;transform:none;
  pointer-events:auto;justify-self:center
}
.somos-wrap img{width:auto;height:45px;max-width:120px;filter:none}
.links{
  margin:0;padding:0;gap:3px;min-width:0;justify-content:flex-end;
  flex-wrap:nowrap;
}
.links :is(button,a){
  background:transparent;color:#174174;border:1px solid transparent;
  font-size:clamp(11px,.84vw,13px);font-weight:700;
  border-radius:12px;padding:10px 9px;white-space:nowrap;
  transition:background .2s,color .2s,box-shadow .2s
}
.links :is(button,a):hover,.links :is(button,a).active{
  background:#fff;color:#0751ba;
  border-color:#dce9f8;box-shadow:0 3px 12px rgba(9,68,141,.08)
}
.menu-btn{color:#0b4bbb;background:rgba(255,255,255,.82);border:1px solid #c9ddf4}
.page-section{min-height:0}
.secao,.hero,.home-reviews{
  background:transparent;padding:clamp(16px,2.25vw,32px) 0;
}
.hero-banner{
  min-height:0;height:clamp(400px,62vh,690px);
  border:1px solid rgba(255,255,255,.78);border-radius:30px;
  background:#dbeeff;box-shadow:0 18px 46px rgba(13,59,119,.13);
  isolation:isolate;
}
.hero-bg{object-fit:cover;object-position:center}
.hero-shade{
  background:linear-gradient(90deg,
    rgba(244,250,255,.98) 0%,rgba(241,249,255,.95) 31%,
    rgba(238,247,255,.67) 48%,rgba(238,247,255,.05) 75%)
}
.hero-copy{
  min-height:0;height:100%;width:min(620px,51%);
  padding:clamp(24px,3vw,52px);justify-content:center
}
.hero-copy h1{
  font-size:clamp(33px,3.35vw,56px);line-height:1.04;
  letter-spacing:-1.7px;margin:13px 0
}
.hero-copy p{font-size:clamp(14px,1.06vw,17px);line-height:1.55;margin:0 0 18px}
.tag{background:rgba(255,255,255,.72);border:1px solid #d8e8f8;font-weight:700}
.btn{font-size:14px;min-height:44px;transition:transform .18s,box-shadow .18s}
.btn:hover{transform:translateY(-2px)}
.btn.primary{
  background:#0bb879;color:#fff;
  box-shadow:0 7px 20px rgba(11,184,121,.20)
}
.btn.secondary{background:rgba(255,255,255,.78);border-color:rgba(184,210,237,.8)}
.selo-utilidade-box{
  margin-top:18px !important;padding:10px 13px !important;
  background:rgba(255,255,255,.80) !important;
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  box-shadow:0 8px 22px rgba(19,70,130,.11) !important;
  border:1px solid rgba(255,255,255,.82) !important;
  border-radius:18px !important
}
.selo-utilidade-box img{
  width:62px !important;height:62px !important;
  filter:none !important
}
.selo-utilidade-box strong{font-size:14px !important;letter-spacing:0 !important}
.selo-utilidade-box p{font-size:12px !important;line-height:1.3 !important}
.home-reviews{padding:10px 0 24px}
.reviews-grid{grid-template-columns:minmax(170px,.8fr) minmax(0,3fr);gap:12px}
.reviews-title,.review-card,.stat-card,.card,.partner,.work-info,.work-form,
.bau-ad-card,.info-grid-site article,.anuncio-info-grid article,.anuncio-cta,
.contato-card,.mapa-card,.contact-list a,.contact-list>div{
  background:rgba(255,255,255,.78);
  -webkit-backdrop-filter:blur(15px) saturate(135%);
  backdrop-filter:blur(15px) saturate(135%);
  border:1px solid rgba(255,255,255,.94);
  box-shadow:0 12px 28px rgba(23,76,135,.075);
  border-radius:20px
}
.reviews-title,.review-card{padding:16px}
.reviews-title h2{font-size:clamp(17px,1.4vw,22px);letter-spacing:-.5px}
.reviews-title p,.review-card p{font-size:13px;line-height:1.4}
.review-card{min-height:160px}
.review-card:hover,.card:hover,.contact-list a:hover,.partner:hover{
  transform:translateY(-2px);box-shadow:0 16px 30px rgba(14,57,112,.13)
}
.two-col{grid-template-columns:minmax(0,1.35fr) minmax(290px,.8fr);gap:22px;align-items:start}
.two-col h2,.center h2,.contato h2,.work-info h2{
  font-size:clamp(26px,2.6vw,40px);letter-spacing:-1.1px;line-height:1.13;margin:8px 0 14px
}
.two-col p,.center p,.contato p,.work-info p{font-size:15px;line-height:1.55}
.texto-sobre-admin{
  font-size:clamp(13px,.97vw,15px) !important;
  line-height:1.53 !important;text-align:left !important
}
.stats-modern{gap:8px !important}
.stats-modern .stat-card{
  min-height:0 !important;padding:15px 14px 15px 65px !important;
  border-radius:18px !important
}
.stats-modern .stat-card::before{width:3px !important}
.stats-modern .stat-icon{
  left:14px !important;top:15px !important;
  width:37px !important;height:37px !important;
  border-radius:10px !important;font-size:18px !important
}
.stats-modern .stat-card strong{font-size:18px !important;margin-bottom:2px !important}
.stats-modern .stat-card small{font-size:12px !important;line-height:1.3 !important}
.info-grid-site{margin-top:18px;gap:12px}
.info-grid-site article,.anuncio-info-grid article,.anuncio-cta{padding:15px}
.info-grid-site p,.anuncio-info-grid p{font-size:13px;line-height:1.45}
.center{max-width:860px;margin-left:auto;margin-right:auto}
.center p{line-height:1.45;margin-top:8px}
.cards{gap:14px}
.card{padding:clamp(18px,2vw,28px);transition:transform .2s,box-shadow .2s}
.card h3{font-size:21px;letter-spacing:-.5px}
.card li{font-size:15px;line-height:1.65}
.card-icon{font-size:32px}
.partner-carousel-area{margin-top:18px !important;grid-template-columns:42px minmax(0,1fr) 42px !important;gap:6px !important}
.partner-arrow{height:40px !important;width:40px !important;font-size:27px !important;box-shadow:none !important}
.partner-carousel{padding:12px 8px !important}
.partner-carousel .partner-track{gap:12px !important}
.partner-carousel .partner{
  flex:0 0 210px !important;width:210px !important;min-width:210px !important;
  min-height:155px !important;padding:14px !important;border-radius:19px !important;
  box-shadow:0 5px 16px rgba(3,37,92,.07) !important
}
.partner-carousel .partner img{max-width:170px !important;max-height:86px !important}
.partner-carousel .partner span{font-size:13px !important;line-height:1.25}
.bau-ads-grid,.anuncio-info-grid{gap:12px}
.bau-ad-card{padding:12px}
.bau-ad-card img,.bau-ad-placeholder{height:clamp(150px,26vh,260px);object-fit:contain}
.anuncio-info-grid{margin-top:12px}
.anuncio-info-grid h3,.anuncio-cta h3{font-size:16px}
.anuncio-cta{margin-top:12px}
.anuncio-cta p{font-size:13px;margin:6px auto 10px}
.trabalhe-grid{grid-template-columns:minmax(0,.95fr) minmax(0,1.05fr);gap:16px}
.work-info,.work-form{padding:18px}
.work-info p,.work-form label,.bau-details,.docs-list li{font-size:13px;line-height:1.4}
.bau-box,.docs-box{margin-top:12px;padding:12px}
.bau-box h3,.docs-box h3,.work-form h3{margin:0 0 9px}
.bau-img{max-height:155px !important;width:100%;object-fit:contain}
.docs-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px 8px}
.docs-list li{padding:8px}
.work-form input:not([type=checkbox]),.work-form select{
  min-height:40px;padding:9px 12px;border-radius:12px
}
.contato-grid{gap:16px}
.contato-card,.mapa-card{padding:18px}
.contact-list{gap:10px}
.contact-list a,.contact-list>div{padding:12px 14px}
.mapa-card iframe{height:clamp(220px,34vh,350px)}
.footer-royal{
  background:rgba(8,51,112,.96) !important;
  padding:10px 0 !important;box-shadow:none !important
}
.footer-royal-grid{min-height:37px !important}
.footer-policy,.footer-copy{font-size:11px !important}
.footer-logo-coopex{height:32px !important;filter:none !important}
.footer-logo-somos{height:27px !important;filter:none !important}
.floating-delivery{box-shadow:0 7px 22px rgba(5,122,82,.17)}
@media (min-width:1100px) and (min-height:690px){
  .hero{padding:15px 0 8px}
  .hero-banner{height:clamp(380px,56vh,600px)}
  .home-reviews{padding:8px 0 12px}
}
@media (max-width:1180px){
  .nav{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;min-height:70px}
  .brand{min-width:0}
  .brand img{height:50px}
  .somos-wrap{position:static;display:flex;transform:none}
  .somos-wrap img{height:37px}
  .links{padding:0;margin:0}
  .links :is(button,a){font-size:12px;padding:8px 7px}
}
@media (max-width:980px){
  .container{width:calc(100% - 34px)}
  .nav{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:9px}
  .brand img{height:48px;max-width:min(50vw,190px)}
  .somos-wrap{display:flex !important;position:static;transform:none}
  .somos-wrap img{height:30px;max-width:85px}
  .menu-btn{display:block;padding:8px 12px}
  .links{
    display:none;position:absolute;top:calc(100% + 5px);left:0;right:0;z-index:30;
    background:rgba(248,252,255,.97);border:1px solid #d9e9fa;
    box-shadow:0 15px 32px rgba(13,50,96,.14);border-radius:18px;
    padding:10px;max-height:75vh;overflow:auto;
    -webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px)
  }
  body.menu-open .links{display:grid;grid-template-columns:1fr 1fr;gap:5px}
  .links :is(button,a){min-height:44px;text-align:center;color:#123e78;font-size:13px;padding:10px;white-space:normal}
  .hero-banner{height:auto;min-height:0;aspect-ratio:auto}
  .hero-copy{min-height:430px;height:auto;width:min(550px,74%);padding:26px}
  .hero-copy h1{font-size:clamp(31px,5vw,45px)}
  .hero-shade{background:linear-gradient(90deg,rgba(245,250,255,.98) 0%,rgba(245,250,255,.82) 56%,rgba(245,250,255,.10) 100%)}
  .two-col,.trabalhe-grid,.contato-grid{grid-template-columns:1fr}
  .info-grid-site{grid-template-columns:1fr 1fr}
  .contact-list{grid-template-columns:repeat(2,minmax(0,1fr))}
  .work-info,.work-form{padding:18px}
}
@media (max-width:640px){
  .container{width:calc(100% - 24px)}
  .nav{min-height:64px;padding:5px 0}
  .brand img{height:40px;max-width:175px}
  .somos-wrap img{height:26px;max-width:70px}
  .menu-btn{font-size:21px}
  .hero{padding:12px 0}
  .hero-banner{border-radius:21px;min-height:0;height:auto}
  .hero-bg{object-position:center}
  .hero-shade{background:linear-gradient(180deg,rgba(244,250,255,.97) 0%,rgba(244,250,255,.90) 55%,rgba(244,250,255,.70) 100%)}
  .hero-copy{width:100%;min-height:0;padding:23px 19px 18px}
  .hero-copy h1{font-size:clamp(29px,8.2vw,40px);line-height:1.07;letter-spacing:-1px}
  .hero-copy p{font-size:14px;line-height:1.48}
  .actions{flex-direction:column}
  .actions .btn{width:100%;min-height:44px}
  .selo-utilidade-box{margin-top:14px !important}
  .selo-utilidade-box img{height:51px !important;width:51px !important}
  .reviews-grid,.reviews-cards,.cards,.two-col,.info-grid-site,.anuncio-info-grid,
  .bau-ads-grid,.trabalhe-grid,.contato-grid,.contact-list{
    grid-template-columns:1fr
  }
  .home-reviews{padding:7px 0 16px}
  .reviews-title,.review-card{padding:14px}
  .review-card{min-height:unset}
  .secao{padding:19px 0 26px}
  .center h2,.two-col h2,.contato h2,.work-info h2{font-size:28px}
  .partner-carousel-area{grid-template-columns:30px minmax(0,1fr) 30px !important}
  .partner-arrow{width:30px !important;height:35px !important;font-size:22px !important}
  .partner-carousel .partner{flex-basis:175px !important;width:175px !important;min-width:175px !important}
  .docs-list{grid-template-columns:1fr}
  .bau-ad-card img,.bau-ad-placeholder{height:190px}
  .floating-delivery{bottom:14px;right:12px}
  .footer-royal-grid{grid-template-columns:1fr !important;gap:10px !important;justify-items:center}
  .footer-copy{white-space:normal !important;text-align:center !important}
}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms !important;scroll-behavior:auto !important;transition-duration:.01ms !important}
}

'''


def render_cf(template_name, **context):
    html = TEMPLATES.get(template_name)
    if html is None:
        abort(500, description=f'Template não encontrado: {template_name}')

    # Uma unica consulta de configuracoes por pagina, sem carregar
    # a mesma tabela duas vezes no context processor.
    if 'cfg' not in context or 'card_cfg' not in context:
        valores = {r['chave']: r['valor'] for r in
                   _rows('SELECT chave, valor FROM site_config')}
        context.setdefault('cfg', {k: valores.get(k, v) for k, v in DEFAULTS.items()})
        context.setdefault('card_cfg', {k: valores.get(k, v) for k, v in CARD_DEFAULTS.items()})

    # Evita embutir ~CSS volumoso em toda resposta HTML.
    # Os templates ja carregam /static/style.css, que possui cache.
    response = make_response(render_template(template_name, **context))
    response.headers['Cache-Control'] = 'private, no-store, no-cache, max-age=0, must-revalidate'
    response.headers['CDN-Cache-Control'] = 'no-store'
    response.headers['Cloudflare-CDN-Cache-Control'] = 'no-store'
    return response

def allowed_file(filename, allowed):
    return bool(filename and '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed)


def _storage_key(row):
    folder = 'privado/' if str(row.get('categoria') or '').lower().startswith('curriculo') else 'publico/'
    return folder + str(row['id']) + '/' + str(row.get('filename') or '')


def salvar_upload(arquivo, prefixo, allowed):
    if not arquivo or not arquivo.filename or not allowed_file(arquivo.filename, allowed):
        return None

    safe = secure_filename(arquivo.filename)
    filename = f'{prefixo}_{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")}_{safe}'
    arquivo.stream.seek(0)
    dados = arquivo.read(5 * 1024 * 1024 + 1) if prefixo != 'card_video' else arquivo.read(10 * 1024 * 1024 + 1)
    limite = 10 * 1024 * 1024 if prefixo == 'card_video' else 5 * 1024 * 1024
    if len(dados) > limite:
        return None
    if not dados:
        return None

    # Validate image signatures without altering transparency or original bytes.
    ext = safe.rsplit('.', 1)[-1].lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        valid = ((ext == 'png' and dados.startswith(b'\x89PNG\r\n\x1a\n')) or
                 (ext in ('jpg', 'jpeg') and dados.startswith(b'\xff\xd8\xff')) or
                 (ext == 'webp' and dados[:4] == b'RIFF' and dados[8:12] == b'WEBP') or
                 (ext == 'gif' and dados[:6] in (b'GIF87a', b'GIF89a')))
        if not valid:
            return None

    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'webp': 'image/webp', 'gif': 'image/gif'}.get(ext, arquivo.mimetype or 'application/octet-stream')
    file_id = _insert(
        '''INSERT INTO file_upload
           (filename, original_filename, mimetype, categoria, tamanho, criado_em)
           VALUES (?, ?, ?, ?, ?, ?)''',
        filename, safe, mime, prefixo, len(dados), agora_utc_iso()
    )
    if not file_id:
        return None

    key = _storage_key({'id': file_id, 'filename': filename, 'categoria': prefixo})
    storage = getattr(_env(), 'FILES', None)
    try:
        if storage is None:
            raise RuntimeError('R2 binding unavailable')
        # Copy bytes into an independent JavaScript buffer before awaiting I/O.
        from pyodide.ffi import to_js
        raw = to_js(dados)
        verified = run_sync(storage.put(key, raw))
        if verified is None or int(verified.size) != len(dados):
            raise RuntimeError('Upload size verification failed')
        return f'db:{file_id}'
    except Exception as exc:
        print(f'R2 upload failed for file {file_id}: {type(exc).__name__}: {exc}')
        if storage is not None:
            try:
                run_sync(storage.delete(key))
            except Exception as cleanup_exc:
                print(f'R2 cleanup failed for file {file_id}: {cleanup_exc}')
                return None
        _db_run('DELETE FROM file_upload WHERE id = ?', file_id)
        return None


def excluir_arquivo_referencia(valor):
    if not valor or not str(valor).startswith('db:'):
        return not bool(valor)
    try:
        file_id = int(str(valor).split(':', 1)[1])
        row = _one('SELECT * FROM file_upload WHERE id = ? LIMIT 1', file_id)
        if row:
            storage = getattr(_env(), 'FILES', None)
            if storage is None:
                raise RuntimeError('R2 binding unavailable')
            key = _storage_key(row)
            run_sync(storage.delete(key))
            if run_sync(storage.head(key)) is not None:
                raise RuntimeError('R2 deletion not confirmed')
        _db_run('DELETE FROM file_chunk WHERE file_id = ?', file_id)
        _db_run('DELETE FROM file_upload WHERE id = ?', file_id)
        return True
    except Exception as exc:
        # Keep metadata for retry rather than orphaning an object.
        print(f'File cleanup failed: {type(exc).__name__}')
        return False


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
    return url_for('static', filename='uploads/' + valor)


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
        _db_run(
            'INSERT OR IGNORE INTO site_config (chave, valor) VALUES (?, ?)',
            chave,
            valor
        )

    # Migração única do acesso administrativo.
    # Garante que hashes antigos do Render/Werkzeug não impeçam o login no Worker.
    admin_seed = get_config('__admin_seed_cloudflare_v4', '')
    if admin_seed != '1':
        usuario = 'coopex'
        senha = 'coopex05289'
        senha_hash = gerar_hash_senha(senha)
        admin = _one('SELECT id FROM admin_user LIMIT 1')
        if admin:
            _db_run(
                'UPDATE admin_user SET usuario = ?, senha_hash = ? WHERE id = ?',
                usuario,
                senha_hash,
                admin['id']
            )
        else:
            _db_run(
                'INSERT INTO admin_user (usuario, senha_hash) VALUES (?, ?)',
                usuario,
                senha_hash
            )
        set_config('__admin_seed_cloudflare_v4', '1')

    if not _one('SELECT id FROM site_access LIMIT 1'):
        _db_run(
            'INSERT INTO site_access (total_acessos, atualizado_em) VALUES (0, ?)',
            agora_utc_iso()
        )

    if not _one('SELECT id FROM partner LIMIT 1'):
        _db_run(
            'INSERT INTO partner (nome, link, ativo, ordem, cliques, criado_em) VALUES (?, ?, 1, 1, 0, ?)',
            'Parceiro COOPEX',
            '#',
            agora_utc_iso()
        )
        _db_run(
            'INSERT INTO partner (nome, link, ativo, ordem, cliques, criado_em) VALUES (?, ?, 1, 2, 0, ?)',
            'Solicite sua entrega',
            get_config('link_solicitar_entrega', DEFAULTS['link_solicitar_entrega']),
            agora_utc_iso()
        )

    if not _one('SELECT id FROM review LIMIT 1'):
        reviews = [
            ('Cliente COOPEX', 'Restaurante parceiro',
             'Atendimento organizado, entregadores bem apresentados e suporte rápido quando precisamos.',
             'há 2 semanas', 1),
            ('Empresa parceira', 'Delivery local',
             'A operação ficou mais segura com a COOPEX. Sempre que precisamos, conseguimos falar com a equipe.',
             'há 1 mês', 2),
            ('Estabelecimento cliente', 'Farmácia',
             'Equipe responsável, boa comunicação e entregadores fardados. Recomendo para operação fixa.',
             'há 2 meses', 3),
        ]
        for nome, empresa, comentario, data_avaliacao, ordem in reviews:
            _db_run(
                """INSERT INTO review
                   (nome, empresa, comentario, nota, data_avaliacao, link, ativo, ordem, criado_em)
                   VALUES (?, ?, ?, 5, ?, '#', 1, ?, ?)""",
                nome, empresa, comentario, data_avaliacao, ordem, agora_utc_iso()
            )

    if not _one('SELECT id FROM card_link LIMIT 1'):
        links = [
            ('Solicitar entrega', 'Atendimento COOPEX',
             get_config('link_solicitar_entrega', DEFAULTS['link_solicitar_entrega']), 1),
            ('Instagram', 'Acompanhe a COOPEX',
             'https://instagram.com/coopex.entregas', 2),
            ('Contato', 'Fale conosco',
             'https://wa.me/5584981110706', 3),
        ]
        for titulo, subtitulo, url, ordem in links:
            _db_run(
                """INSERT INTO card_link
                   (titulo, subtitulo, url, ativo, ordem, cliques, criado_em)
                   VALUES (?, ?, ?, 1, ?, 0, ?)""",
                titulo, subtitulo, url, ordem, agora_utc_iso()
            )


@app.before_request
def _redirect_public_technical_host():
    # Keep technical Worker URL from competing with the official site in search.
    # Limit to public read-only pages; do not redirect APIs or admin sessions.
    from urllib.parse import quote
    host = request.host.split(':', 1)[0].lower()
    public = ('/', '/inicio', '/parceiros', '/sobre', '/servicos', '/anuncie', '/trabalhe', '/contato', '/instagram', '/card-instagram', '/politica-de-privacidade', '/sitemap.xml', '/robots.txt', '/favicon.svg', '/favicon.png', '/favicon.ico')
    if host in ('coopex-site.thalesalcantara88.workers.dev', 'coopexentregas.com.br') and request.method in ('GET', 'HEAD') and (request.path in public or request.path.strip('/') in SEO_SERVICES):
        path = {'/inicio':'/', '/parceiros':'/', '/instagram':'/card-instagram'}.get(request.path, request.path)
        target = 'https://www.coopexentregas.com.br' + quote(path, safe='/')
        if request.query_string:
            target += '?' + request.query_string.decode('ascii', errors='ignore')
        return redirect(target, code=301)
    return None


@app.before_request
def _bootstrap():
    # D1 ja foi inicializado e restaurado. Nao executar dezenas de
    # INSERT OR IGNORE em todas as requisicoes: isso aumenta a latencia
    # e pode exceder a CPU do Cloudflare Python Workers.
    return None


@app.context_processor
def inject_global():
    # Somente as paginas que usam cfg/card_cfg devem consultar o D1.
    # Evita duas consultas extras em cada arquivo e em cada renderizacao.
    return {
        'arquivo_url': arquivo_url,
        'formatar_data_hora_br': formatar_data_hora_br,
    }


@app.route('/static/<path:filename>', endpoint='static')
def static_asset(filename):
    if filename == 'img/coopex-oficial-v2.webp':
        import base64
        return Response(base64.b64decode('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'), mimetype='image/webp', headers={'Cache-Control': 'no-cache, must-revalidate'})

    # As logos fixas pertencem ao repositorio publico original.
    # O binding ASSETS nem sempre as serviu apos a migracao.
    if filename in (
        'img/coopex-nome-entregas.png',
        'img/coopex-oficial-v2.webp',
        'img/coopex-oficial-3d.webp',
        'img/coopex-transparente.png',
        'img/somos-coop.png',
        'img/somos-coop-v2.png',
        'selo.png',
    ):
        return redirect('https://raw.githubusercontent.com/thalesalcantara/coopex-site/main/static/' + filename, code=302)
    # O CSS principal é servido diretamente pelo Worker para não depender
    # do binding ASSETS. O site e o painel administrativo usam este arquivo.
    if filename == 'style.css':
        return Response(
            SITE_CSS,
            mimetype='text/css',
            headers={'Cache-Control': 'no-cache, must-revalidate'}
        )
    if filename == 'site.js':
        return Response("const paginasCOOPEX = {\"inicio\":\"/\",\"sobre\":\"/sobre\",\"servicos\":\"/servicos\",\"anuncie\":\"/anuncie\",\"trabalhe\":\"/trabalhe\",\"contato\":\"/contato\"};\nfunction paginaAtual(){\n  const path = location.pathname.replace(/\\/+$/, '') || '/';\n  const old = location.hash.slice(1);\n  if(path === '/' && Object.hasOwn(paginasCOOPEX,old)) return old;\n  return Object.keys(paginasCOOPEX).find(id=>paginasCOOPEX[id]===path)||'inicio';\n}\nfunction mostrarPagina(id,modo='push'){\n  if(!Object.hasOwn(paginasCOOPEX,id)) id='inicio';\n  document.querySelectorAll('.page-section').forEach(sec=>sec.classList.toggle('active',sec.id===id));\n  document.querySelectorAll('.tab-link').forEach(btn=>btn.classList.toggle('active',btn.dataset.page===id));\n  const avaliacoes=document.getElementById('avaliacoesGoogle');\n  if(avaliacoes) avaliacoes.style.display=id==='inicio'?'block':'none';\n  document.body.classList.remove('menu-open');\n  const path=paginasCOOPEX[id]+location.search;\n  if(location.pathname+location.search+location.hash!==path && modo!=='none'){\n    if(modo==='replace')history.replaceState({pagina:id},'',path);\n    else history.pushState({pagina:id},'',path);\n  }\n  const canonical=document.querySelector('link[rel=\"canonical\"]');\n  if(canonical)canonical.href='https://www.coopexentregas.com.br'+paginasCOOPEX[id];\n  const labels={inicio:'Entregas em Natal/RN',sobre:'Sobre',servicos:'Serviços',anuncie:'Divulgue sua marca',trabalhe:'Trabalhe conosco',contato:'Contato'};\n  document.title='COOPEX Entregas | '+labels[id];\n  window.scrollTo(0,0);\n}\ndocument.addEventListener('DOMContentLoaded',()=>{\n  document.querySelectorAll('.tab-link').forEach(btn=>btn.addEventListener('click',function(e){\n    if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;\n    e.preventDefault();mostrarPagina(this.dataset.page||'inicio');\n  }));\n  mostrarPagina(paginaAtual(),'replace');\n});\nwindow.addEventListener('popstate',()=>mostrarPagina(paginaAtual(),'replace'));\nwindow.addEventListener('hashchange',()=>{if(location.hash)mostrarPagina(paginaAtual(),'replace')});\nfunction abrirSolicitacao(){\n  const modal = document.getElementById('modalSolicitacao');\n  const iframe = document.getElementById('iframeSolicitacao');\n\n  if (!modal || !iframe) return;\n\n  modal.classList.add('aberto');\n  modal.setAttribute('aria-hidden', 'false');\n\n  if (!iframe.src) {\n    iframe.src = iframe.dataset.src;\n  }\n}\n\nfunction fecharSolicitacao(){\n  const modal = document.getElementById('modalSolicitacao');\n\n  if (!modal) return;\n\n  modal.classList.remove('aberto');\n  modal.setAttribute('aria-hidden', 'true');\n}\n\ndocument.addEventListener('keydown', function(e){\n  if (e.key === 'Escape') {\n    fecharSolicitacao();\n  }\n});\n", mimetype='application/javascript',
                        headers={'Cache-Control': 'no-store'})
    return _asset_response(filename)


@app.route('/arquivo/<int:file_id>')
def arquivo_db(file_id):
    arquivo = _one('SELECT * FROM file_upload WHERE id = ? LIMIT 1', file_id)
    if not arquivo:
        abort(404)

    # Recuperação Render -> Cloudflare: arquivos antigos armazenados no R2.
    # Nunca tornar currículos públicos, mesmo que conheçam o ID do arquivo.
    if str(arquivo.get('categoria') or '').lower().startswith('curriculo') and not login_required():
        abort(403)
    try:
        storage = getattr(_env(), 'FILES', None)
        if storage is not None:
            key = ('privado/' if str(arquivo.get('categoria') or '').lower().startswith('curriculo')
                   else 'publico/') + str(file_id) + '/' + str(arquivo.get('filename') or '')
            obj = run_sync(storage.get(key))
            if obj is not None:
                blob = run_sync(obj.arrayBuffer())
                from js import Uint8Array
                raw = Uint8Array.new(blob).to_bytes()
                if len(raw) != int(arquivo.get('tamanho') or len(raw)):
                    raise RuntimeError('Stored R2 file size mismatch')
                return send_file(BytesIO(raw),
                    mimetype=arquivo.get('mimetype') or 'application/octet-stream',
                    download_name=arquivo.get('original_filename') or arquivo.get('filename'),
                    max_age=86400 if not str(arquivo.get('categoria') or '').lower().startswith('curriculo') else 0)
    except Exception:
        # Compatibilidade com arquivos antigos que residem nos chunks do D1.
        pass

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

    raw = b''.join(partes)
    if not raw or len(raw) != int(arquivo.get('tamanho') or len(raw)):
        abort(404)
    return send_file(
        BytesIO(raw),
        mimetype=arquivo.get('mimetype') or 'application/octet-stream',
        download_name=arquivo.get('original_filename') or arquivo.get('filename'),
        max_age=0 if str(arquivo.get('categoria') or '').lower().startswith('curriculo') else 86400
    )



# Public service pages: distinct useful content, server-rendered, no extra D1 queries.
import json as _seo_json
SEO_SERVICES = {p['slug']:p for p in _seo_json.loads("[{\"slug\":\"motoboy-natal\",\"title\":\"Motoboy em Natal/RN\",\"description\":\"Contrate motoboy para entregas comerciais, documentos e encomendas em Natal e Grande Natal.\",\"body\":\"Precisa de um motoboy para uma entrega pontual? A COOPEX organiza a coleta e o destino conforme a necessidade do cliente. Informe os endereços, o tipo de volume e o horário desejado para consultar disponibilidade e valor.\",\"items\":[\"Documentos, pequenas encomendas e compras\",\"Atendimento a empresas e pessoas físicas\",\"Solicite uma entrega pelo canal oficial\"]},{\"slug\":\"motofrete-natal\",\"title\":\"Motofrete em Natal/RN\",\"description\":\"Serviço de motofrete da COOPEX para empresas e pessoas físicas, com cooperados identificados.\",\"body\":\"O motofrete é indicado para transportar pequenos volumes compatíveis com a motocicleta. A COOPEX organiza profissionais cooperados e fardados para atender demandas comerciais e particulares. Consulte as condições de transporte antes de solicitar a coleta.\",\"items\":[\"Coletas e entregas comerciais\",\"Transporte de volumes compatíveis com o baú\",\"Atendimento organizado por região\"]},{\"slug\":\"delivery-natal\",\"title\":\"Delivery para empresas em Natal\",\"description\":\"Soluções de entrega para restaurantes, lanchonetes, farmácias e estabelecimentos comerciais.\",\"body\":\"Estabelecimentos que recebem pedidos próprios podem contratar apoio de entregadores para o despacho. A COOPEX oferece modalidades avulsas e fixas conforme a demanda, os horários e as condições do contrato. O serviço é de transporte, não de venda de refeições.\",\"items\":[\"Delivery de restaurantes e lanchonetes\",\"Entregas de pedidos de farmácias\",\"Planejamento de horários e demanda\"]},{\"slug\":\"entregas-rapidas\",\"title\":\"Entregas rápidas e avulsas em Natal\",\"description\":\"Solicite coleta e entrega de documentos, encomendas e compras na Grande Natal.\",\"body\":\"Para uma entrega avulsa, informe o local de retirada, o destino, a natureza do item e a urgência. A equipe orienta sobre o valor, a disponibilidade e as condições aplicáveis. O prazo depende da distância, do trânsito e da operação.\",\"items\":[\"Coleta e entrega de encomendas\",\"Compras e pequenos volumes\",\"Consulta de preço conforme o destino\"]},{\"slug\":\"motoboy-fixo\",\"title\":\"Motoboy fixo para empresas em Natal\",\"description\":\"Contratação de entregadores para operações recorrentes de delivery e logística.\",\"body\":\"Empresas com fluxo recorrente de pedidos podem consultar a COOPEX para organizar uma operação de entregas com profissionais escalados. O dimensionamento considera horários, volume, região e características da atividade.\",\"items\":[\"Escalas para estabelecimentos\",\"Operação recorrente de entregas\",\"Proposta de acordo com a demanda\"]},{\"slug\":\"logistica-empresarial\",\"title\":\"Logística empresarial e malotes em Natal\",\"description\":\"Coletas programadas, documentos, malotes e apoio à distribuição comercial.\",\"body\":\"A COOPEX auxilia empresas que precisam organizar deslocamentos de pequenos volumes entre unidades, clientes e fornecedores. A operação pode incluir coletas recorrentes ou avulsas, conforme a necessidade e as condições contratadas.\",\"items\":[\"Coleta e distribuição entre unidades\",\"Documentos e malotes\",\"Rotas e horários combinados\"]},{\"slug\":\"entregas-hospitalares\",\"title\":\"Coletas hospitalares e laboratoriais em Natal\",\"description\":\"Consulte soluções de transporte para hospitais, clínicas e laboratórios.\",\"body\":\"Operações de saúde exigem atenção aos requisitos de acondicionamento, documentação e horário. A COOPEX avalia as necessidades de cada contrato e as condições específicas do material. A contratação depende da compatibilidade com os requisitos técnicos e legais aplicáveis.\",\"items\":[\"Coletas programadas\",\"Atendimento a clínicas e laboratórios\",\"Condições de transporte definidas por contrato\"]},{\"slug\":\"entrega-documentos\",\"title\":\"Entrega de documentos e encomendas em Natal\",\"description\":\"Serviços de coleta e entrega de documentos, malotes, cartórios e Correios.\",\"body\":\"A COOPEX atende demandas de deslocamento de documentos e pequenos volumes entre empresas e destinatários. Informe se a entrega envolve protocolo, assinatura ou outra exigência de recebimento para que a equipe avalie o atendimento.\",\"items\":[\"Documentos e malotes empresariais\",\"Deslocamentos a cartórios e Correios\",\"Coleta em endereço combinado\"]},{\"slug\":\"area-de-atendimento\",\"title\":\"Área de atendimento da COOPEX na Grande Natal\",\"description\":\"Conheça os municípios atendidos pela cooperativa de entregas do Rio Grande do Norte.\",\"body\":\"A COOPEX atua em Natal e atende demandas na Grande Natal. Consulte a disponibilidade para seu endereço de retirada e destino, pois valores e prazos dependem da região, do horário e da modalidade de serviço.\",\"items\":[\"Natal e Parnamirim\",\"Macaíba e São Gonçalo do Amarante\",\"Extremoz e Nísia Floresta\"]}]")}
_SEO_BASE = 'https://www.coopexentregas.com.br'
_SEO_SERVICE_TEMPLATE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ p.title }} | COOPEX Entregas</title><meta name="description" content="{{ p.description }}"><link rel="canonical" href="{{ canonical }}"><link rel="icon" type="image/png" sizes="96x96" href="/favicon.png">
<meta property="og:title" content="{{ p.title }} | COOPEX"><meta property="og:description" content="{{ p.description }}"><meta property="og:url" content="{{ canonical }}"><meta property="og:site_name" content="COOPEX Entregas">
<script type="application/ld+json">{{ structured|tojson }}</script>
<style> *{box-sizing:border-box} body{margin:0;font:16px/1.65 system-ui,sans-serif;background:linear-gradient(145deg,#f3f9ff,#cce6ff);color:#173b60;min-height:100vh} header,main,footer{max-width:1000px;margin:auto;padding:20px} header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px} header img{width:220px;max-width:55vw;height:auto} nav{display:flex;gap:16px;flex-wrap:wrap} a{color:#064d9e} article,section{background:linear-gradient(145deg,#fffdfd,#e4f2ffbb);border:1px solid white;border-radius:24px;padding:clamp(20px,5vw,46px);box-shadow:0 12px 36px #143b6920,inset 0 2px 2px white;margin-bottom:20px} h1{font-size:clamp(28px,5vw,46px);line-height:1.12;letter-spacing:-.03em;margin:.3em 0;color:#103c72} h2{line-height:1.3;font-size:23px} .cta{display:inline-block;background:#0959b5;color:white;padding:12px 22px;border-radius:14px;text-decoration:none;font-weight:700;margin:8px 8px 0 0} .related{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px} .related a{display:block;padding:12px;background:#fff9;border:1px solid white;border-radius:12px} footer{font-size:14px} </style></head>
<body><header><a href="/"><img src="/static/img/coopex-oficial-v2.webp" alt="COOPEX Entregas"></a><nav aria-label="Navegação"><a href="/">Início</a><a href="/sobre">Sobre</a><a href="/servicos">Serviços</a><a href="/contato">Contato</a></nav></header>
<main><article><p>COOPEX • Desde 2002 • Natal/RN</p><h1>{{ p.title }}</h1><p><strong>{{ p.description }}</strong></p><p>{{ p.body }}</p><h2>Como podemos atender</h2><ul>{% for item in p['items'] %}<li>{{ item }}</li>{% endfor %}</ul><a class="cta" href="/contato">Solicitar atendimento</a><a class="cta" href="/servicos">Conhecer os serviços</a></article><section><h2>Outras soluções da COOPEX</h2><div class="related">{% for item in related %}<a href="/{{ item.slug }}">{{ item.title }}</a>{% endfor %}</div></section></main><footer>COOPEX Entregas – Cooperativa de Trabalhadores de Entregas do Rio Grande do Norte • <a href="/politica-de-privacidade">Privacidade</a></footer></body></html>"""

def _seo_service_page(slug):
    p = SEO_SERVICES[slug]
    canonical = _SEO_BASE + '/' + slug
    structured = {'@context':'https://schema.org','@type':'Service','name':p['title'],'description':p['description'],'url':canonical,'provider':{'@type':'Organization','name':'COOPEX Entregas','url':_SEO_BASE+'/'},'areaServed':{'@type':'City','name':'Natal'}}
    return render_template_string(_SEO_SERVICE_TEMPLATE,p=p,canonical=canonical,structured=structured,related=[v for k,v in SEO_SERVICES.items() if k!=slug])

for _slug in SEO_SERVICES:
    app.add_url_rule('/'+_slug, endpoint='seo_service_'+_slug.replace('-','_'), view_func=lambda slug=_slug: _seo_service_page(slug), methods=['GET'])

# Discoverable links in the existing services section, no JavaScript dependency.
_seo_links = '<div class="seo-service-links" style="display:flex;flex-wrap:wrap;gap:8px;margin:12px 0"><strong style="width:100%">Conheça nossas soluções de entrega</strong>'+''.join('<a style="padding:7px 12px;border-radius:12px;background:#e4f1ff;color:#164d89" href="/'+p['slug']+'">'+p['title']+'</a>' for p in SEO_SERVICES.values())+'</div>'
# Put links inside the existing service section without changing the other sections.
_seo_index = TEMPLATES['index.html']
_seo_start = _seo_re.search(r'<section\b[^>]*\bid=["\']servicos["\'][^>]*>',_seo_index)
if _seo_start:
    _seo_end = _seo_index.find('</section>',_seo_start.end())
    if _seo_end >= 0:
        TEMPLATES['index.html'] = _seo_index[:_seo_end]+_seo_links+_seo_index[_seo_end:]


@app.route('/sitemap.xml')
def sitemap_publico():
    base = 'https://www.coopexentregas.com.br'
    paths = ('/', '/sobre', '/servicos', '/anuncie', '/trabalhe', '/contato', '/card-instagram', '/politica-de-privacidade') + tuple('/'+slug for slug in SEO_SERVICES)
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += ''.join('<url><loc>' + base + path + '</loc></url>\n' for path in paths)
    xml += '</urlset>'
    return Response(xml, mimetype='application/xml', headers={'Cache-Control': 'public, max-age=3600'})


# IndexNow ownership proof: public UTF-8 key, not an authentication secret.
@app.route('/cf9d9ecc3dae4f4088b07f305647dafa.txt', methods=['GET', 'HEAD'])
def indexnow_ownership():
    return Response('cf9d9ecc3dae4f4088b07f305647dafa', content_type='text/plain; charset=utf-8', headers={'Cache-Control':'public, max-age=3600'})


@app.route('/robots.txt')
def robots_publico():
    return Response('User-agent: *\nAllow: /\nDisallow: /admin-site\nDisallow: /admin-coopex\nDisallow: /card-link/\nDisallow: /parceiro/\nDisallow: /api/\nSitemap: https://www.coopexentregas.com.br/sitemap.xml\n', mimetype='text/plain', headers={'Cache-Control': 'public, max-age=3600'})


@app.route('/')
@app.route('/sobre')
@app.route('/servicos')
@app.route('/anuncie')
@app.route('/trabalhe')
@app.route('/contato')
def index():
    pagina = request.path.strip('/') or 'inicio'
    if not session.get('site_visitou'):
        _db_run('UPDATE site_access SET total_acessos = COALESCE(total_acessos, 0) + 1, atualizado_em = ? WHERE id = (SELECT id FROM site_access LIMIT 1)', agora_utc_iso())
        session['site_visitou'] = True

    parceiros = _objs(_rows('SELECT * FROM partner WHERE ativo = 1 ORDER BY ordem ASC, nome ASC'))
    avaliacoes = _objs(_rows('SELECT * FROM review WHERE ativo = 1 ORDER BY ordem ASC, criado_em DESC'))
    return render_cf('index.html', parceiros=parceiros, avaliacoes=avaliacoes, pagina=pagina, canonical_path=request.path)


@app.route('/inicio')
@app.route('/parceiros')
def antigo_inicio():
    return redirect('/', code=301)


@app.route('/anunciar-marca')
def anunciar_marca():
    import re
    numero = re.sub(r'[^0-9]', '', str(get_config('whatsapp', DEFAULTS.get('whatsapp', ''))))
    if not numero:
        return redirect('/anuncie')
    if len(numero) in (10, 11):
        numero = '55' + numero
    _db_run("""INSERT INTO site_config (chave, valor) VALUES ('__cliques_anunciar', '1')
        ON CONFLICT(chave) DO UPDATE SET valor=CAST(COALESCE(CAST(site_config.valor AS INTEGER),0)+1 AS TEXT)""")
    resposta = redirect('https://wa.me/' + numero)
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta


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
        return redirect('/trabalhe')

    try:
        nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Data de nascimento inválida.', 'erro')
        return redirect('/trabalhe')

    idade = calcular_idade(nascimento)
    if idade < 21:
        flash('O cadastro só pode ser enviado por candidatos com 21 anos ou mais.', 'erro')
        return redirect('/trabalhe')

    if not atividade:
        flash('Para enviar, marque que possui atividade remunerada na CNH.', 'erro')
        return redirect('/trabalhe')

    import base64
    import calendar
    cpf = _seo_re.sub(r'\D', '', request.form.get('cpf',''))
    telefone = _seo_re.sub(r'\D', '', request.form.get('telefone',''))
    def digito(base):
        resto = sum(int(v)*p for v,p in zip(base, range(len(base)+1,1,-1))) % 11
        return str(0 if resto < 2 else 11-resto)
    if (len(cpf)!=11 or len(set(cpf))==1 or cpf[9]!=digito(cpf[:9])
            or cpf[10]!=digito(cpf[:10]) or len(telefone) not in (10,11)
            or not _site_valid_email(email) or len(nome)>120 or len(escolaridade)>100):
        flash('Confira CPF, telefone e demais dados do cadastro.', 'erro')
        return redirect('/trabalhe')
    filename = secure_filename(arquivo.filename or '') if arquivo else ''
    if not filename or '.' not in filename or filename.rsplit('.',1)[1].lower() not in ALLOWED_CURRICULO_EXTENSIONS:
        flash('Envie um currículo em PDF, DOC, DOCX ou imagem.', 'erro')
        return redirect('/trabalhe')
    data = arquivo.read(4*1024*1024+1)
    if not data or len(data)>4*1024*1024:
        flash('O currículo deve ter até 4 MB.', 'erro')
        return redirect('/trabalhe')
    secret = getattr(_env(),'SITE_CPF_HASH_KEY',None)
    if not secret or not getattr(_env(),'RESEND_API_KEY',None) or not getattr(_env(),'SITE_MAIL_FROM',None):
        flash('Envio temporariamente indisponível. Tente novamente mais tarde.', 'erro')
        return redirect('/trabalhe')
    fingerprint = hmac.new(str(secret).encode(),cpf.encode(),hashlib.sha256).hexdigest()
    now = datetime.now(timezone.utc)
    month = now.month+6
    year = now.year+(month-1)//12
    month = (month-1)%12+1
    next_date = now.replace(year=year,month=month,day=min(now.day,calendar.monthrange(year,month)[1]))
    token = secrets.token_hex(16)
    try:
        _db_run("""CREATE TABLE IF NOT EXISTS candidatura_envio (
            cpf_hash TEXT PRIMARY KEY, proximo_envio TEXT NOT NULL,
            reserva_ate TEXT NOT NULL, token TEXT NOT NULL)""")
        result = _db_run("""INSERT INTO candidatura_envio(cpf_hash,proximo_envio,reserva_ate,token)
            VALUES(?,?,?,?) ON CONFLICT(cpf_hash) DO UPDATE SET
            reserva_ate=excluded.reserva_ate,token=excluded.token
            WHERE candidatura_envio.proximo_envio<=? AND candidatura_envio.reserva_ate<=?""",
            fingerprint,now.isoformat(),(now+timedelta(minutes=15)).isoformat(),token,now.isoformat(),now.isoformat())
        row = _one('SELECT * FROM candidatura_envio WHERE cpf_hash=?',fingerprint)
        if not row or row['token']!=token:
            when = row['proximo_envio'] if row else now.isoformat()
            if when>now.isoformat():
                date_text=datetime.fromisoformat(when).strftime('%d/%m/%Y')
                flash('Você já possui candidatura cadastrada. Próximo envio permitido: '+date_text+'.', 'erro')
            else:
                flash('Já existe um envio em processamento. Aguarde antes de tentar novamente.', 'erro')
            return redirect('/trabalhe')
        body = (f'Nome: {nome}\nCPF: {cpf}\nTelefone: {telefone}\nE-mail: {email}\n'
                f'Nascimento: {nascimento.strftime("%d/%m/%Y")}\nIdade: {idade}\n'
                f'Escolaridade: {escolaridade}\nAtividade remunerada na CNH: Sim\n'
                f'Data do cadastro: {now.strftime("%d/%m/%Y %H:%M")} UTC')
        _site_send_email('Candidato à vaga de entregador — '+nome,body,email,
            {'filename':filename,'content':base64.b64encode(data).decode('ascii')})
        _db_run('UPDATE candidatura_envio SET proximo_envio=?,reserva_ate=? WHERE cpf_hash=? AND token=?',
                next_date.isoformat(),now.isoformat(),fingerprint,token)
    except Exception:
        flash('Não foi possível confirmar o envio. Aguarde 15 minutos antes de tentar novamente.', 'erro')
        return redirect('/trabalhe')
    flash('Currículo enviado com sucesso! Não envie novamente. Você poderá renovar sua candidatura em '+next_date.strftime('%d/%m/%Y')+'. Entraremos em contato caso surja uma oportunidade.', 'ok')
    return redirect('/trabalhe')


@app.route('/politica-de-privacidade')
def politica_privacidade():
    return render_cf('politica_privacidade.html')


@app.post('/admin-site/sso')
def admin_site_sso():
    """Validação local da autorização assinada pelo Financeiro, sem HTTP externo."""
    import base64
    import hashlib
    import hmac
    import json
    import re
    import time
    token = request.form.get('autorizacao', '')
    def negar():
        response = make_response(render_template_string('<h2>Autorização inválida ou expirada</h2><p>Volte ao Financeiro e clique novamente em Site.</p><a href="https://www.financeiro.coopexentregas.com.br/admin/site/entrar">Tentar novamente</a>'), 403)
        response.headers['Cache-Control'] = 'no-store'
        return response
    try:
        secret = str(getattr(_env(), 'COOPEX_SITE_SSO_SIGN_KEY', '') or '')
        if len(secret)<64 or len(token)>2048:
            return negar()
        body, signature = token.split('.')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',body) or not re.fullmatch(r'[0-9a-f]{64}',signature):
            return negar()
        expected=hmac.new(secret.encode(),b'coopex-site-sso-v2:'+body.encode('ascii'),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,signature):
            return negar()
        dados=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        now=int(time.time())
        if (dados.get('iss')!='coopex-financeiro' or dados.get('aud')!='coopex-site-admin'
            or dados.get('destino') not in ('painel','card') or dados.get('master') is not True
            or not isinstance(dados.get('uid'),int) or dados['uid']<=0
            or not isinstance(dados.get('iat'),int) or not isinstance(dados.get('exp'),int)
            or not dados['iat']-5<=now<dados['exp'] or not 0<dados['exp']-dados['iat']<=90
            or not re.fullmatch(r'[0-9a-f]{64}',str(dados.get('jti','')))):
            return negar()
        # Uso único atômico no D1, inclusive entre instâncias do Worker.
        _db_run('CREATE TABLE IF NOT EXISTS site_sso_usados (jti TEXT PRIMARY KEY, exp INTEGER NOT NULL)')
        result=_db_run('INSERT OR IGNORE INTO site_sso_usados(jti,exp) VALUES (?,?)',dados['jti'],dados['exp'])
        meta=_to_py(result.meta) or {}
        if int(meta.get('changes',0))!=1:
            return negar()
        _db_run('DELETE FROM site_sso_usados WHERE exp < ?',now-120)
    except Exception as exc:
        print('SSO v2 site:',type(exc).__name__)
        return negar()
    session.clear()
    session['site_admin_logado']=True
    session['site_admin_usuario']=str(dados.get('usuario') or 'Financeiro')[:100]
    response=redirect('/admin-site/painel' if dados['destino']=='painel' else '/admin-site/card',code=303)
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    return response


@app.route('/admin-coopex', methods=['GET', 'POST'])
@app.route('/admin-site', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '')

        # Acesso de recuperação independente do D1: se essas credenciais forem
        # usadas, entra imediatamente e depois tenta sincronizar o hash no banco.
        if usuario == 'coopex' and senha == 'coopex05289':
            session['site_admin_logado'] = True
            session['site_admin_usuario'] = usuario
            try:
                novo_hash = gerar_hash_senha(senha)
                atual = _one('SELECT id FROM admin_user WHERE usuario = ? LIMIT 1', usuario)
                if atual:
                    _db_run('UPDATE admin_user SET senha_hash = ? WHERE id = ?', novo_hash, atual['id'])
                else:
                    _db_run('INSERT INTO admin_user (usuario, senha_hash) VALUES (?, ?)', usuario, novo_hash)
            except Exception:
                pass
            return redirect(url_for('admin_dashboard'))

        # Demais usuários continuam sendo validados normalmente no D1.
        try:
            admin = _one('SELECT * FROM admin_user WHERE usuario = ? LIMIT 1', usuario)
        except Exception:
            admin = None

        if admin and verificar_senha(admin.get('senha_hash', ''), senha):
            session['site_admin_logado'] = True
            session['site_admin_usuario'] = usuario
            return redirect(url_for('admin_dashboard'))

        flash('Usuário ou senha inválidos.', 'erro')

    return render_template_string("""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin COOPEX</title>
  <style>
    :root{
      --azul:#0047b8;
      --azul-royal:#0057d9;
      --azul-escuro:#062a59;
      --verde:#00b86b;
      --verde-escuro:#008f53;
      --branco:#ffffff;
      --cinza:#f4f8fd;
      --texto:#132238;
      --muted:#64748b;
      --borda:#dbe5f1;
      --sombra:0 18px 45px rgba(3,37,92,.14);
    }
    *{box-sizing:border-box}
    html{scroll-behavior:smooth}
    body{margin:0;font-family:Arial,Helvetica,sans-serif;color:var(--texto);background:#eaf6ff;min-height:100vh}
    a{text-decoration:none;color:inherit}
    button{font-family:inherit}
    .flash{padding:12px 14px;border-radius:14px;margin-bottom:12px;font-weight:800}
    .flash.erro{background:#fff0f0;color:#a00000;border:1px solid #ffcaca}
    .admin-bg{background:linear-gradient(135deg,#e8f2ff,#fff)}
    .login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
    .login-card{width:min(420px,94vw);background:#fff;border:1px solid var(--borda);border-radius:28px;padding:30px;box-shadow:var(--sombra)}
    .login-card img{height:110px;width:auto;object-fit:contain;display:block;margin:0 auto 10px}
    .login-card h1{text-align:center;color:var(--azul-escuro)}
    .login-card p{text-align:center;color:var(--muted)}
    .login-card label{font-weight:800;color:#334155}
    .login-card input{width:100%;border:1px solid #cdd9ea;border-radius:14px;padding:13px;margin:7px 0 15px}
    .btn{border:0;border-radius:999px;padding:13px 20px;font-weight:900;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px}
    .btn.primary{background:linear-gradient(135deg,var(--verde),#00c777);color:#fff;box-shadow:0 10px 24px rgba(0,169,92,.25)}
    .btn.full{width:100%}
    .voltar{display:block;text-align:center;margin-top:14px;color:var(--azul);font-weight:800}
  </style>
</head>
<body class="admin-bg">
  <main class="login-wrap">
    <form class="login-card" method="post">
      <img src="data:image/png;base64,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" alt="COOPEX">
      <h1>Admin COOPEX</h1>
      <p>Acesso administrativo para alterar as informações do site.</p>
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% for cat, msg in messages %}<div class="flash {{ cat }}">{{ msg }}</div>{% endfor %}
      {% endwith %}
      <label>Usuário</label>
      <input name="usuario" required autocomplete="username">
      <label>Senha</label>
      <input name="senha" type="password" required autocomplete="current-password">
      <button class="btn primary full" type="submit">Entrar</button>
      <a class="voltar" href="{{ url_for('index') }}">Voltar para o site</a>
    </form>
  </main>
</body>
</html>""")

@app.route('/admin-coopex/sair')
@app.route('/admin-site/sair')
def admin_logout():
    session.clear()
    if request.args.get('financeiro') == '1':
        return redirect('https://www.financeiro.coopexentregas.com.br/logout')
    return redirect(url_for('index'))


@app.route('/admin-coopex/painel')
@app.route('/admin-site/painel')
def admin_dashboard():
    if not login_required():
        return redirect(url_for('admin_login'))

    parceiros = _objs(_rows('SELECT * FROM partner ORDER BY criado_em DESC, id DESC'))
    avaliacoes = _objs(_rows('SELECT * FROM review ORDER BY ordem ASC, criado_em DESC'))
    candidatos = _objs(_rows('SELECT * FROM candidato ORDER BY criado_em DESC LIMIT 100'))
    contador = _one('SELECT total_acessos FROM site_access LIMIT 1')
    total_acessos_site = int(contador['total_acessos'] or 0) if contador else 0
    totais = _one("""SELECT (SELECT COALESCE(SUM(cliques),0) FROM partner) AS anuncios,
        (SELECT COUNT(*) FROM candidato) AS curriculos,
        (SELECT valor FROM site_config WHERE chave='__cliques_anunciar') AS interesse""") or {}
    total_anuncios = int(totais.get('anuncios') or 0)
    total_curriculos = int(totais.get('curriculos') or 0)
    total_interesse = int(totais.get('interesse') or 0)

    return render_cf(
        'admin_dashboard.html',
        parceiros=parceiros,
        avaliacoes=avaliacoes,
        candidatos=candidatos,
        configs=config_dict(),
        total_acessos_site=total_acessos_site,
        total_anuncios=total_anuncios,
        total_curriculos=total_curriculos,
        total_interesse=total_interesse
    )


@app.route('/admin-coopex/candidatos/<int:candidato_id>/excluir', methods=['POST'])
@app.route('/admin-site/candidatos/<int:candidato_id>/excluir', methods=['POST'])
def candidato_excluir(candidato_id):
    if not login_required():
        return redirect(url_for('admin_login'))
    candidato = _one('SELECT * FROM candidato WHERE id = ? LIMIT 1', candidato_id)
    if not candidato:
        abort(404)
    if not excluir_arquivo_referencia(candidato.get('curriculo')):
        flash('Não foi possível confirmar a exclusão do currículo. O cadastro foi mantido para permitir nova tentativa.', 'erro')
        return redirect(url_for('admin_dashboard'))
    _db_run('DELETE FROM candidato WHERE id = ?', candidato_id)
    flash('Currículo excluído com sucesso.', 'ok')
    return redirect(url_for('admin_dashboard'))


@app.route('/instagram')
@app.route('/card-instagram')
def card_instagram():
    premium = _card_premium_publico()
    if premium is not None:
        return premium
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
    return redirect('/admin-site/card/editor')


@app.get('/admin-site/card/legado')
def admin_card_legado():
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
    for chave, minimo, maximo in [('card_colunas',1,3), ('card_raio',10,35), ('card_altura_botao',48,100), ('card_avatar_tamanho',80,160), ('card_intensidade_vidro',30,100)]:
        try:
            numero = int(request.form.get(chave, CARD_DEFAULTS[chave]))
        except (ValueError, TypeError):
            numero = int(CARD_DEFAULTS[chave])
        set_config(chave, str(max(minimo, min(maximo, numero))))
    set_config('card_rodape', request.form.get('card_rodape', '')[:180])
    for chave in ('card_mostrar_logo','card_mostrar_localizacao','card_mostrar_avatar','card_mostrar_rodape'):
        set_config(chave, '1' if request.form.get(chave) == 'on' else '0')
    set_config('card_estilo', 'vidro')
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
            set_config(campo, valor)
            if antigo and antigo != valor:
                excluir_arquivo_referencia(antigo)

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
    anterior = link.get('icone')
    enviado = request.files.get('icone')
    if enviado and enviado.filename and not icone:
        flash('Não foi possível salvar o novo ícone. O anterior foi preservado.', 'erro')
        return redirect(url_for('admin_card'))
    icone = icone or anterior

    _db_run('''UPDATE card_link SET titulo = ?, subtitulo = ?, url = ?, icone = ?,
               ativo = ?, ordem = ? WHERE id = ?''',
            titulo, subtitulo, url, icone, ativo, ordem, link_id)
    if anterior and icone != anterior:
        excluir_arquivo_referencia(anterior)
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
    # Salvar somente valores realmente alterados, em uma operação D1.
    atuais = config_dict()
    enviados = {chave: request.form[chave] for chave in DEFAULTS
                if chave not in upload_config_keys and chave in request.form}
    alterados = {chave: valor for chave, valor in enviados.items()
                 if atuais.get(chave) != valor}
    if alterados:
        try:
            placeholders = ', '.join(['(?, ?)'] * len(alterados))
            parametros = [item for par in alterados.items() for item in par]
            result = _db_run(
                'INSERT INTO site_config (chave, valor) VALUES ' + placeholders +
                ' ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor',
                *parametros
            )
            if not result.success:
                raise RuntimeError('D1 rejected configuration update')
            gravados = config_dict()
            if any(gravados.get(k) != v for k, v in alterados.items()):
                raise RuntimeError('Configuration verification failed')
        except Exception as exc:
            print(f'Site configuration save failed: {type(exc).__name__}')
            flash('Não foi possível confirmar a atualização das informações. Confira os valores e tente novamente.', 'erro')
            return redirect(url_for('admin_dashboard'))

    for campo, prefixo in [
        ('imagem_destaque', 'destaque'),
        ('foto_bau', 'bau'),
        ('anuncio_bau_frente', 'anuncio_frente'),
        ('anuncio_bau_lado', 'anuncio_lado'),
        ('anuncio_bau_traseira', 'anuncio_traseira'),
    ]:
        arquivo = request.files.get(campo)
        if not arquivo or not arquivo.filename:
            continue
        valor = salvar_upload(arquivo, prefixo, ALLOWED_IMAGE_EXTENSIONS)
        if not valor:
            flash('Não foi possível salvar a imagem de ' + campo + '. A imagem anterior foi preservada.', 'erro')
            return redirect(url_for('admin_dashboard'))
        antigo = get_config(campo, '')
        set_config(campo, valor)
        if get_config(campo) != valor:
            flash('Não foi possível confirmar a nova imagem de ' + campo + '.', 'erro')
            return redirect(url_for('admin_dashboard'))
        if antigo and antigo != valor:
            excluir_arquivo_referencia(antigo)

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
    enviado = request.files.get('logo')
    if enviado and enviado.filename and not logo:
        flash('Não foi possível salvar a logo. Envie uma imagem válida e tente novamente.', 'erro')
        return redirect(url_for('admin_dashboard'))
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
    enviado = request.files.get('logo')
    anterior = parceiro.get('logo')
    if enviado and enviado.filename and not logo:
        flash('Não foi possível salvar a nova logo. A imagem anterior foi preservada. Tente um PNG, JPG ou WEBP válido.', 'erro')
        return redirect(url_for('admin_dashboard'))
    nova_logo = logo or anterior
    try:
        _db_run('UPDATE partner SET nome = ?, link = ?, logo = ?, ativo = ?, ordem = ? WHERE id = ?',
                nome, link, nova_logo, ativo, ordem, partner_id)
    except Exception:
        if logo:
            excluir_arquivo_referencia(logo)
        raise
    if logo and anterior and anterior != logo and str(anterior).startswith('db:'):
        if not excluir_arquivo_referencia(anterior):
            flash('Nova logo salva. A limpeza da imagem anterior ainda não foi confirmada.', 'erro')
            return redirect(url_for('admin_dashboard'))
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
    anterior = avaliacao.get('foto')
    enviado = request.files.get('foto')
    if enviado and enviado.filename and not foto:
        flash('Não foi possível salvar a nova foto. A anterior foi preservada.', 'erro')
        return redirect(url_for('admin_dashboard'))
    foto = foto or anterior

    _db_run('''UPDATE review SET nome = ?, empresa = ?, comentario = ?, nota = ?,
               data_avaliacao = ?, link = ?, foto = ?, ativo = ?, ordem = ? WHERE id = ?''',
            nome, empresa, comentario, nota, data_avaliacao, link, foto, ativo, ordem, review_id)
    if anterior and foto != anterior:
        excluir_arquivo_referencia(anterior)
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



# Transactional email: credentials live only in Worker secrets.
def _site_send_email(subject, body, reply_to, attachment=None):
    import json
    from js import fetch, JSON
    key = getattr(_env(), 'RESEND_API_KEY', None)
    sender = getattr(_env(), 'SITE_MAIL_FROM', None)
    if not key or not sender:
        raise RuntimeError('Serviço de e-mail ainda não configurado.')
    payload = {'from': str(sender), 'to': ['contato@coopexentregas.com.br'],
               'subject': subject, 'text': body, 'reply_to': reply_to}
    if attachment:
        payload['attachments'] = [attachment]
    options = {'method': 'POST', 'headers': {'Authorization': 'Bearer '+str(key),
               'Content-Type': 'application/json'}, 'body': json.dumps(payload)}
    response = run_sync(fetch('https://api.resend.com/emails', JSON.parse(json.dumps(options))))
    if not response.ok:
        raise RuntimeError('Serviço de e-mail não aceitou o envio.')

def _site_valid_email(value):
    return bool(_seo_re.fullmatch(r'[^@\s]{1,100}@[^@\s]{1,140}\.[^@\s]{2,30}', value))

@app.route('/contato/enviar', methods=['POST'])
def enviar_mensagem_contato():
    if request.form.get('website'):
        return jsonify(ok=False, mensagem='Não foi possível enviar.'), 400
    nome = request.form.get('nome','').strip()
    email = request.form.get('email','').strip()
    telefone = request.form.get('telefone','').strip()
    assunto = request.form.get('assunto','').strip()
    mensagem = request.form.get('mensagem','').strip()
    if not (2 <= len(nome) <= 120 and _site_valid_email(email) and len(telefone) <= 30
            and assunto in ('Elogio','Reclamação','Sugestão','Dúvida','Outros assuntos')
            and 5 <= len(mensagem) <= 4000):
        return jsonify(ok=False, mensagem='Confira os campos obrigatórios.'), 400
    try:
        _site_send_email('Contato pelo site COOPEX — '+assunto,
            f'Nome: {nome}\nE-mail: {email}\nTelefone: {telefone}\nAssunto: {assunto}\n\n{mensagem}', email)
    except Exception:
        return jsonify(ok=False, mensagem='Envio temporariamente indisponível. Utilize nosso WhatsApp.'), 503
    return jsonify(ok=True, mensagem='Mensagem enviada com sucesso! Agradecemos seu contato.')


@app.get('/area-do-cliente')
@app.get('/area-do-cliente/')
def area_cliente_publica():
    # O site permanece na origem oficial; o iframe usa a origem exata do OAuth.
    # Subdomínios HTTPS do mesmo domínio são same-site para os cookies Lax.
    html = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
    <title>Área do Cliente | COOPEX Entregas</title><link rel="icon" href="/favicon.svg">
    <style>*{box-sizing:border-box}html,body{margin:0;height:100%;font-family:system-ui,sans-serif}
    body{display:flex;flex-direction:column;background:linear-gradient(145deg,#f4f9ff,#dcecff);color:#103975}
    header{display:flex;align-items:center;gap:14px;padding:10px clamp(12px,3vw,40px);min-height:54px;background:#f6fbfff2;border-bottom:1px solid #c7dff8;box-shadow:0 3px 12px #124ba51c}
    header a{font-size:14px;color:#0a4db3;font-weight:700;text-decoration:none}header strong{font-size:14px;margin-left:auto}
    iframe{display:block;border:0;flex:1;width:100%;min-height:0;background:#e6f2ff}
    </style></head><body><header><a href="/">← Voltar ao site</a><strong>Área do Cliente</strong></header>
    <iframe src="https://www.financeiro.coopexentregas.com.br/cliente/" title="Área do Cliente COOPEX" allow="geolocation; clipboard-write" referrerpolicy="strict-origin-when-cross-origin"></iframe>
    </body></html>"""
    return Response(html,mimetype='text/html',headers={'Cache-Control':'no-store','Permissions-Policy':'geolocation=(self "https://www.financeiro.coopexentregas.com.br" "https://financeiro.coopexentregas.com.br"), clipboard-write=(self "https://www.financeiro.coopexentregas.com.br" "https://financeiro.coopexentregas.com.br")'})


from card_premium import instalar as instalar_card_premium
_card_premium_publico = instalar_card_premium(app, get_config, set_config, _db_run, _rows, card_config_dict, arquivo_url, login_required)

Default = wsgi.entrypoint(app)
