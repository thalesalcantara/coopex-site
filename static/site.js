function mostrarPagina(id){
  document.querySelectorAll('.page-section').forEach(sec => {
    sec.classList.toggle('active', sec.id === id);
  });

  document.querySelectorAll('.tab-link').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.page === id);
  });

  const avaliacoes = document.getElementById('avaliacoesGoogle');

  if (avaliacoes) {
    if (id === 'inicio' || id === 'sobre') {
      avaliacoes.style.display = 'block';
    } else {
      avaliacoes.style.display = 'none';
    }
  }

  document.body.classList.remove('menu-open');

  if (history.replaceState) {
    history.replaceState(null, '', '#' + id);
  }

  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  });
}

document.addEventListener('DOMContentLoaded', function(){
  document.querySelectorAll('.tab-link').forEach(btn => {
    btn.addEventListener('click', function(){
      const page = this.dataset.page || 'inicio';
      mostrarPagina(page);
    });
  });

  const hash = (window.location.hash || '').replace('#', '');

  if (hash && document.getElementById(hash)) {
    mostrarPagina(hash);
  } else {
    mostrarPagina('inicio');
  }
});

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
