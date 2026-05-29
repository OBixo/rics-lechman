import argparse
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib import parse, request
from urllib.error import HTTPError, URLError
from http.cookiejar import CookieJar

BASE_URL = "http://agendamento-ioa.lechman.com.br"
LOGIN_PAGE_URL = f"{BASE_URL}/"
LOGIN_API_URL = f"{BASE_URL}/Account/Index"
INTERCHANGE_URL = f"{BASE_URL}/InterchangeCopy"

OUTPUT_DIR = Path("output")
LINKS_TXT = Path("rics_links.txt")
DEBUG_DIR = OUTPUT_DIR / "_debug_pages"
DOWNLOAD_DELAY_SECONDS = 0.1
LOGIN_FILE = Path("login.local.json")
INPUT_LIST_FILE = Path("input") / "lista.txt"
LIST_OUTPUT_DIR = OUTPUT_DIR / "lista"


def load_credentials(login_file: Path) -> Tuple[str, str]:
    if not login_file.exists():
        raise RuntimeError(
            "Arquivo de login nao encontrado. Crie login.local.json com CNPJ e Password."
        )

    try:
        data = json.loads(login_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Arquivo de login invalido: {exc}") from exc

    cnpj = str(data.get("CNPJ", "")).strip()
    password = str(data.get("Password", "")).strip()

    if not cnpj or not password:
        raise RuntimeError("Arquivo de login sem CNPJ/Password preenchidos.")

    return cnpj, password


class RicsClient:
    def __init__(self, cnpj: str, password: str, timeout: int = 60) -> None:
        self.cnpj = cnpj
        self.password = password
        self.timeout = timeout
        self.cookies = CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.cookies))
        self.opener.addheaders = [
            ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            ("Accept-Language", "pt-BR,pt;q=0.9,en;q=0.8"),
        ]

    def _open(self, req: request.Request) -> bytes:
        with self.opener.open(req, timeout=self.timeout) as resp:
            return resp.read()

    def get_text(self, url: str) -> str:
        req = request.Request(url, method="GET")
        return self._open(req).decode("utf-8", errors="replace")

    def get_binary(self, url: str) -> Tuple[bytes, Dict[str, str]]:
        req = request.Request(url, method="GET")
        with self.opener.open(req, timeout=self.timeout) as resp:
            data = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return data, headers

    def login(self) -> bool:
        payload = {
            "CNPJ": self.cnpj,
            "Password": self.password,
            "access": "Acessar",
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            LOGIN_API_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json, text/javascript, */*; q=0.01"},
        )

        try:
            raw = self._open(req)
        except (HTTPError, URLError):
            return False

        text = raw.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False

        return str(data.get("Status", "")).lower() == "success"

    def ensure_interchange_page(self) -> str:
        # First access can return login HTML if the session expired.
        html = self.get_text(INTERCHANGE_URL)
        if has_interchange_links(html):
            return html

        if not self.login():
            raise RuntimeError("Falha no login. Verifique CNPJ/Senha ou disponibilidade do site.")

        html = self.get_text(INTERCHANGE_URL)
        if not has_interchange_links(html):
            raise RuntimeError("Login realizado, mas a página de RICs não retornou links de impressão.")
        return html


def has_interchange_links(page_html: str) -> bool:
    return "/InterchangeCopy/Print?" in page_html


def extract_links(page_html: str) -> List[str]:
    raw_links = re.findall(r'href=["\'](/InterchangeCopy/Print\?[^"\']+)["\']', page_html, flags=re.IGNORECASE)
    dedup: List[str] = []
    seen: Set[str] = set()
    for link in raw_links:
        clean_link = html.unescape(link)
        full_link = parse.urljoin(BASE_URL, clean_link)
        if full_link not in seen:
            seen.add(full_link)
            dedup.append(full_link)
    return dedup


def unit_from_link(link: str) -> Optional[str]:
    parsed = parse.urlparse(html.unescape(link))
    params = parse.parse_qs(parsed.query)
    unit = params.get("unit", [None])[0]
    if not unit:
        return None
    return unit.strip().upper()


def save_debug_page(name: str, content: str) -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    (DEBUG_DIR / name).write_text(content, encoding="utf-8")


def save_debug_binary(name: str, content: bytes) -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    (DEBUG_DIR / name).write_bytes(content)


def save_links_txt(links: List[str]) -> List[str]:
    lines: List[str] = []
    for link in links:
        unit = unit_from_link(link) or "SEM_CONTAINER"
        lines.append(f"{unit}|{link}")
    LINKS_TXT.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return lines


def existing_units(output_dir: Path) -> Set[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    units: Set[str] = set()
    for entry in output_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.lower() in {"rics_links.txt"}:
            continue
        # Consider filename stem as container code, e.g. TCNU3409030.pdf -> TCNU3409030
        stem = entry.stem.strip().upper()
        if stem:
            units.add(stem)
    return units


def extension_from_headers(headers: Dict[str, str]) -> str:
    content_type = headers.get("content-type", "").lower()
    if "pdf" in content_type:
        return ".pdf"
    if "html" in content_type:
        return ".html"
    if "json" in content_type:
        return ".json"
    return ".bin"


def build_site_index(links: List[str]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for link in links:
        unit = unit_from_link(link)
        if unit:
            index[unit] = link
    return index


def read_units_list(list_file: Path) -> List[str]:
    if not list_file.exists():
        raise RuntimeError(f"Arquivo de lista nao encontrado: {list_file}")

    units: List[str] = []
    seen: Set[str] = set()
    for raw_line in list_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().upper()
        if not line or line.startswith("#"):
            continue
        if line not in seen:
            seen.add(line)
            units.append(line)
    return units


def pesquisar_rics(client: RicsClient, limit: Optional[int] = None) -> int:
    print("\n[Pesquisar Rics] Coletando página de login...")
    login_html = client.get_text(LOGIN_PAGE_URL)
    save_debug_page("login_page.html", login_html)

    print("[Pesquisar Rics] Acessando página de RICs...")
    interchange_html = client.ensure_interchange_page()
    save_debug_page("interchange_page.html", interchange_html)

    links = extract_links(interchange_html)
    if limit is not None:
        links = links[:limit]

    save_links_txt(links)

    site_index = build_site_index(links)
    site_units = set(site_index.keys())
    local_units = existing_units(OUTPUT_DIR)
    missing_units = sorted(site_units - local_units)

    print("\n===== RELATORIO RICS =====")
    print(f"Numero de Rics disponiveis no site: {len(site_units)}")
    print(f"Numero de Rics faltando baixar: {len(missing_units)}")
    print(f"Arquivo de links salvo em: {LINKS_TXT.resolve()}")
    print(f"Paginas mapeadas em: {DEBUG_DIR.resolve()}")

    if missing_units:
        preview = ", ".join(missing_units[:10])
        suffix = "..." if len(missing_units) > 10 else ""
        print(f"Exemplo de faltantes: {preview}{suffix}")

    return 0


def baixar_rics(client: RicsClient, limit: Optional[int] = None) -> int:
    print("\n[Baixar Rics] Acessando página de RICs...")
    interchange_html = client.ensure_interchange_page()
    save_debug_page("interchange_page.html", interchange_html)

    links = extract_links(interchange_html)
    if limit is not None:
        links = links[:limit]

    site_index = build_site_index(links)
    site_units = set(site_index.keys())
    local_units = existing_units(OUTPUT_DIR)
    missing_units = sorted(site_units - local_units)

    if not missing_units:
        print("Nenhuma RIC pendente para baixar.")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(missing_units)
    print(f"Rics pendentes: {total}")

    for idx, unit in enumerate(missing_units, start=1):
        link = site_index[unit]
        print(f"[{idx}/{total}] Baixando {unit}...")
        try:
            content, headers = client.get_binary(link)
        except (HTTPError, URLError) as exc:
            print(f"  ERRO ao baixar {unit}: {exc}")
            continue

        ext = extension_from_headers(headers)
        out_file = OUTPUT_DIR / f"{unit}{ext}"
        out_file.write_bytes(content)

        if idx == 1:
            save_debug_binary("first_print_response.bin", content)

        # Delay pedido para evitar sobrecarga de conexao.
        time.sleep(DOWNLOAD_DELAY_SECONDS)

    print("Download finalizado.\n")
    return 0


def baixar_lista_unidades(
    client: RicsClient,
    list_file: Path = INPUT_LIST_FILE,
    destination_dir: Path = LIST_OUTPUT_DIR,
) -> int:
    print(f"\n[Baixar Lista] Lendo unidades de: {list_file.resolve()}")
    requested_units = read_units_list(list_file)
    if not requested_units:
        print("Arquivo de lista vazio. Inclua ao menos uma unidade por linha.")
        return 0

    print("[Baixar Lista] Acessando página de RICs...")
    interchange_html = client.ensure_interchange_page()
    save_debug_page("interchange_page.html", interchange_html)

    links = extract_links(interchange_html)
    site_index = build_site_index(links)

    destination_dir.mkdir(parents=True, exist_ok=True)

    available_units = [u for u in requested_units if u in site_index]
    missing_on_site = [u for u in requested_units if u not in site_index]

    print(f"Unidades na lista: {len(requested_units)}")
    print(f"Encontradas no site: {len(available_units)}")
    print(f"Nao encontradas no site: {len(missing_on_site)}")

    for idx, unit in enumerate(available_units, start=1):
        link = site_index[unit]
        print(f"[{idx}/{len(available_units)}] Baixando {unit}...")
        try:
            content, headers = client.get_binary(link)
        except (HTTPError, URLError) as exc:
            print(f"  ERRO ao baixar {unit}: {exc}")
            continue

        ext = extension_from_headers(headers)
        out_file = destination_dir / f"{unit}{ext}"
        out_file.write_bytes(content)
        time.sleep(DOWNLOAD_DELAY_SECONDS)

    if missing_on_site:
        print("Unidades nao encontradas no site:")
        for unit in missing_on_site:
            print(f"  - {unit}")

    print(f"Download da lista finalizado. Arquivos em: {destination_dir.resolve()}\n")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automacao de pesquisa/download de RICs")
    parser.add_argument("command", choices=["search", "download", "download-list"], help="Acao a executar")
    parser.add_argument("--limit", type=int, default=None, help="Limita quantidade de links (teste)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cnpj, password = load_credentials(LOGIN_FILE)
    client = RicsClient(cnpj, password)

    try:
        if args.command == "search":
            return pesquisar_rics(client, limit=args.limit)
        if args.command == "download":
            return baixar_rics(client, limit=args.limit)
        if args.command == "download-list":
            return baixar_lista_unidades(client)
    except Exception as exc:
        print(f"ERRO: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
