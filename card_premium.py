"""Editor visual próprio COOPEX. Rascunho, histórico e versão pública separados."""
import json
import re
import secrets
from urllib.parse import urlsplit
from flask import request, session, jsonify, abort, redirect, render_template_string, make_response

def instalar(app, get_config, set_config, db_run, rows, card_config_dict, arquivo_url, login_required):
    def seguro_url(v):
        v=str(v or '').strip()[:2000]
        if not v or any(ord(c)<32 for c in v) or '\\' in v:return ''
        if v.startswith('/') and not v.startswith('//'):return v
        try:
            p=urlsplit(v)
            if p.scheme in ('https','http') and p.hostname:return v
            if p.scheme in ('mailto','tel') and p.path:return v
        except ValueError:pass
        return ''
    def txt(v,n=300):return str(v or '')[:n]
    def num(v,d,lo,hi):
        try:return max(lo,min(hi,int(v)))
        except (ValueError,TypeError,OverflowError):return d
    def cor(v,d):return v if isinstance(v,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',v) else d
    def escolha(v,opts,d):return v if isinstance(v,str) and v in opts else d
    tipos=('botao','titulo','texto','imagem','video','divisor','espaco','faq','aviso','contato','rede','contagem')
    def normalizar(d):
        if not isinstance(d,dict):raise ValueError('Configuração inválida')
        p=d.get('tema',{})
        if not isinstance(p,dict):raise ValueError('Tema inválido')
        theme={'nome':txt(p.get('nome'),120),'subtitulo':txt(p.get('subtitulo'),180),'bio':txt(p.get('bio'),900),
          'foto':seguro_url(p.get('foto')),'capa':seguro_url(p.get('capa')),'fundo':seguro_url(p.get('fundo')),
          'primaria':cor(p.get('primaria'),'#0047b8'),'secundaria':cor(p.get('secundaria'),'#eaf4ff'),'texto':cor(p.get('texto'),'#ffffff'),
          'estilo':escolha(p.get('estilo'),('vidro','fosco','minimalista','escuro','metalico','3d','solido','degrade'),'vidro'),
          'cabecalho':escolha(p.get('cabecalho'),('circular','quadrado','retrato','banner','sobreposto','video','minimalista','premium'),'premium'),
          'avatar':num(p.get('avatar'),100,40,220),'raio':num(p.get('raio'),20,0,60),'espaco':num(p.get('espaco'),10,0,40),
          'fonte':num(p.get('fonte'),16,10,28),'largura':num(p.get('largura'),480,300,1000),
          'alinhamento':escolha(p.get('alinhamento'),('left','center','right'),'center')}
        paginas=[];ids=set()
        for pg in (d.get('paginas') or [])[:20]:
            if not isinstance(pg,dict):continue
            pid=txt(pg.get('id'),50)
            if not re.fullmatch(r'[a-zA-Z0-9_-]+',pid) or pid in ids:continue
            ids.add(pid); blocks=[];bids=set()
            for b in (pg.get('blocos') or [])[:100]:
                if not isinstance(b,dict):continue
                bid=txt(b.get('id'),50)
                if not re.fullmatch(r'[a-zA-Z0-9_-]+',bid) or bid in bids:continue
                bids.add(bid)
                blocks.append({'id':bid,'tipo':escolha(b.get('tipo'),tipos,'texto'),'titulo':txt(b.get('titulo'),180),
                    'texto':txt(b.get('texto'),2000),'url':seguro_url(b.get('url')),'imagem':seguro_url(b.get('imagem')),
                    'icone':('' if str(b.get('icone') or '').startswith('db:') else txt(b.get('icone'),12)), 'icone_imagem':seguro_url(b.get('icone_imagem') or (arquivo_url(b.get('icone')) if re.fullmatch(r'db:\d+',str(b.get('icone') or '')) else '')),'cor':cor(b.get('cor'),'#ffffff'),'texto_cor':cor(b.get('texto_cor'),'#12427c'),
                    'largura':num(b.get('largura'),100,20,100),'altura':num(b.get('altura'),64,16,600),
                    'raio':num(b.get('raio'),20,0,80),'fonte':num(b.get('fonte'),16,10,42),
                    'opacidade':num(b.get('opacidade'),95,10,100),'sombra':num(b.get('sombra'),12,0,40),
                    'alinhamento':escolha(b.get('alinhamento'),('left','center','right'),'center'),
                    'estilo':escolha(b.get('estilo'),('vidro','solido','contorno','capsula','3d','transparente'),'vidro'),
                    'animacao':escolha(b.get('animacao'),('nenhuma','pulsar','flutuar','brilhar'),'nenhuma'),
                    'acao':escolha(b.get('acao'),('link','nova','pagina','janela'),'link'),'destino':txt(b.get('destino'),50),
                    'oculto':b.get('oculto') is True})
            paginas.append({'id':pid,'nome':txt(pg.get('nome'),60) or 'Página','blocos':blocks})
        if not paginas:raise ValueError('Crie pelo menos uma página')
        return {'tema':theme,'paginas':paginas,'menu':escolha(d.get('menu'),('superior','inferior','nenhum'),'inferior')}
    def inicial():
        c=card_config_dict()
        bs=[]
        for r in rows('SELECT * FROM card_link ORDER BY ordem ASC, criado_em ASC'):
            bs.append({'id':'legado-'+str(r['id']),'tipo':'botao','titulo':r.get('titulo') or r.get('nome') or 'Link','texto':r.get('descricao') or '', 'url':r.get('url') or '', 'icone':r.get('icone') or '', 'icone_imagem':arquivo_url(r.get('icone')) if re.fullmatch(r'db:\d+',str(r.get('icone') or '')) else '', 'oculto':not bool(r.get('ativo')), 'cor':c.get('card_cor_botao'),'texto_cor':c.get('card_cor_texto_botao'),'altura':min(52,num(c.get('card_altura_botao'),48,16,600)),'raio':c.get('card_raio'),'largura':100})
        if c.get('card_link_whatsapp'):
            bs.append({'id':'whatsapp','tipo':'botao','titulo':c.get('card_botao_whatsapp'),'url':c.get('card_link_whatsapp')})
        return normalizar({'tema':{'nome':c.get('card_nome'),'subtitulo':c.get('card_descricao'),'bio':c.get('card_bio'),
            'foto':arquivo_url(c.get('card_foto')) or arquivo_url(c.get('card_logo')) or '/static/img/coopex-oficial-v2.webp',
            'fundo':arquivo_url(c.get('card_fundo_imagem')),'primaria':c.get('card_cor_primaria'),'secundaria':c.get('card_cor_secundaria'),
            'texto':c.get('card_cor_texto'),'avatar':min(108,num(c.get('card_avatar_tamanho'),100,40,220)),'raio':c.get('card_raio'),'espaco':7,'fonte':14},
            'paginas':[{'id':'inicio','nome':'Início','blocos':bs}]})
    def carregar(chave):
        raw=get_config(chave,'')
        return normalizar(json.loads(raw)) if raw else None
    def admin():
        if not login_required():abort(403)
    def csrf():
        admin()
        token=request.headers.get('X-Card-CSRF','')
        if not token or not secrets.compare_digest(token,session.get('card_editor_csrf','')):abort(403)
    def resposta(html):
        r=make_response(html);r.headers['Cache-Control']='private, no-store';return r
    @app.get('/admin-site/card/editor')
    def editor_card_premium():
        if not login_required():return redirect('/admin-site')
        session.setdefault('card_editor_csrf',secrets.token_urlsafe(32))
        data=carregar('__card_premium_rascunho') or carregar('__card_premium_publicado') or inicial()
        return resposta(render_template_string(EDITOR, data=data, csrf=session['card_editor_csrf'], render_js=RENDER_JS))
    @app.post('/admin-site/card/editor/salvar')
    def salvar_card_premium():
        csrf()
        if request.content_length and request.content_length>400000:return jsonify(ok=False,erro='Projeto muito grande'),413
        try:d=normalizar(request.get_json())
        except (ValueError,TypeError,AttributeError):return jsonify(ok=False,erro='Configuração inválida'),400
        set_config('__card_premium_rascunho',json.dumps(d,ensure_ascii=False,separators=(',',':')))
        return jsonify(ok=True)
    @app.post('/admin-site/card/editor/publicar')
    def publicar_card_premium():
        csrf()
        if request.content_length and request.content_length>400000:return jsonify(ok=False,erro='Projeto muito grande'),413
        try:d=normalizar(request.get_json())
        except (ValueError,TypeError,AttributeError):return jsonify(ok=False,erro='Configuração inválida'),400
        raw=json.dumps(d,ensure_ascii=False,separators=(',',':'))
        db_run('CREATE TABLE IF NOT EXISTS card_premium_versoes (id INTEGER PRIMARY KEY AUTOINCREMENT, conteudo TEXT NOT NULL, autor TEXT NOT NULL, criado TEXT DEFAULT CURRENT_TIMESTAMP)')
        db_run('INSERT INTO card_premium_versoes(conteudo,autor) VALUES (?,?)',raw,session.get('site_admin_usuario','Admin'))
        set_config('__card_premium_rascunho',raw)
        set_config('__card_premium_publicado',raw)
        return jsonify(ok=True)
    @app.get('/admin-site/card/editor/versoes')
    def versoes_card_premium():
        admin()
        db_run('CREATE TABLE IF NOT EXISTS card_premium_versoes (id INTEGER PRIMARY KEY AUTOINCREMENT, conteudo TEXT NOT NULL, autor TEXT NOT NULL, criado TEXT DEFAULT CURRENT_TIMESTAMP)')
        return jsonify(ok=True,versoes=rows('SELECT id,autor,criado FROM card_premium_versoes ORDER BY id DESC LIMIT 30'))
    @app.get('/admin-site/card/editor/versoes/<int:vid>')
    def restaurar_card_premium(vid):
        admin()
        itens=rows('SELECT conteudo FROM card_premium_versoes WHERE id=?',vid)
        if not itens:abort(404)
        return jsonify(ok=True,data=normalizar(json.loads(itens[0]['conteudo'])))
    def publico():
        d=carregar('__card_premium_publicado')
        if d is None:return None
        return resposta(render_template_string(PUBLICO,data=d,render_js=RENDER_JS))
    return publico

RENDER_JS=r"""
function desenhar(host,d,pid,editar=false,onSelect=null,onMove=null,onResize=null){
 const pg=d.paginas.find(x=>x.id===pid)||d.paginas[0],t=d.tema;
 host.replaceChildren();host.className='card-publico '+t.estilo;
 Object.assign(host.style,{backgroundColor:t.primaria,backgroundImage:t.fundo?'url('+JSON.stringify(t.fundo)+')':'linear-gradient(145deg,'+t.primaria+','+t.secundaria+')',color:t.texto,fontSize:t.fonte+'px',maxWidth:t.largura+'px',textAlign:t.alinhamento,backgroundSize:'cover',backgroundPosition:'center'});
 const el=(tag,cls,txt)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(txt)n.textContent=txt;return n};
 const head=el('header','cp-head '+t.cabecalho);
 if(t.capa){const im=el(t.cabecalho==='video'?'video':'img','cp-capa');im.src=t.capa;if(im.tagName==='VIDEO'){im.muted=true;im.loop=true;im.autoplay=true;im.playsInline=true;}else im.alt='Capa';head.append(im)}
 if(t.foto&&t.cabecalho!=='minimalista'){const im=el('img','cp-avatar');im.src=t.foto;im.alt='Logotipo';im.style.width=t.avatar+'px';im.style.height=t.avatar+'px';head.append(im)}
 head.append(el('h1','',t.nome),el('strong','',t.subtitulo),el('p','',t.bio));host.append(head);
 const nav=el('nav','cp-nav '+d.menu);if(d.menu!=='nenhum'&&d.paginas.length>1){for(const p of d.paginas){const n=el('button',p.id===pg.id?'atual':'',p.nome);n.onclick=()=>desenhar(host,d,p.id,editar,onSelect,onMove,onResize);nav.append(n)}if(d.menu==='superior')host.append(nav)}
 const grid=el('main','cp-grid');grid.style.gap=t.espaco+'px';host.append(grid);
 for(const b of pg.blocos){if(b.oculto&&!editar)continue;
  const node=el('article','cp-bloco '+b.estilo+' '+b.animacao+(b.oculto?' oculto':''));
  node.dataset.bid=b.id;Object.assign(node.style,{width:'calc('+b.largura+'% - '+(b.largura<100?t.espaco:0)+'px)',minHeight:b.altura+'px',borderRadius:(b.estilo==='capsula'?999:b.raio)+'px',fontSize:b.fonte+'px',color:b.texto_cor,backgroundColor:b.cor+Math.round(b.opacidade*2.55).toString(16).padStart(2,'0'),boxShadow:'0 5px '+b.sombra+'px #15284c33',textAlign:b.alinhamento});
  if(b.tipo==='divisor'){node.append(el('hr'))}else if(b.tipo==='espaco'){node.style.background='transparent';node.style.boxShadow='none'}else{
   if(b.imagem){const im=el(b.tipo==='video'?'video':'img','cp-media');im.src=b.imagem;if(im.tagName==='VIDEO'){im.controls=!editar;im.preload='metadata'}else{im.alt=b.titulo;im.loading='lazy'}node.append(im)}
   if(b.tipo==='faq'){const det=el('details');det.append(el('summary','',b.titulo),el('p','',b.texto));node.append(det)}
   else {const n=el(b.tipo==='titulo'?'h2':'strong','cp-label',(b.icone&&!b.icone.startsWith('db:')?b.icone+' ':'')+b.titulo);if(b.icone_imagem){const icon=el('img','cp-icon');icon.src=b.icone_imagem;icon.alt='';n.prepend(icon)}node.append(n);if(b.texto)node.append(el('p','',b.texto))}
  }
  if(editar){node.draggable=true;node.tabIndex=0;node.onclick=()=>onSelect(pg.id,b.id);node.ondragstart=e=>{e.dataTransfer.setData('text/plain',b.id);e.dataTransfer.effectAllowed='move'};node.ondragover=e=>e.preventDefault();node.ondrop=e=>{e.preventDefault();onMove(pg.id,e.dataTransfer.getData('text/plain'),b.id)};
   const handle=el('button','cp-resize','↘');handle.title='Redimensionar';handle.onpointerdown=e=>{e.preventDefault();e.stopPropagation();handle.setPointerCapture(e.pointerId);const start=[e.clientX,e.clientY],w=node.offsetWidth,h=node.offsetHeight,full=grid.clientWidth;handle.onpointermove=ev=>{node.style.width=Math.max(20,Math.min(100,(w+ev.clientX-start[0])/full*100))+'%';node.style.minHeight=Math.max(16,h+ev.clientY-start[1])+'px'};handle.onpointerup=ev=>{handle.onpointermove=null;onResize(pg.id,b.id,Math.round((w+ev.clientX-start[0])/full*100),Math.round(h+ev.clientY-start[1]))}};node.append(handle)
  }else if(b.url||b.acao==='pagina'||b.acao==='janela'){const action=()=>{if(b.acao==='pagina'){desenhar(host,d,b.destino);return}if(b.acao==='janela'){const dlg=el('dialog','cp-modal');const close=el('button','','Fechar ×');close.onclick=()=>dlg.close();dlg.append(close,el('h2','',b.titulo),el('p','',b.texto));if(b.url){const a=el('a','','Abrir serviço');a.href=b.url;a.target='_blank';a.rel='noopener noreferrer';dlg.append(a)}document.body.append(dlg);dlg.onclose=()=>dlg.remove();dlg.showModal();return}if(b.url){if(b.acao==='nova')window.open(b.url,'_blank','noopener,noreferrer');else location.href=b.url}};node.tabIndex=0;node.setAttribute('role','link');node.onclick=action;node.onkeydown=e=>{if(e.key==='Enter')action()}}
  grid.append(node)
 }
 if(d.menu==='inferior'&&d.paginas.length>1)host.append(nav);
}
"""
CSS=r"""
*{box-sizing:border-box}body{margin:0;font:14px system-ui,sans-serif;color:#16386c;background:#dcecff}button,input,select,textarea{font:inherit}button{cursor:pointer}button:focus-visible,a:focus-visible{outline:3px solid #39a5ff;outline-offset:2px}.card-publico{width:100%;min-height:100%;margin:auto;padding:16px;overflow:hidden}.cp-head{text-align:inherit;padding:8px 2px}.cp-label{display:flex;gap:8px;align-items:center;justify-content:inherit}.cp-icon{width:26px;height:26px;object-fit:contain;flex:none}.cp-head h1{overflow-wrap:anywhere}.cp-head p{line-height:1.3}.cp-grid{align-content:start}.cp-head h1{font-size:1.5em;margin:8px 0}.cp-head p,.cp-bloco p{white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0}.cp-avatar{object-fit:contain;border-radius:50%;background:#fff;max-width:100%}.quadrado .cp-avatar,.retrato .cp-avatar{border-radius:18px}.cp-capa{width:100%;max-height:180px;object-fit:cover;border-radius:16px}.premium .cp-avatar{box-shadow:0 6px 24px #0004,inset 0 0 12px #fff}.sobreposto .cp-avatar{margin-top:-35px;position:relative}.cp-grid{display:flex;flex-wrap:wrap;justify-content:center;align-items:flex-start}.cp-bloco{position:relative;padding:12px;display:flex;flex-direction:column;justify-content:center;overflow-wrap:anywhere;max-width:100%;border:1px solid #ffffff80}.cp-bloco.vidro{backdrop-filter:blur(9px);background-image:linear-gradient(145deg,#ffffff66,transparent)}.cp-bloco.contorno{background:transparent!important;border:2px solid currentColor}.cp-bloco.transparente{background:transparent!important;box-shadow:none!important}.cp-bloco[role=link]{cursor:pointer}.cp-media{width:100%;max-height:420px;object-fit:contain;border-radius:inherit}.cp-nav{display:flex;flex-wrap:wrap;justify-content:center;gap:5px;margin:12px 0}.cp-nav button{border:1px solid #fff;border-radius:14px;padding:8px;background:#ffffffa0;color:#123b76}.cp-nav .atual{background:#fff;font-weight:bold}.cp-resize{position:absolute;bottom:0;right:0;width:25px;height:25px;padding:0;touch-action:none;border:1px solid #1266c9;border-radius:5px;background:#fff;color:#1266c9}.cp-modal{border:1px solid #fff;border-radius:20px;max-width:90vw;color:#153c77;background:#edf6ff;padding:20px}.cp-modal::backdrop{background:#001b4b77}.oculto{opacity:.35}.cp-bloco h2{margin:0}.cp-bloco hr{width:100%;border:0;border-top:1px solid currentColor}@keyframes pulsar{50%{transform:scale(.98)}}@keyframes flutuar{50%{transform:translateY(-3px)}}@keyframes brilhar{50%{filter:brightness(1.12)}}.pulsar,.flutuar,.brilhar{animation-duration:3s;animation-iteration-count:infinite}.pulsar{animation-name:pulsar}.flutuar{animation-name:flutuar}.brilhar{animation-name:brilhar}@media(prefers-reduced-motion:reduce){*{animation:none!important}}
"""
PUBLICO="""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{data.tema.nome}} | COOPEX</title><meta name="description" content="{{data.tema.bio}}"><meta property="og:title" content="{{data.tema.nome}}"><meta property="og:description" content="{{data.tema.bio}}"><meta property="og:image" content="https://www.coopexentregas.com.br/static/img/coopex-oficial-v2.webp"><link rel="canonical" href="https://www.coopexentregas.com.br/instagram"><link rel="icon" href="/favicon.svg"><style>"""+CSS+"""html,body{min-height:100%;background:#e3efff}#pagina{min-height:100dvh}</style></head><body><div id="pagina"></div><noscript><p>{{data.tema.nome}}</p>{% for p in data.paginas %}{% for b in p.blocos %}{% if not b.oculto and b.url %}<a href="{{b.url}}">{{b.titulo}}</a>{% endif %}{% endfor %}{% endfor %}</noscript><script>{{render_js|safe}}
const data={{data|tojson}};desenhar(document.getElementById('pagina'),data,data.paginas[0].id);
</script></body></html>"""
EDITOR="""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Editor Instagram COOPEX</title><style>"""+CSS+"""
body{background:linear-gradient(135deg,#f4f9ff,#b9d8f8);min-height:100dvh}.top{display:flex;align-items:center;gap:7px;padding:10px;flex-wrap:wrap;background:#ffffffb0;border-bottom:1px solid white;position:sticky;top:0;z-index:5}.top strong{flex:1;font-size:18px}.top a{color:#154b8f}.btn,.top button,.menu button{border:1px solid #fff;border-radius:10px;padding:9px 12px;background:linear-gradient(145deg,#fff,#d0e6ff);color:#15437c;font-weight:700}.primary{background:linear-gradient(145deg,#3198ee,#0739b4)!important;color:white!important}.workspace{display:grid;grid-template-columns:190px minmax(260px,1fr) minmax(340px,1.2fr);gap:12px;padding:12px;height:calc(100dvh - 76px);min-height:460px}.panel{background:linear-gradient(145deg,#ffffffdd,#d4e8ffbb);border:1px solid white;border-radius:18px;box-shadow:0 6px 18px #15487826,inset 0 1px 3px white;padding:12px;overflow:auto;min-width:0}.menu{display:flex;flex-direction:column;gap:7px}.menu button{text-align:left}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.fields label{display:flex;flex-direction:column;gap:4px;font-size:12px;font-weight:700;min-width:0}.fields input,.fields select,.fields textarea{width:100%;padding:8px;min-width:0;border:1px solid #b1cde9;border-radius:9px;background:#f4faff;color:#173b72}.fields input[type=color]{height:38px}.wide{grid-column:1/-1}.preview{display:flex;flex-direction:column;align-items:center;gap:8px;overflow:auto}.device{display:flex;gap:5px;flex-wrap:wrap;justify-content:center}.phone{background:#12263e;border:7px solid #182b43;border-radius:30px;max-width:100%;width:390px;height:690px;min-height:320px;overflow:hidden;position:relative;box-shadow:0 8px 25px #123b7b55}.phone.desktop{border-radius:12px;width:100%;height:100%}.phone .card-publico{max-width:none!important;min-height:100%;transform-origin:top center}.phone #preview{position:relative}.phone .cp-head{padding:5px 0}.phone .cp-head h1{margin:5px 0}.phone .cp-bloco{padding:7px 10px}.phone .cp-resize{width:20px;height:20px}.phone.desktop{overflow:hidden}.phone .cp-bloco{cursor:grab;animation:none!important}.phone .cp-bloco.selected{outline:2px solid #20d3fd;outline-offset:2px}.status{font-size:12px;color:#355b84}.list{display:flex;flex-direction:column;gap:5px;margin:10px 0}.list button{text-align:left;border:1px solid #c8ddf4;border-radius:9px;padding:8px;background:#f7fbff;color:#174077}.list .active{background:#135cc5;color:white}.actions{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}.panel h2{font-size:17px;margin:4px 0 12px}.panel h3{font-size:14px}#status{min-width:120px}@media(max-width:900px){.workspace{grid-template-columns:130px minmax(200px,1fr);height:auto}.preview{grid-column:1/-1;min-height:700px}.top{position:static}}@media(max-width:520px){.workspace{grid-template-columns:1fr}.menu{flex-direction:row;flex-wrap:wrap}.preview{grid-column:auto}.fields{grid-template-columns:1fr}}
</style></head><body><header class="top"><strong>COOPEX · Editor Instagram</strong><a href="/admin-site/painel">Painel</a><a href="/admin-site/card/legado">Configuração anterior</a><button id="undo">↶ Desfazer</button><button id="redo">↷ Refazer</button><button id="save">Salvar rascunho</button><button id="publish" class="primary">Publicar</button><a href="/instagram" target="_blank" rel="noopener">Página pública ↗</a><span id="status" class="status">Rascunho</span></header><div class="workspace"><aside class="panel menu" id="menu"></aside><section class="panel" id="props"></section><section class="panel preview"><h2>Prévia em tempo real</h2><div class="device" id="devices"></div><div class="phone" id="phone"><div id="preview"></div></div><small id="fitnotice">Selecione, arraste ou redimensione os blocos na prévia.</small></section></div><script>{{render_js|safe}}
let d={{data|tojson}},csrf={{csrf|tojson}},pid=d.paginas[0].id,bid=null,aba='Aparência',past=[],future=[],timer,seq=0,saved=0,queue=Promise.resolve();
const $=id=>document.getElementById(id),copy=o=>JSON.parse(JSON.stringify(o)),uid=()=>crypto.randomUUID(),pg=()=>d.paginas.find(x=>x.id===pid)||d.paginas[0],block=()=>pg().blocos.find(x=>x.id===bid);
const kinds={botao:'Botão / link',titulo:'Título',texto:'Texto',imagem:'Imagem',video:'Vídeo',divisor:'Divisor',espaco:'Espaçamento',faq:'Pergunta frequente',aviso:'Aviso',contato:'Contato',rede:'Rede social',contagem:'Contagem'};
function status(t){$('status').textContent=t}
function change(fn,redraw=true){past.push(copy(d));if(past.length>80)past.shift();future=[];fn();seq++;preview();if(redraw)props();status('Alterações não publicadas');clearTimeout(timer);timer=setTimeout(()=>save(false),1200)}
function preview(){desenhar($('preview'),d,pid,true,(p,b)=>{pid=p;bid=b;aba='Elementos';menu();props();preview()},(p,from,to)=>{if(from===to)return;change(()=>{const arr=d.paginas.find(x=>x.id===p).blocos,i=arr.findIndex(x=>x.id===from),j=arr.findIndex(x=>x.id===to);if(i>=0&&j>=0)arr.splice(j,0,arr.splice(i,1)[0])})},(p,b,w,h)=>change(()=>{const x=d.paginas.find(x=>x.id===p).blocos.find(x=>x.id===b);x.largura=Math.max(20,Math.min(100,w));x.altura=Math.max(16,Math.min(600,h))}));for(const n of $('preview').querySelectorAll('[data-bid]'))n.classList.toggle('selected',n.dataset.bid===bid);ajustarPrevia()}
function ajustarPrevia(){const phone=$('phone'),p=$('preview');p.style.transform='none';p.style.width='100%';const h=phone.clientHeight;const real=p.scrollHeight;const ratio=Math.min(1,h/Math.max(1,real));if(ratio<1){p.style.transform='scale('+ratio+')';$('fitnotice').textContent='Prévia reduzida para mostrar tudo ('+Math.round(ratio*100)+'%). Ajuste tamanhos ou divida em páginas para caber em 100%.';}else{$('fitnotice').textContent='Tudo cabe na tela. Arraste ou redimensione os blocos.'}}window.addEventListener('resize',ajustarPrevia);document.addEventListener('load',e=>{if(e.target.tagName==='IMG'&&e.target.closest('#preview'))ajustarPrevia()},true);
function button(parent,title,fn,cls='btn'){const b=document.createElement('button');b.className=cls;b.textContent=title;b.onclick=fn;parent.append(b);return b}
function field(parent,label,obj,key,kind='text',opts=null,wide=false){const l=document.createElement('label');l.textContent=label;if(wide)l.className='wide';const e=document.createElement(kind==='select'?'select':kind==='textarea'?'textarea':'input');if(kind==='select'){for(const [v,t] of opts){const o=document.createElement('option');o.value=v;o.textContent=t;e.append(o)}}else if(kind!=='textarea'){e.type=kind;if(kind==='number'||kind==='range'){e.min=opts[0];e.max=opts[1]}}if(kind==='checkbox')e.checked=!!obj[key];else e.value=obj[key]??'';e.oninput=()=>change(()=>obj[key]=kind==='checkbox'?e.checked:kind==='number'||kind==='range'?Number(e.value):e.value,false);l.append(e);parent.append(l)}
const choices=a=>a.map(x=>[x,x[0].toUpperCase()+x.slice(1)]);
function menu(){const m=$('menu');m.replaceChildren();for(const x of ['Visão geral','Aparência','Cabeçalho','Elementos','Páginas internas','Redes sociais','Histórico'])button(m,x,()=>{aba=x;menu();props()},'btn '+(aba===x?'primary':''))}
function props(){const root=$('props');root.replaceChildren();const h=document.createElement('h2');h.textContent=aba;root.append(h);const f=document.createElement('div');f.className='fields';const t=d.tema;
 if(aba==='Visão geral'){const p=document.createElement('p');p.textContent='Crie e organize seu minissite. O rascunho é salvo automaticamente, mas só Publicar altera a página pública.';root.append(p);button(root,'Editar aparência',()=>{aba='Aparência';menu();props()});return}
 if(aba==='Aparência'){field(f,'Cor principal',t,'primaria','color');field(f,'Cor secundária',t,'secundaria','color');field(f,'Cor do texto',t,'texto','color');field(f,'Tema',t,'estilo','select',choices(['vidro','fosco','minimalista','escuro','metalico','3d','solido','degrade']));field(f,'Imagem de fundo (URL)',t,'fundo','text',null,true);field(f,'Espaçamento',t,'espaco','range',[0,40]);field(f,'Fonte',t,'fonte','range',[10,28]);field(f,'Largura máxima',t,'largura','number',[300,1000]);field(f,'Alinhamento',t,'alinhamento','select',[['left','Esquerda'],['center','Centro'],['right','Direita']]);}
 if(aba==='Cabeçalho'){field(f,'Nome',t,'nome','text',null,true);field(f,'Subtítulo',t,'subtitulo','text',null,true);field(f,'Biografia',t,'bio','textarea',null,true);field(f,'Modelo',t,'cabecalho','select',choices(['circular','quadrado','retrato','banner','sobreposto','video','minimalista','premium']));field(f,'Tamanho da foto',t,'avatar','range',[40,220]);field(f,'Foto ou logotipo (URL)',t,'foto','text',null,true);field(f,'Capa ou vídeo (URL)',t,'capa','text',null,true)}
 if(aba==='Páginas internas'){const a=document.createElement('div');a.className='actions';button(a,'Adicionar página',()=>change(()=>{pid=uid();d.paginas.push({id:pid,nome:'Nova página',blocos:[]});bid=null}));root.append(a);for(const p of d.paginas)button(root,p.nome,()=>{pid=p.id;bid=null;props();preview()});field(f,'Nome da página',pg(),'nome');field(f,'Posição do menu',d,'menu','select',[['superior','Superior'],['inferior','Inferior'],['nenhum','Oculto']]);if(d.paginas.length>1)button(root,'Excluir página selecionada',()=>{if(confirm('Excluir esta página do rascunho?'))change(()=>{d.paginas=d.paginas.filter(x=>x.id!==pid);pid=d.paginas[0].id;bid=null})});}
 if(aba==='Elementos'||aba==='Redes sociais'){const a=document.createElement('div');a.className='actions';const sel=document.createElement('select');for(const [k,v] of Object.entries(kinds)){const o=document.createElement('option');o.value=k;o.textContent=v;sel.append(o)}a.append(sel);button(a,'+ Adicionar',()=>change(()=>{bid=uid();pg().blocos.push({id:bid,tipo:sel.value,titulo:kinds[sel.value],texto:'',url:'',imagem:'',icone:'',cor:'#ffffff',texto_cor:'#12427c',largura:100,altura:64,raio:20,fonte:16,opacidade:95,sombra:12,alinhamento:'center',estilo:'vidro',animacao:'nenhuma',acao:'link',destino:'',oculto:false})}));root.append(a);
 const l=document.createElement('div');l.className='list';for(const x of pg().blocos)button(l,(x.oculto?'◌ ':'')+(x.titulo||kinds[x.tipo]),()=>{bid=x.id;props();preview()},x.id===bid?'active':'');root.append(l);const b=block();if(b){field(f,'Título',b,'titulo','text',null,true);field(f,'Descrição',b,'texto','textarea',null,true);field(f,'Endereço do link',b,'url','text',null,true);field(f,'Imagem / vídeo (URL)',b,'imagem','text',null,true);field(f,'Ícone (símbolo)',b,'icone');field(f,'Imagem do ícone (URL)',b,'icone_imagem','text',null,true);field(f,'Formato',b,'estilo','select',choices(['vidro','solido','contorno','capsula','3d','transparente']));field(f,'Cor',b,'cor','color');field(f,'Texto',b,'texto_cor','color');field(f,'Largura %',b,'largura','range',[20,100]);field(f,'Altura px',b,'altura','range',[16,600]);field(f,'Cantos',b,'raio','range',[0,80]);field(f,'Fonte',b,'fonte','range',[10,42]);field(f,'Opacidade',b,'opacidade','range',[10,100]);field(f,'Sombra',b,'sombra','range',[0,40]);field(f,'Alinhamento',b,'alinhamento','select',[['left','Esquerda'],['center','Centro'],['right','Direita']]);field(f,'Animação',b,'animacao','select',choices(['nenhuma','pulsar','flutuar','brilhar']));field(f,'Abrir como',b,'acao','select',[['link','Mesmo local'],['nova','Nova aba'],['pagina','Página interna'],['janela','Janela']]);field(f,'Página de destino',b,'destino','select',[['','Selecione'],...d.paginas.map(x=>[x.id,x.nome])]);field(f,'Ocultar',b,'oculto','checkbox');const actions=document.createElement('div');actions.className='actions wide';button(actions,'Duplicar',()=>change(()=>{const n=copy(b);n.id=uid();pg().blocos.splice(pg().blocos.indexOf(b)+1,0,n);bid=n.id}));for(const [label,delta] of [['↑ Subir',-1],['↓ Descer',1]])button(actions,label,()=>change(()=>{const a=pg().blocos,i=a.indexOf(b),j=i+delta;if(j>=0&&j<a.length)[a[i],a[j]]=[a[j],a[i]]}));button(actions,'Excluir',()=>change(()=>{pg().blocos=pg().blocos.filter(x=>x.id!==bid);bid=null}));f.append(actions)}}
 if(aba==='Histórico'){button(root,'Carregar versões publicadas',async()=>{try{const r=await fetch('/admin-site/card/editor/versoes');const j=await r.json();if(!j.ok)throw Error();const l=document.createElement('div');l.className='list';for(const v of j.versoes)button(l,'Versão '+v.id+' · '+v.criado,async()=>{const res=await fetch('/admin-site/card/editor/versoes/'+v.id);const x=await res.json();if(x.ok)change(()=>{d=x.data;pid=d.paginas[0].id;bid=null})});root.append(l)}catch(e){status('Não foi possível carregar versões')}})}
 root.append(f)}
async function send(action,data){const r=await fetch('/admin-site/card/editor/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Card-CSRF':csrf},body:JSON.stringify(data)});const j=await r.json();if(!r.ok||!j.ok)throw Error(j.erro||'Falha de comunicação')}
function save(manual){const snapshot=copy(d),n=seq;queue=queue.catch(()=>{}).then(async()=>{try{await send('salvar',snapshot);saved=n;if(seq===n)status('Rascunho salvo')}catch(e){status('Falha ao salvar · tente novamente')}});return queue}
$('save').onclick=()=>{clearTimeout(timer);save(true)};$('publish').onclick=()=>{if(!confirm('Publicar este rascunho na página pública?'))return;clearTimeout(timer);const snapshot=copy(d),n=seq;queue=queue.catch(()=>{}).then(async()=>{try{await send('publicar',snapshot);saved=n;status(seq===n?'Publicado com sucesso':'Publicado · há novas alterações')}catch(e){status('Falha na publicação')}})};
function restore(from,to){if(!from.length)return;to.push(copy(d));d=from.pop();pid=pg().id;bid=null;seq++;props();preview();status('Rascunho alterado');clearTimeout(timer);timer=setTimeout(()=>save(false),1200)}
$('undo').onclick=()=>restore(past,future);$('redo').onclick=()=>restore(future,past);
for(const [name,w] of [['Android',390],['iPhone',375],['Tablet',768],['Computador',0]])button($('devices'),name,()=>{$('phone').classList.toggle('desktop',!w);$('phone').style.width=w?w+'px':'100%';preview()});
window.addEventListener('beforeunload',e=>{if(seq!==saved){e.preventDefault();e.returnValue=''}});menu();props();preview();
</script></body></html>"""
