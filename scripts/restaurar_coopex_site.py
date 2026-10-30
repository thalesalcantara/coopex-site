#!/usr/bin/env python3
"""Migra o backup PRIVADO do COOPEX Site para D1 e R2 via Wrangler.
Execute com acesso autenticado a Cloudflare. Nunca suba ZIP, SQL extraido
com dados pessoais ou curriculos ao repositorio publico.
Uso: python scripts/restaurar_coopex_site.py /caminho/coopex_site_recuperacao_completa.zip
Exige: npx wrangler autenticado e R2 habilitado na conta.
"""
import argparse
import csv
import io
import pathlib
import subprocess
import tempfile
import zipfile


def run(*args):
    print("+", " ".join(args), flush=True)
    subprocess.run(args, check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("backup", type=pathlib.Path)
    p.add_argument("--database", default="coopex-site")
    p.add_argument("--bucket", default="coopex-site-arquivos")
    p.add_argument("--confirmar-importacao", action="store_true",
                   help="Aplica a importacao remota somente apos backup e verificacao")
    args = p.parse_args()
    if not args.backup.is_file():
        p.error("Arquivo de backup nao encontrado")
    with tempfile.TemporaryDirectory(prefix="coopex-site-") as temp:
        root = pathlib.Path(temp)
        with zipfile.ZipFile(args.backup) as archive:
            for name in archive.namelist():
                dest = (root / name).resolve()
                if not dest.is_relative_to(root.resolve()):
                    raise RuntimeError("Caminho perigoso no ZIP")
            archive.extractall(root)
        sql = root / "importar_dados_coopex_d1.sql"
        csv_path = root / "manifesto_imagens.csv"
        if not sql.exists() or not csv_path.exists():
            raise RuntimeError("Pacote incompleto")
        # Faz exportacao integral remota ANTES de qualquer gravacao.
        arquivo_backup = pathlib.Path.cwd() / "coopex-site-d1-antes-da-migracao.sql"
        if arquivo_backup.exists():
            raise RuntimeError(f"Arquivo ja existe: {arquivo_backup}")
        run("npx", "wrangler", "d1", "export", args.database,
            "--remote", "--output", str(arquivo_backup))
        print("Copia do D1 salva:", arquivo_backup)
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            items = list(reader)
        print(f"Manifesto possui {len(items)} arquivos.")
        print("IMPORTANTE: arquivos de categoria curriculo e documentos pessoais")
        print("devem ficar em bucket privado com autorizacao no Worker.")
        if not args.confirmar_importacao:
            print("SIMULACAO COMPLETA. Nenhum dado remoto foi alterado.")
            print("Use --confirmar-importacao apos validar o SQL,")
            print("configurar R2 e revisar a politica de documentos privados.")
            return
        # Ao contrario da importacao SQL, os arquivos binarios sao
        # armazenados no R2; a aplicacao precisa resolver referencias db:<id>.
        # Exige configuracao do bucket privado e binding FILES no Worker.
        imgdir = root / "imagens_do_banco"
        # Arquivos extraidos guardam seus IDs originais no manifesto CSV.
        # Usar o mesmo caminho que a rota /arquivo/<id> procura.
        for item in items:
            file_id = int(item["id"])
            file_path = imgdir / item["saved_as"]
            if not file_path.is_file():
                raise RuntimeError(f"Arquivo original ausente: {file_id}")
            privado = item["categoria"].lower().startswith("curriculo")
            prefixo = "privado" if privado else "publico"
            chave = f"{prefixo}/{file_id}/{item['filename']}"
            run("npx", "wrangler", "r2", "object", "put",
                f"{args.bucket}/{chave}", "--file", str(file_path),
                "--content-type", item["mimetype"], "--remote")
        # Metadados pequenos no D1; os binarios ficam somente no R2.
        def quote(value):
            return "'" + str(value or "").replace("'", "''") + "'"
        with (root / "coopex_site_arquivos_metadata.sql").open("w", encoding="utf-8") as f:
            for item in items:
                id_ = int(item["id"])
                f.write(
                    "INSERT INTO file_upload "
                    "(id,filename,original_filename,mimetype,categoria,tamanho,criado_em) VALUES "
                    f"({id_},{quote(item['filename'])},{quote(item['original_filename'])},"
                    f"{quote(item['mimetype'])},{quote(item['categoria'])},"
                    f"{int(item['bytes'])},{quote(item['created_at'])}) "
                    "ON CONFLICT(id) DO UPDATE SET "
                    "filename=excluded.filename,original_filename=excluded.original_filename,"
                    "mimetype=excluded.mimetype,categoria=excluded.categoria,"
                    "tamanho=excluded.tamanho,criado_em=excluded.criado_em;\n"
                )
        run("npx", "wrangler", "d1", "execute", args.database,
            "--remote", "--file", str(sql))
        run("npx", "wrangler", "d1", "execute", args.database,
            "--remote", "--file", str(root / "coopex_site_arquivos_metadata.sql"))
        print("Dados importados; verificar renderizacao, uploads, login e painel.")
        print("IMPORTANTE: habilitar resolucao de refs db:<id> no Worker antes do corte.")


if __name__ == "__main__":
    main()
