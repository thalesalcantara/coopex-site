# Recuperação do banco do COOPEX Site na Cloudflare

O arquivo PostgreSQL exportado do Render NÃO deve ser enviado para este repositório público: contém candidaturas, senhas e anexos pessoais.

O pacote de recuperação deve ser mantido em local privado. Nele, `importar_dados_coopex_d1.sql` contém os dados estruturados recuperados (sem hashes de senha e sem arquivos binários) e `imagens_do_banco/` contém anexos extraídos.

1. Fazer backup do D1 atual antes de importar.
2. Conferir a compatibilidade das tabelas e comparar configurações existentes.
3. Aplicar SQL com `npx wrangler d1 execute coopex-site --remote --file=importar_dados_coopex_d1.sql`, a partir do diretório em que estiver o arquivo; **não execute antes de realizar o backup e a conferência**.
4. Migrar arquivos públicos para armazenamento adequado (Cloudflare R2) e integrar o Worker à leitura/gravação deles. Currículos e outros documentos pessoais devem ficar privados.
5. Verificar telas, login, edição, imagens e anexos; só depois desativar o Render.

Apenas executar o SQL **não restaura as imagens** nem garante que o site esteja visualmente idêntico ao original. O código deve preservar as referências `db:<id>` dos arquivos e implementar sua resolução no novo armazenamento.
