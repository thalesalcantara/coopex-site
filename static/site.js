const paginasCOOPEX = {"inicio":"/","sobre":"/sobre","servicos":"/servicos","anuncie":"/anuncie","trabalhe":"/trabalhe","contato":"/contato"};
function paginaAtual(){
  const path = location.pathname.replace(/\/+$/, '') || '/';
  const old = location.hash.slice(1);
  if(path === '/' && Object.hasOwn(paginasCOOPEX,old)) return old;
  return Object.keys(paginasCOOPEX).find(id=>paginasCOOPEX[id]===path)||'inicio';
}
function mostrarPagina(id,modo='push'){
  if(!Object.hasOwn(paginasCOOPEX,id)) id='inicio';
  document.querySelectorAll('.page-section').forEach(sec=>sec.classList.toggle('active',sec.id===id));
  document.querySelectorAll('.tab-link').forEach(btn=>btn.classList.toggle('active',btn.dataset.page===id));
  const avaliacoes=document.getElementById('avaliacoesGoogle');
  if(avaliacoes) avaliacoes.style.display=id==='inicio'?'block':'none';
  document.body.classList.remove('menu-open');
  const path=paginasCOOPEX[id]+location.search;
  if(location.pathname+location.search+location.hash!==path && modo!=='none'){
    if(modo==='replace')history.replaceState({pagina:id},'',path);
    else history.pushState({pagina:id},'',path);
  }
  const canonical=document.querySelector('link[rel="canonical"]');
  if(canonical)canonical.href='https://www.coopexentregas.com.br'+paginasCOOPEX[id];
  const labels={inicio:'Entregas em Natal/RN',sobre:'Sobre',servicos:'Serviços',anuncie:'Divulgue sua marca',trabalhe:'Trabalhe conosco',contato:'Contato'};
  document.title='COOPEX Entregas | '+labels[id];
  window.scrollTo(0,0);
}
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.tab-link').forEach(btn=>btn.addEventListener('click',function(e){
    if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;
    e.preventDefault();mostrarPagina(this.dataset.page||'inicio');
  }));
  mostrarPagina(paginaAtual(),'replace');
});
window.addEventListener('popstate',()=>mostrarPagina(paginaAtual(),'replace'));
window.addEventListener('hashchange',()=>{if(location.hash)mostrarPagina(paginaAtual(),'replace')});
function abrirSolicitacao(){
  const modal = document.getElementById('modalSolicitacao');
  const iframe = document.getElementById('iframeSolicitacao');

  if (!modal || !iframe) return;

  modal.classList.add('aberto');
  modal.setAttribute('aria-hidden', 'false');

  if (!iframe.src) {
    iframe.src = iframe.dataset.src;
  }
}

function fecharSolicitacao(){
  const modal = document.getElementById('modalSolicitacao');

  if (!modal) return;

  modal.classList.remove('aberto');
  modal.setAttribute('aria-hidden', 'true');
}

document.addEventListener('keydown', function(e){
  if (e.key === 'Escape') {
    fecharSolicitacao();
  }
});
