# Site Institucional COOPEX Entregas

Site em Flask com:
- Página única com abas
- Cabeçalho azul royal
- Logo COOPEX sem deformar
- Selo Somos Coop centralizado
- Parceiros com rolagem infinita
- Solicitar entrega em modal dentro da própria página
- Aba Trabalhe conosco com envio de currículo
- Bloqueio para menor de 21 anos
- Obrigatório marcar atividade remunerada
- Painel administrativo oculto para editar dados, imagens, parceiros e ver currículos

## Rodar localmente no Windows

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abra:

```text
http://127.0.0.1:5000
```

## Painel administrativo

O botão de área restrita foi removido do site público.

Acesse diretamente:

```text
http://127.0.0.1:5000/admin-coopex
```

Login padrão:

```text
Usuário: coopex
Senha: coopex05289
```

Também funciona a rota antiga:

```text
/admin-site
```

## Render

Variáveis opcionais:

```text
SITE_ADMIN_USER=coopex
SITE_ADMIN_PASS=coopex05289
FORCAR_SENHA_ADMIN_SITE=1
SECRET_KEY=coloque-uma-chave-segura
```


## Ajuste desta versão

- menu do cabeçalho reorganizado para não ficar um em cima do outro
- logo Somos Coop separada do menu
- logo COOPEX aumentada no cabeçalho
- banner inicial grande para imagem horizontal


## Ajuste de texto do banner

- coluna de texto do banner aumentada
- título reduzido um pouco para não cortar
- quebra de linha ajustada


## Versão harmonizada

Esta versão reorganiza o design para evitar corte de texto no banner:
- texto fica sobre a imagem com uma camada clara em degradê;
- imagem principal ocupa todo o banner;
- cabeçalho alinhado e responsivo;
- logo COOPEX com sombra e sem deformação;
- menu recolhe no celular;
- mantém admin, parceiros, solicitação de entrega e Trabalhe Conosco.


## Avaliações e mapa

Esta versão inclui:
- avaliações estilo Google cadastradas pelo painel administrativo;
- exibição das avaliações na aba Início, no canto esquerdo da área inicial;
- mapa incorporado na aba Contato;
- campo no admin para alterar o link do mapa;
- fundo azul claro para contrastar com o azul royal da identidade visual.


## Ajuste de logos no cabeçalho

- Cabeçalho usando somente o nome COOPEX entregas, sem o símbolo acima.
- Logo COOPEX entregas maior no canto esquerdo.
- Logo Somos Coop maior e centralizada.
- Botões das abas alinhados mais à direita.


## Ajuste fino do topo

- logo Somos Coop aumentada no cabeçalho;
- abas alinhadas mais à direita;
- cabeçalho mantido com o nome COOPEX entregas à esquerda.
