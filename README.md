# Automacao de RICs (Passo a passo simples)

Este projeto foi feito para facilitar a busca e o download das RICs no site da Lechman.

Ele abre um menu com 3 opcoes:

1. Pesquisar Rics
2. Baixar Rics
3. Sair

## O que o sistema faz

### 1) Pesquisar Rics
- Faz login no site automaticamente.
- Entra na pagina de RICs.
- Coleta os links dos botoes de download.
- Salva os links no arquivo `rics_links.txt`.
- Compara com os arquivos que ja existem na pasta `output`.
- Mostra no terminal:
  - Quantas RICs existem no site.
  - Quantas RICs ainda faltam baixar.

### 2) Baixar Rics
- Tenta acessar a pagina de RICs.
- Se precisar, faz login automaticamente.
- Baixa somente as RICs que ainda faltam.
- Salva os arquivos na pasta `output` com nome do container.
- Aplica um atraso de 100ms entre downloads para evitar travar a conexao.

### 3) Sair
- Fecha o menu.

## Requisitos (dependencias)

Este projeto usa:
- Python 3.10 ou superior
- Windows (arquivo `.bat`)

Nao foi usada biblioteca externa. O script usa apenas bibliotecas padrao do Python.

## Como instalar o Python (se ainda nao tiver)

### Opcao 1 (mais facil): baixar do site oficial
1. Acesse: https://www.python.org/downloads/
2. Baixe e instale o Python 3.
3. Marque a opcao `Add Python to PATH` durante a instalacao.

### Opcao 2 (via terminal no Windows)
No PowerShell, execute:

```powershell
winget install -e --id Python.Python.3.12
```

## Como verificar se o Python esta instalado

No terminal (PowerShell ou CMD):

```powershell
python --version
```

Se aparecer algo como `Python 3.x.x`, esta ok.

## Como usar

### 0) Configurar login (obrigatorio)

Antes de rodar, crie/edite o arquivo `login.local.json` na pasta do projeto com seus dados:

```json
{
  "CNPJ": "SEU_CNPJ",
  "Password": "SUA_SENHA"
}
```

Existe um modelo pronto em `login.example.json`.

O arquivo `login.local.json` fica fora do Git (nao sera enviado ao GitHub).

### 1) Abrir o menu

1. Abra a pasta do projeto.
2. Dê duplo clique em `rics_menu.bat`.
3. Escolha no menu:
   - `1` para pesquisar
   - `2` para baixar faltantes
   - `3` para sair

## Teste rapido (somente 5 links)

Se quiser testar com apenas 5 RICs primeiro:

No CMD:

```cmd
set RICS_TEST_LIMIT=5
rics_menu.bat
```

No PowerShell:

```powershell
$env:RICS_TEST_LIMIT="5"
.\rics_menu.bat
```

Para voltar ao modo normal (sem limite):

No CMD:

```cmd
set RICS_TEST_LIMIT=
```

No PowerShell:

```powershell
Remove-Item Env:RICS_TEST_LIMIT -ErrorAction SilentlyContinue
```

## Onde ficam os arquivos

- Downloads: `output`
- Lista de links coletados: `rics_links.txt`
- Paginas salvas para diagnostico: `output/_debug_pages`
- Login local: `login.local.json` (ignorado no Git)
- Modelo de login: `login.example.json`

## Problemas comuns

- `python nao reconhecido`:
  - Reinstale o Python com `Add Python to PATH` marcado.
- Falha de login:
  - Verifique internet e se o site esta no ar.
- Nenhuma RIC encontrada:
  - Pode nao haver RIC disponivel no momento, ou a sessao pode ter expirado.

## Aviso de seguranca

As credenciais ficam em `login.local.json`.
Esse arquivo esta no `.gitignore` para nao ser publicado no GitHub.
