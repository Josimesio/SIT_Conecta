from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Page,
    Download,
)
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import time
import traceback
import csv
import hashlib
import re

load_dotenv()

GTN_URL = os.getenv("GTN_URL", "https://gtn.ninecon.com.br/ords/r/gtn/gtn/login?tz=-3:00")
GTN_HOME_URL = os.getenv("GTN_HOME_URL", "https://gtn.ninecon.com.br/ords/r/gtn/gtn/home")
GTN_USER = os.getenv("GTN_USER")
GTN_PASS = os.getenv("GTN_PASS")

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DOWNLOAD_DIR = BASE_DIR / "downloads"
LOCK_FILE = BASE_DIR / "rodando.lock"
LOG_FILE = BASE_DIR / "execucao_fluxo2.log"

OUTPUT_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(exist_ok=True)

RELATORIO_POS_MODAL_ID = "36017690830433903"

RELATORIOS = [
    {"id": "75126574677490011", "nome": "relatorio_01"},
    {"id": "75307651324595294", "nome": "relatorio_02"},
    {"id": "75308641635576924", "nome": "relatorio_03"},
    {"id": "75312931254550487", "nome": "relatorio_04"},
    {"id": "75313445605545355", "nome": "relatorio_05"},
    {"id": "75313959829541095", "nome": "relatorio_06"},
    {"id": "75314469764536662", "nome": "relatorio_07"},
    {"id": "75314905291531893", "nome": "relatorio_08"},
    {"id": "75315471314525895", "nome": "relatorio_09"},
]

DOWNLOAD_TIMEOUT_MS = int(os.getenv("GTN_DOWNLOAD_TIMEOUT_MS", "180000"))
DEFAULT_TIMEOUT_MS = int(os.getenv("GTN_DEFAULT_TIMEOUT_MS", "60000"))
POST_DOWNLOAD_PAUSE_MS = int(os.getenv("GTN_POST_DOWNLOAD_PAUSE_MS", "2000"))
MAX_TENTATIVAS_DOWNLOAD = int(os.getenv("GTN_MAX_TENTATIVAS_DOWNLOAD", "3"))
MAX_TENTATIVAS_APLICAR_RELATORIO = int(os.getenv("GTN_MAX_TENTATIVAS_APLICAR_RELATORIO", "3"))
APEX_REFRESH_TIMEOUT_MS = int(os.getenv("GTN_APEX_REFRESH_TIMEOUT_MS", "45000"))
EXECUCAO_TESTES_READY_TIMEOUT_MS = int(os.getenv("GTN_EXECUCAO_TESTES_READY_TIMEOUT_MS", "120000"))


def url_tem_sessao(url: str) -> bool:
    try:
        return "session=" in (url or "").lower()
    except Exception:
        return False


def log(msg: str) -> None:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{agora}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def validar_env() -> None:
    faltando = []

    if not GTN_USER:
        faltando.append("GTN_USER")
    if not GTN_PASS:
        faltando.append("GTN_PASS")

    if faltando:
        raise ValueError(f"Variáveis ausentes no .env: {', '.join(faltando)}")


def pagina_aberta(page: Page) -> bool:
    try:
        return (page is not None) and (not page.is_closed())
    except Exception:
        return False


def aguardar_processamento_apex(page: Page, motivo: str = "") -> None:
    if motivo:
        log(f"🌀 Aguardando refresh APEX: {motivo}")

    seletores_loading = [
        ".u-Processing",
        ".u-Processing-spinner",
        ".a-Region-loading",
        ".a-Region--loading",
        ".a-IRR-loading",
        ".a-IRR-icon--processing",
        ".js-regionIsLoading",
        "[aria-busy='true']",
    ]

    for seletor in seletores_loading:
        try:
            page.locator(seletor).first.wait_for(state="hidden", timeout=APEX_REFRESH_TIMEOUT_MS)
        except Exception:
            continue

    page.wait_for_timeout(1200)


def obter_assinatura_grade(page: Page) -> str:
    seletores = [
        "#R35932200234408468 .a-IRR-table tbody",
        "#R35932200234408468 .a-GV-table tbody",
        "#R35932200234408468 .t-Report-report tbody",
        "table.a-IRR-table tbody",
    ]

    partes = []

    for seletor in seletores:
        try:
            alvo = page.locator(seletor).first
            if alvo.is_visible(timeout=1500):
                linhas = alvo.locator("tr")
                qtd = linhas.count()
                partes.append(f"rows={qtd}")

                limite = min(qtd, 5)
                for i in range(limite):
                    try:
                        texto = linhas.nth(i).inner_text(timeout=1500).strip()
                        texto = " ".join(texto.split())
                        if texto:
                            partes.append(texto[:220])
                    except Exception:
                        continue
                break
        except Exception:
            continue

    if not partes:
        try:
            partes.append(page.locator("#R35932200234408468").first.inner_text(timeout=2000)[:800])
        except Exception:
            partes.append("(sem assinatura de grade)")

    return " | ".join(partes)


def aplicar_select_saved_report(page: Page, relatorio_id: str) -> None:
    seletor = page.locator("#R35932200234408468_saved_reports")
    seletor.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)

    try:
        seletor.select_option(relatorio_id)
    except Exception:
        page.evaluate(
            """(cfg) => {
                const el = document.querySelector(cfg.selector);
                if (!el) throw new Error('select não encontrado');
                el.value = cfg.value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            {"selector": "#R35932200234408468_saved_reports", "value": relatorio_id},
        )
        return

    try:
        seletor.dispatch_event("input")
    except Exception:
        pass

    try:
        seletor.dispatch_event("change")
    except Exception:
        pass

    try:
        page.evaluate(
            """(cfg) => {
                const el = document.querySelector(cfg.selector);
                if (!el) return;
                el.value = cfg.value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            {"selector": "#R35932200234408468_saved_reports", "value": relatorio_id},
        )
    except Exception:
        pass


def aguardar_grade_mudar(page: Page, assinatura_anterior: str, relatorio_nome: str) -> str:
    inicio = time.time()
    ultima_assinatura = assinatura_anterior

    while (time.time() - inicio) * 1000 < APEX_REFRESH_TIMEOUT_MS:
        aguardar_processamento_apex(page, f"aplicação do relatório {relatorio_nome}")
        aguardar_estabilidade(page, f"refresh do relatório {relatorio_nome}")
        atual = obter_assinatura_grade(page)
        if atual and atual != assinatura_anterior:
            return atual
        ultima_assinatura = atual
        page.wait_for_timeout(1500)

    return ultima_assinatura


def aguardar_estabilidade(page: Page, motivo: str = "") -> None:
    if motivo:
        log(f"⏳ Aguardando estabilidade: {motivo}")

    try:
        page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    page.wait_for_timeout(1500)



def aguardar_execucao_testes_renderizada(page: Page, origem: str = "") -> None:
    """Aguarda a página Execução de Testes terminar de renderizar de verdade.

    Em APEX, o clique/goto pode alterar a URL antes da região da grade estar pronta.
    Por isso o sinal principal de pronto é o select de relatórios salvos da região
    #R35932200234408468_saved_reports ficar visível.
    """
    detalhe = f" ({origem})" if origem else ""
    log(f"🧪 Aguardando renderização completa da Execução de Testes{detalhe}...")

    try:
        page.wait_for_url(
            lambda url: (
                "execu" in (url or "").lower()
                and ("teste" in (url or "").lower() or "testes" in (url or "").lower())
            ),
            timeout=EXECUCAO_TESTES_READY_TIMEOUT_MS,
        )
        log(f"✅ URL da Execução de Testes detectada: {page.url}")
    except Exception:
        log("⚠️ A URL não mudou claramente para Execução de Testes. Vou validar pelo componente da tela.")

    try:
        page.wait_for_load_state("domcontentloaded", timeout=EXECUCAO_TESTES_READY_TIMEOUT_MS)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:
        # APEX às vezes mantém requisições abertas; não pode travar por isso.
        pass

    aguardar_processamento_apex(page, "renderização da página Execução de Testes")

    seletores_prontos = [
        "#R35932200234408468_saved_reports",
        "#R35932200234408468 button:has-text('Ações')",
        "#R35932200234408468 label:has-text('Linhas')",
        "button:has-text('Ações')",
        "label:has-text('Linhas')",
    ]

    ultimo_erro = None
    for seletor in seletores_prontos:
        try:
            page.locator(seletor).first.wait_for(
                state="visible",
                timeout=EXECUCAO_TESTES_READY_TIMEOUT_MS,
            )
            log(f"✅ Execução de Testes renderizada. Componente pronto: {seletor}")
            aguardar_processamento_apex(page, "pós-renderização da grade Execução de Testes")
            page.wait_for_timeout(1500)
            return
        except Exception as e:
            ultimo_erro = e
            continue

    salvar_debug(page, "execucao_testes_renderizacao_incompleta")
    raise RuntimeError(
        "A página Execução de Testes foi acionada, mas a grade/select de relatórios não ficou disponível "
        f"dentro de {EXECUCAO_TESTES_READY_TIMEOUT_MS} ms. Último erro: {ultimo_erro}"
    )


def salvar_debug(page: Page, nome_base: str) -> None:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = OUTPUT_DIR / f"{nome_base}_{timestamp}.png"
    html_path = OUTPUT_DIR / f"{nome_base}_{timestamp}.html"

    try:
        if not pagina_aberta(page):
            log("⚠️ Página já estava fechada. Debug visual não pôde ser salvo.")
            return

        page.screenshot(path=str(screenshot_path), full_page=False)
        html_path.write_text(page.content(), encoding="utf-8")
        log(f"📸 Screenshot salvo em: {screenshot_path}")
        log(f"📝 HTML salvo em: {html_path}")
    except Exception as e:
        log(f"⚠️ Falha ao salvar debug: {e}")


def fechar_modal_download(page: Page) -> None:
    def aplicar_select_pos_modal() -> None:
        try:
            log(f"🎯 Aplicando seleção pós-modal no relatório {RELATORIO_POS_MODAL_ID}...")
            aplicar_select_saved_report(page, RELATORIO_POS_MODAL_ID)
            aguardar_processamento_apex(page, "seleção pós-modal")
            log("⏳ Aguardando 5 segundos após select_option pós-modal...")
            page.wait_for_timeout(5000)
        except Exception as e:
            log(f"⚠️ Falha ao aplicar select_option pós-modal: {e}")

    candidatos = [
        page.get_by_role("button", name="Fechar"),
        page.get_by_role("button", name="Cancelar"),
        page.locator("button.ui-dialog-titlebar-close"),
        page.locator(".ui-dialog-titlebar-close"),
        page.locator("button.t-Dialog-closeButton"),
        page.locator("button[aria-label='Close']"),
    ]

    for candidato in candidatos:
        try:
            if candidato.first.is_visible(timeout=1500):
                candidato.first.click(timeout=3000)
                log("🪟 Janela/modal de download fechada.")
                page.wait_for_timeout(1000)
                aplicar_select_pos_modal()
                return
        except Exception:
            continue

    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        log("ℹ️ Modal não tinha botão claro. Tentei fechar com ESC.")
        aplicar_select_pos_modal()
    except Exception:
        log("ℹ️ Não foi possível fechar modal explicitamente. Seguindo o fluxo.")


def fazer_login(page: Page) -> None:
    log("🌐 Abrindo tela de login...")
    page.goto(GTN_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    aguardar_estabilidade(page, "carregamento inicial da tela de login")

    log("🔐 Preenchendo credenciais...")
    page.get_by_role("textbox", name="Usuário").click()
    page.get_by_role("textbox", name="Usuário").fill(GTN_USER)
    page.get_by_role("textbox", name="Senha").fill(GTN_PASS)

    log("➡️ Clicando em Acessar...")
    page.get_by_role("button", name="Acessar").click()

    try:
        page.wait_for_url(lambda url: "login" not in url.lower(), timeout=DEFAULT_TIMEOUT_MS)
    except Exception:
        pass

    aguardar_estabilidade(page, "pós-login")
    log(f"✅ Pós-login. URL atual: {page.url}")

    if "login" in page.url.lower():
        salvar_debug(page, "falha_login")
        raise RuntimeError(
            "O sistema permaneceu na tela de login após o acesso. "
            "Verifique credenciais, expiração de sessão ou bloqueio do APEX."
        )

    if not url_tem_sessao(page.url):
        log("ℹ️ URL sem session explícita. Tentando validar contexto da aplicação...")
        try:
            page.goto(GTN_HOME_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            aguardar_estabilidade(page, "validação da home após login")
            log(f"✅ Home validada. URL atual: {page.url}")
        except Exception as e:
            raise RuntimeError(f"Login aparentemente efetuado, mas a home não abriu corretamente: {e}")


def listar_botoes_visiveis(page: Page) -> None:
    try:
        botoes = page.locator("button:visible, a:visible")
        qtd = min(botoes.count(), 20)
        nomes = []
        for i in range(qtd):
            try:
                texto = botoes.nth(i).inner_text(timeout=500).strip()
                if not texto:
                    texto = (botoes.nth(i).get_attribute("aria-label") or "").strip()
                if not texto:
                    texto = (botoes.nth(i).get_attribute("title") or "").strip()
                if texto:
                    nomes.append(texto.replace("\n", " "))
            except Exception:
                continue
        if nomes:
            log(f"🔎 Ações/botões visíveis na tela: {nomes}")
    except Exception:
        pass


def tela_execucao_testes_ativa(page: Page) -> bool:
    candidatos = [
        "#R35932200234408468_saved_reports",
        "label:has-text('Linhas')",
        "button:has-text('Ações')",
    ]
    for seletor in candidatos:
        try:
            if page.locator(seletor).first.is_visible(timeout=1500):
                return True
        except Exception:
            continue
    return False


def tentar_abrir_menu_navegacao(page: Page) -> bool:
    candidatos = [
        page.get_by_role("button", name="Navegação Principal"),
        page.locator("#t_Button_navControl"),
        page.locator("button[aria-label='Navegação Principal']"),
        page.locator("button[title='Navegação Principal']"),
        page.locator("button[aria-label*='Navegação']"),
        page.locator("button[title*='Navegação']"),
        page.locator("button.t-Button--header"),
    ]

    for i, candidato in enumerate(candidatos, start=1):
        try:
            alvo = candidato.first
            if alvo.is_visible(timeout=2000):
                log(f"🧭 Abrindo navegação principal com seletor alternativo #{i}...")
                alvo.scroll_into_view_if_needed()
                alvo.click(timeout=5000, force=True)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    return False


def obter_link_apex_por_texto(page: Page, texto_procurado: str) -> str | None:
    """Procura links no DOM inteiro, inclusive itens ocultos do menu APEX."""
    try:
        return page.evaluate(
            """(textoProcurado) => {
                const normalizar = (v) => (v || '')
                    .normalize('NFD')
                    .replace(/[\u0300-\u036f]/g, '')
                    .toLowerCase()
                    .replace(/\\s+/g, ' ')
                    .trim();

                const alvo = normalizar(textoProcurado);
                const links = Array.from(document.querySelectorAll('a'));

                for (const a of links) {
                    const texto = normalizar(a.innerText || a.textContent || a.getAttribute('aria-label') || a.title || '');
                    const href = a.href || a.getAttribute('href') || '';
                    const hrefNorm = normalizar(href);

                    if ((texto && texto.includes(alvo)) || (hrefNorm && hrefNorm.includes(alvo.replace(/ /g, '-')))) {
                        return href;
                    }
                }

                return null;
            }""",
            texto_procurado,
        )
    except Exception:
        return None


def listar_links_relevantes_debug(page: Page) -> None:
    """Ajuda a diagnosticar quais links de Testes/Ocorrências existem no HTML atual."""
    try:
        links = page.evaluate(
            """() => {
                const normalizar = (v) => (v || '')
                    .normalize('NFD')
                    .replace(/[\u0300-\u036f]/g, '')
                    .toLowerCase();

                return Array.from(document.querySelectorAll('a'))
                    .map(a => ({
                        texto: (a.innerText || a.textContent || a.getAttribute('aria-label') || a.title || '').trim().replace(/\\s+/g, ' '),
                        href: a.href || a.getAttribute('href') || ''
                    }))
                    .filter(x => {
                        const combinado = normalizar(`${x.texto} ${x.href}`);
                        return combinado.includes('teste') || combinado.includes('execucao') || combinado.includes('ocorrencia');
                    })
                    .slice(0, 20);
            }"""
        )

        if links:
            resumo = []
            for item in links:
                texto = item.get('texto') or '(sem texto)'
                href = item.get('href') or '(sem href)'
                resumo.append(f"{texto} -> {href[:120]}")
            log(f"🔗 Links relevantes no HTML: {resumo}")
        else:
            log("🔗 Nenhum link relevante de teste/execução/ocorrência apareceu no HTML atual.")
    except Exception as e:
        log(f"⚠️ Não consegui listar links relevantes: {e}")


def expandir_no_arvore_por_texto(page: Page, texto: str) -> bool:
    """Expande o nó correto clicando no toggle do LI pai, não no texto do menu."""
    try:
        resultado = page.evaluate(
            """(textoAlvo) => {
                const normalizar = (v) => (v || '')
                    .normalize('NFD')
                    .replace(/[\u0300-\u036f]/g, '')
                    .toLowerCase()
                    .replace(/\\s+/g, ' ')
                    .trim();

                const alvo = normalizar(textoAlvo);
                const elementos = Array.from(document.querySelectorAll('li, a, span, div'));

                for (const el of elementos) {
                    const texto = normalizar(el.innerText || el.textContent || el.getAttribute('aria-label') || el.title || '');
                    if (!texto || !texto.includes(alvo)) continue;

                    const li = el.closest('li');
                    if (!li) continue;

                    const expanded = li.getAttribute('aria-expanded');
                    if (expanded === 'true') return 'ja_expandido';

                    const toggle = li.querySelector('.a-TreeView-toggle, button[aria-expanded], .a-TreeView-toggleIcon');
                    if (toggle) {
                        toggle.click();
                        return 'toggle_clicado';
                    }
                }

                return '';
            }""",
            texto,
        )

        if resultado:
            log(f"🌲 Nó '{texto}' tratado via JS: {resultado}")
            page.wait_for_timeout(1200)
            return True
    except Exception as e:
        log(f"⚠️ Falha ao expandir nó '{texto}' via JS: {e}")

    return False


def tentar_expandir_arvore(page: Page) -> None:
    """
    Expande a árvore do menu lateral sem clicar no texto do módulo.

    Observação importante:
    - Clicar em 'Gestão de Testes' pode navegar para a página do módulo.
    - O correto é clicar no toggle/ícone expansor do nó pai.
    """
    expandiu_algo = False

    for texto in ["Gestão de Testes", "Plano de Teste", "Testes"]:
        if expandir_no_arvore_por_texto(page, texto):
            expandiu_algo = True
            if tentar_abrir_execucao_testes_pelo_menu(page):
                return

    for rodada in range(1, 4):
        try:
            toggles = page.locator(".a-TreeView-toggle:visible, button[aria-expanded='false']:visible")
            qtd = toggles.count()
            log(f"🌲 Rodada {rodada}: toggles visíveis encontrados na árvore: {qtd}")

            for i in range(qtd):
                try:
                    alvo = toggles.nth(i)
                    alvo.scroll_into_view_if_needed()
                    alvo.click(timeout=3000, force=True)
                    page.wait_for_timeout(700)
                    expandiu_algo = True

                    if tentar_abrir_execucao_testes_pelo_menu(page):
                        return
                except Exception:
                    continue
        except Exception:
            continue

    if expandiu_algo:
        log("✅ Expansão da árvore finalizada. Tentando localizar 'Execução de Testes'.")
    else:
        log("ℹ️ Não consegui expandir a árvore. Vou tentar localizar links diretos no HTML.")


def tentar_abrir_execucao_testes_pelo_menu(page: Page) -> bool:
    candidatos = [
        page.get_by_role("treeitem", name="Execução de Testes"),
        page.get_by_role("link", name="Execução de Testes"),
        page.get_by_text("Execução de Testes", exact=True),
        page.locator("a:has-text('Execução de Testes')"),
        page.locator("span:has-text('Execução de Testes')"),
        page.locator("text=/Execu[cç][aã]o de Testes/i"),
        page.locator("a[href*='execucao'][href*='teste']"),
        page.locator("a[href*='teste']"),
    ]

    for i, candidato in enumerate(candidatos, start=1):
        try:
            alvo = candidato.first
            if alvo.is_visible(timeout=1800):
                log(f"🧪 Entrando em Execução de Testes com seletor alternativo #{i}...")
                alvo.scroll_into_view_if_needed()
                alvo.click(timeout=10000, force=True)
                aguardar_execucao_testes_renderizada(page, f"clique no menu - seletor #{i}")
                if tela_execucao_testes_ativa(page):
                    return True
        except Exception:
            continue

    link = obter_link_apex_por_texto(page, "Execução de Testes")
    if link:
        try:
            log(f"🧪 Abrindo Execução de Testes por link encontrado no HTML: {link[:160]}")
            page.goto(link, wait_until="domcontentloaded", timeout=EXECUCAO_TESTES_READY_TIMEOUT_MS)
            aguardar_execucao_testes_renderizada(page, "abertura por link encontrado no HTML")
            return tela_execucao_testes_ativa(page)
        except Exception as e:
            log(f"⚠️ Link encontrado, mas falhou ao abrir Execução de Testes: {e}")

    return False


def tentar_abrir_execucao_testes_por_url_amigavel(page: Page) -> bool:
    """Último fallback: tenta aliases comuns do APEX preservando a sessão atual."""
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        atual = page.url
        parsed = urlparse(atual)
        partes = parsed.path.rstrip('/').split('/')

        if not partes:
            return False

        # Troca somente o alias da página, preservando /ords/r/workspace/app/
        base_path = '/'.join(partes[:-1])
        query = parse_qs(parsed.query)

        session = None
        for chave in ["session", "cs"]:
            if chave in query and query[chave]:
                session = query[chave][0]
                break

        aliases = [
            "execucao-de-testes",
            "execucao-testes",
            "execu%C3%A7%C3%A3o-de-testes",
            "execu%C3%A7%C3%A3o-testes",
            "execucao-de-teste",
        ]

        for alias in aliases:
            nova_query = parsed.query
            nova_url = urlunparse((parsed.scheme, parsed.netloc, f"{base_path}/{alias}", '', nova_query, ''))
            log(f"🧭 Tentando URL amigável da Execução de Testes: {nova_url}")
            try:
                page.goto(nova_url, wait_until="domcontentloaded", timeout=EXECUCAO_TESTES_READY_TIMEOUT_MS)
                aguardar_execucao_testes_renderizada(page, f"fallback URL {alias}")
                if tela_execucao_testes_ativa(page):
                    log("✅ Execução de Testes aberta via URL amigável.")
                    return True
            except Exception as e:
                log(f"ℹ️ Alias {alias} não abriu a tela esperada: {e}")

    except Exception as e:
        log(f"⚠️ Falha no fallback de URL amigável: {e}")

    return False


def abrir_execucao_testes(page: Page) -> None:
    if tela_execucao_testes_ativa(page):
        log("✅ Tela de Execução de Testes já está ativa. Seguindo o fluxo.")
        return

    log(f"🔎 URL atual antes de abrir menu: {page.url}")

    if not url_tem_sessao(page.url):
        raise RuntimeError(
            "A URL atual não contém sessão válida do APEX. O login não ficou persistido na navegação."
        )

    aguardar_estabilidade(page, "estado atual após login")

    if tela_execucao_testes_ativa(page):
        log("✅ Tela de Execução de Testes ficou disponível sem precisar navegar de novo.")
        return

    menu_aberto = tentar_abrir_menu_navegacao(page)
    if not menu_aberto:
        listar_botoes_visiveis(page)
        listar_links_relevantes_debug(page)
        salvar_debug(page, "sem_menu_no_estado_atual")
        raise RuntimeError(
            "Não encontrei o botão/menu de navegação principal no estado atual da página. "
            "Não vou redirecionar para HOME sem session para não derrubar o login."
        )

    tentar_expandir_arvore(page)

    if tela_execucao_testes_ativa(page):
        log(f"✅ Tela de execução carregada: {page.url}")
        return

    if tentar_abrir_execucao_testes_pelo_menu(page):
        log(f"✅ Tela de execução carregada: {page.url}")
        return

    listar_links_relevantes_debug(page)

    if tentar_abrir_execucao_testes_por_url_amigavel(page):
        log(f"✅ Tela de execução carregada: {page.url}")
        return

    listar_botoes_visiveis(page)
    salvar_debug(page, "menu_sem_execucao_testes")
    raise RuntimeError(
        "Não encontrei a opção 'Execução de Testes' no menu lateral nem por links/URLs alternativas. "
        "Verifique se o usuário tem permissão nessa tela ou envie o HTML salvo para eu mapear o alias exato."
    )


def selecionar_relatorio(page: Page, relatorio_id: str, relatorio_nome: str) -> None:
    log(f"📑 Selecionando relatório {relatorio_nome} ({relatorio_id})...")
    seletor = page.locator("#R35932200234408468_saved_reports")
    seletor.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    seletor.select_option(relatorio_id)
    aguardar_estabilidade(page, f"seleção do relatório {relatorio_nome}")

    valor_atual = ""
    try:
        valor_atual = seletor.input_value(timeout=3000).strip()
    except Exception:
        pass

    texto_atual = obter_texto_relatorio_selecionado(page)
    log(f"🧾 Relatório selecionado na tela -> id atual: {valor_atual or '(indisponível)'} | nome visível: {texto_atual}")

    if valor_atual and valor_atual != relatorio_id:
        raise RuntimeError(
            f"O select não confirmou o ID esperado. Esperado: {relatorio_id} | Atual na tela: {valor_atual}"
        )


def obter_texto_relatorio_selecionado(page: Page) -> str:
    try:
        seletor = page.locator("#R35932200234408468_saved_reports")
        texto = seletor.locator("option:checked").first.inner_text(timeout=3000).strip()
        return texto
    except Exception:
        return "(não foi possível obter o nome visível do relatório selecionado)"


def calcular_hash_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def contar_linhas_csv(caminho: Path) -> int:
    with abrir_csv_com_encoding_flexivel(caminho) as entrada:
        amostra = entrada.read(4096)
        entrada.seek(0)

        try:
            dialect = csv.Sniffer().sniff(amostra, delimiters=",;\t|")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ";" if ";" in amostra else ","

        reader = csv.reader(entrada, dialect)
        try:
            next(reader)
        except StopIteration:
            return 0

        return sum(1 for linha in reader if any((col or '').strip() for col in linha))


def ajustar_quantidade_linhas(page: Page) -> None:
    log("📄 Ajustando quantidade de linhas para 100000...")
    linhas = page.get_by_label("Linhas", exact=True)
    linhas.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    linhas.select_option("100000")
    try:
        linhas.dispatch_event("change")
    except Exception:
        pass
    aguardar_processamento_apex(page, "ajuste da quantidade de linhas")
    aguardar_estabilidade(page, "ajuste da quantidade de linhas")



def clicar_primeiro_que_aparecer(page: Page, tentativas: list[tuple[str, object]], descricao: str, timeout: int = 8000) -> None:
    """Clica no primeiro locator visível dentre várias alternativas.

    Uso principal: menus do APEX que mudam texto/role conforme idioma, tema,
    renderização ou estado do Interactive Report.
    """
    ultimo_erro = None

    for nome, locator_fn in tentativas:
        try:
            locator = locator_fn()
            alvo = locator.first
            alvo.wait_for(state="visible", timeout=timeout)
            try:
                alvo.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass
            alvo.click(timeout=timeout, force=True)
            log(f"✅ Clique efetuado em {descricao}: {nome}")
            return
        except Exception as e:
            ultimo_erro = e
            continue

    raise RuntimeError(f"Não encontrei/click no {descricao}. Último erro: {ultimo_erro}")


def listar_menu_download_debug(page: Page) -> None:
    """Lista itens visíveis quando o menu de ações não apresenta Download."""
    try:
        itens = page.locator(".a-Menu-content :visible, [role='menu'] :visible, [role='menuitem']:visible")
        qtd = min(itens.count(), 30)
        textos = []
        for i in range(qtd):
            try:
                txt = itens.nth(i).inner_text(timeout=500).strip()
                if txt:
                    textos.append(" ".join(txt.split()))
            except Exception:
                continue
        if textos:
            log(f"🔎 Itens visíveis no menu APEX: {textos}")
    except Exception:
        pass


def abrir_menu_acoes_relatorio(page: Page) -> None:
    log("📤 Abrindo menu Ações do relatório...")

    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    except Exception:
        pass

    aguardar_processamento_apex(page, "antes de abrir menu Ações")

    tentativas_menu_acoes = [
        (
            "botão Ações por role",
            lambda: page.get_by_role("button", name=re.compile(r"Ações|Actions", re.I)),
        ),
        (
            "botão Ações dentro da região R35932200234408468",
            lambda: page.locator("#R35932200234408468 button").filter(has_text=re.compile(r"Ações|Actions", re.I)),
        ),
        (
            "botão padrão APEX IRR actions",
            lambda: page.locator("#R35932200234408468 button.a-IRR-button--actions, button.a-IRR-button--actions"),
        ),
        (
            "id APEX actions_button",
            lambda: page.locator("#R35932200234408468_actions_button, button[id$='_actions_button']"),
        ),
        (
            "aria-label/title Ações",
            lambda: page.locator("button[aria-label*='Ações'], button[title*='Ações'], button[aria-label*='Actions'], button[title*='Actions']"),
        ),
    ]

    clicar_primeiro_que_aparecer(page, tentativas_menu_acoes, "menu Ações", timeout=10000)
    page.wait_for_timeout(1000)


def abrir_download_csv(page: Page) -> None:
    """Abre o modal de download CSV do APEX de forma resiliente.

    O erro que estava derrubando o fluxo acontecia porque o script procurava
    apenas o menuitem com nome exatamente 'Fazer Download'. Em algumas cargas do
    APEX esse item aparece como 'Download', demora mais, ou perde o role.
    """
    abrir_menu_acoes_relatorio(page)

    log("📄 Selecionando opção de download...")

    tentativas_download = [
        (
            "menuitem Fazer Download/Download",
            lambda: page.get_by_role("menuitem", name=re.compile(r"Fazer\s+Download|Download|Baixar", re.I)),
        ),
        (
            "link/botão com texto Fazer Download",
            lambda: page.locator("a:has-text('Fazer Download'), button:has-text('Fazer Download')"),
        ),
        (
            "link/botão com texto Download/Baixar",
            lambda: page.locator("a:has-text('Download'), button:has-text('Download'), a:has-text('Baixar'), button:has-text('Baixar')"),
        ),
        (
            "item APEX a-Menu contendo download",
            lambda: page.locator(".a-Menu-content a, .a-Menu-content li, [role='menuitem']").filter(has_text=re.compile(r"Fazer\s+Download|Download|Baixar", re.I)),
        ),
        (
            "texto Download visível",
            lambda: page.get_by_text(re.compile(r"Fazer\s+Download|^\s*Download\s*$|^\s*Baixar\s*$", re.I)),
        ),
    ]

    try:
        clicar_primeiro_que_aparecer(page, tentativas_download, "opção Fazer Download/Download", timeout=12000)
    except Exception:
        listar_menu_download_debug(page)
        salvar_debug(page, "menu_sem_fazer_download")
        raise

    page.wait_for_timeout(1400)

    # Seleciona CSV quando a tela/modal oferece escolha de formato.
    tentativas_csv = [
        (
            "option CSV",
            lambda: page.get_by_role("option", name=re.compile(r"CSV", re.I)),
        ),
        (
            "radio CSV por role",
            lambda: page.get_by_role("radio", name=re.compile(r"CSV", re.I)),
        ),
        (
            "label CSV",
            lambda: page.locator("label:has-text('CSV')"),
        ),
        (
            "input CSV",
            lambda: page.locator("input[value='CSV'], input[value='csv']"),
        ),
        (
            "texto CSV",
            lambda: page.get_by_text(re.compile(r"^\s*CSV\s*$", re.I)),
        ),
    ]

    try:
        clicar_primeiro_que_aparecer(page, tentativas_csv, "formato CSV", timeout=5000)
        log("✅ Formato CSV selecionado explicitamente.")
        page.wait_for_timeout(500)
    except Exception:
        log("ℹ️ Opção CSV não apareceu explicitamente. Seguindo com o padrão da tela.")


def clicar_botao_download_final(page: Page) -> None:
    """Clica no botão final do modal de download e deixa o expect_download capturar."""
    tentativas_botao_final = [
        (
            "botão Fazer Download/Download/Baixar por role",
            lambda: page.get_by_role("button", name=re.compile(r"Fazer\s+Download|Download|Baixar", re.I)),
        ),
        (
            "botão no diálogo/modal",
            lambda: page.locator(".ui-dialog button, .t-Dialog button, [role='dialog'] button").filter(has_text=re.compile(r"Fazer\s+Download|Download|Baixar", re.I)),
        ),
        (
            "button por texto",
            lambda: page.locator("button:has-text('Fazer Download'), button:has-text('Download'), button:has-text('Baixar')"),
        ),
        (
            "link por texto",
            lambda: page.locator("a:has-text('Fazer Download'), a:has-text('Download'), a:has-text('Baixar')"),
        ),
    ]

    clicar_primeiro_que_aparecer(page, tentativas_botao_final, "botão final de download", timeout=12000)


def coletar_indicios_apos_clique(page: Page) -> None:
    try:
        dialogos = page.locator(".ui-dialog, .t-Dialog, [role='dialog']")
        qtd = dialogos.count()
        log(f"🔎 Diálogos visíveis após clique: {qtd}")
    except Exception:
        pass

    try:
        botoes = page.locator("button:visible")
        qtd = min(botoes.count(), 12)
        nomes = []
        for i in range(qtd):
            texto = botoes.nth(i).inner_text(timeout=1000).strip()
            if texto:
                nomes.append(texto.replace("\n", " "))
        if nomes:
            log(f"🔎 Botões visíveis: {nomes}")
    except Exception:
        pass



def esperar_download_com_fallback(page: Page, relatorio_nome: str) -> Download:
    ultimo_erro = None

    for tentativa in range(1, MAX_TENTATIVAS_DOWNLOAD + 1):
        log(f"⬇️ Tentativa {tentativa}/{MAX_TENTATIVAS_DOWNLOAD} de download para {relatorio_nome}...")

        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as download_info:
                clicar_botao_download_final(page)
            download = download_info.value
            log(f"✅ Evento de download capturado para {relatorio_nome}.")
            return download

        except PlaywrightTimeoutError as e:
            ultimo_erro = e
            log(f"⚠️ Timeout aguardando download do {relatorio_nome} na tentativa {tentativa}.")
            coletar_indicios_apos_clique(page)
            salvar_debug(page, f"timeout_download_{relatorio_nome}_tentativa_{tentativa}")

            try:
                popup = page.context.wait_for_event("page", timeout=5000)
                popup.wait_for_load_state("domcontentloaded", timeout=10000)
                log(f"🪟 Popup detectado após clique. URL: {popup.url}")
                try:
                    with popup.expect_download(timeout=15000) as download_info:
                        popup.wait_for_timeout(2000)
                    download = download_info.value
                    log(f"✅ Download capturado via popup para {relatorio_nome}.")
                    return download
                except Exception:
                    log("ℹ️ Popup apareceu, mas não entregou download automaticamente.")
            except Exception:
                log("ℹ️ Nenhum popup detectado após a tentativa.")

            if tentativa < MAX_TENTATIVAS_DOWNLOAD:
                fechar_modal_download(page)
                abrir_download_csv(page)

        except Exception as e:
            ultimo_erro = e
            log(f"⚠️ Falha ao acionar botão final de download do {relatorio_nome} na tentativa {tentativa}: {e}")
            coletar_indicios_apos_clique(page)
            salvar_debug(page, f"falha_botao_download_{relatorio_nome}_tentativa_{tentativa}")

            if tentativa < MAX_TENTATIVAS_DOWNLOAD:
                fechar_modal_download(page)
                abrir_download_csv(page)

    raise RuntimeError(
        f"Nenhum download foi disparado para {relatorio_nome} após {MAX_TENTATIVAS_DOWNLOAD} tentativas. Último erro: {ultimo_erro}"
    )


def baixar_relatorio(page: Page, relatorio_nome: str) -> Path:
    abrir_download_csv(page)
    log(f"⬇️ Iniciando rotina blindada de download do relatório {relatorio_nome}...")

    download = esperar_download_com_fallback(page, relatorio_nome)

    erro_download = download.failure()
    if erro_download:
        raise RuntimeError(f"Falha no download do relatório {relatorio_nome}: {erro_download}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_original = download.suggested_filename or f"{relatorio_nome}.csv"
    nome_limpo = nome_original.replace(" ", "_")
    destino = DOWNLOAD_DIR / f"{timestamp}_{relatorio_nome}_{nome_limpo}"

    download.save_as(str(destino))
    log(f"✅ Download salvo em: {destino}")

    fechar_modal_download(page)
    page.wait_for_timeout(POST_DOWNLOAD_PAUSE_MS)
    return destino



def fechar_modal_download_simples(page: Page) -> None:
    """Fecha o modal de download sem aplicar relatório pós-modal.

    Usado na tela de Ocorrências, porque ali não existe a mesma regra de
    select pós-modal dos relatórios de Execução de Testes.
    """
    candidatos = [
        page.get_by_role("button", name="Fechar"),
        page.get_by_role("button", name="Cancelar"),
        page.locator("button.ui-dialog-titlebar-close"),
        page.locator(".ui-dialog-titlebar-close"),
        page.locator("button.t-Dialog-closeButton"),
        page.locator("button[aria-label='Close']"),
    ]

    for candidato in candidatos:
        try:
            if candidato.first.is_visible(timeout=1500):
                candidato.first.click(timeout=3000)
                log("🪟 Janela/modal de download de ocorrências fechada.")
                page.wait_for_timeout(1000)
                return
        except Exception:
            continue

    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        log("ℹ️ Modal de ocorrências não tinha botão claro. Tentei fechar com ESC.")
    except Exception:
        log("ℹ️ Não foi possível fechar modal de ocorrências explicitamente. Seguindo o fluxo.")


def tentar_abrir_ocorrencias_pelo_menu(page: Page) -> bool:
    candidatos = [
        page.get_by_role("treeitem", name="Ocorrências"),
        page.get_by_role("link", name="Ocorrências"),
        page.get_by_text("Ocorrências", exact=True),
        page.locator("a:has-text('Ocorrências')"),
        page.locator("span:has-text('Ocorrências')"),
    ]

    for i, candidato in enumerate(candidatos, start=1):
        try:
            alvo = candidato.first
            if alvo.is_visible(timeout=2500):
                log(f"🐞 Entrando em Ocorrências com seletor alternativo #{i}...")
                alvo.scroll_into_view_if_needed()
                alvo.click(timeout=8000, force=True)
                aguardar_estabilidade(page, "entrada em Ocorrências")
                return True
        except Exception:
            continue

    return False


def abrir_ocorrencias(page: Page) -> None:
    log("🐞 Abrindo tela de Ocorrências...")

    if tentar_abrir_ocorrencias_pelo_menu(page):
        return

    menu_aberto = tentar_abrir_menu_navegacao(page)
    if menu_aberto:
        tentar_expandir_arvore(page)
        if tentar_abrir_ocorrencias_pelo_menu(page):
            return

    listar_botoes_visiveis(page)
    salvar_debug(page, "menu_sem_ocorrencias")
    raise RuntimeError("Não encontrei a opção 'Ocorrências' no menu lateral.")


def baixar_ocorrencias(page: Page) -> Path:
    """Baixa o CSV de Ocorrências para o output com nome fixo do dashboard."""
    abrir_ocorrencias(page)

    log("📄 Ajustando quantidade de linhas das Ocorrências para 100000...")
    linhas = page.get_by_label("Linhas", exact=True)
    linhas.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    linhas.select_option("100000")
    try:
        linhas.dispatch_event("change")
    except Exception:
        pass

    aguardar_processamento_apex(page, "ajuste de linhas em Ocorrências")
    aguardar_estabilidade(page, "ajuste de linhas em Ocorrências")

    abrir_download_csv(page)
    log("⬇️ Iniciando download do relatório de Ocorrências...")

    with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as download_info:
        clicar_botao_download_final(page)

    download = download_info.value
    erro_download = download.failure()
    if erro_download:
        raise RuntimeError(f"Falha no download de Ocorrências: {erro_download}")

    destino = OUTPUT_DIR / "Ocorrencias_Consolidadas_atualizado.csv"
    download.save_as(str(destino))
    log(f"✅ Ocorrências salvas em: {destino}")

    fechar_modal_download_simples(page)
    page.wait_for_timeout(POST_DOWNLOAD_PAUSE_MS)

    try:
        linhas_ocorrencias = contar_linhas_csv(destino)
        log(f"🧮 {destino.name} -> linhas de dados: {linhas_ocorrencias}")
    except Exception as e:
        log(f"⚠️ Não consegui contar as linhas do CSV de Ocorrências: {e}")

    return destino


def processar_relatorios(page: Page) -> list[Path]:
    arquivos_baixados = []
    hashes_anteriores: dict[str, dict[str, str | int]] = {}

    for indice, relatorio in enumerate(RELATORIOS, start=1):
        log("--------------------------------------------------")
        log(f"🚚 Processando relatório {indice}/{len(RELATORIOS)}: {relatorio['nome']}")
        selecionar_relatorio(page, relatorio["id"], relatorio["nome"])
        ajustar_quantidade_linhas(page)

        try:
            arquivo = baixar_relatorio(page, relatorio["nome"])
            arquivos_baixados.append(arquivo)

            hash_atual = calcular_hash_arquivo(arquivo)
            linhas_atuais = contar_linhas_csv(arquivo)
            log(f"🧮 {arquivo.name} -> linhas de dados: {linhas_atuais} | hash: {hash_atual[:16]}")

            if hash_atual in hashes_anteriores:
                anterior = hashes_anteriores[hash_atual]
                log(
                    "🚨 CSV repetido detectado! "
                    f"{arquivo.name} está idêntico ao arquivo {anterior['arquivo']} "
                    f"(relatório {anterior['relatorio']}, {anterior['linhas']} linhas)."
                )
            else:
                hashes_anteriores[hash_atual] = {
                    "arquivo": arquivo.name,
                    "relatorio": relatorio["nome"],
                    "linhas": linhas_atuais,
                }

        except Exception as e:
            log(f"❌ Falha ao baixar {relatorio['nome']}: {e}")
            salvar_debug(page, f"falha_{relatorio['nome']}")
            raise

    return arquivos_baixados


def abrir_csv_com_encoding_flexivel(caminho: Path):
    encodings_teste = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    ultimo_erro = None

    for encoding in encodings_teste:
        try:
            f = open(caminho, "r", newline="", encoding=encoding)
            f.read(4096)
            f.seek(0)
            log(f"🔤 Lendo {caminho.name} com encoding: {encoding}")
            return f
        except UnicodeDecodeError as e:
            ultimo_erro = e
            try:
                f.close()
            except Exception:
                pass
            continue

    raise RuntimeError(
        f"Não foi possível ler o CSV {caminho.name} com os encodings suportados. Último erro: {ultimo_erro}"
    )


def obter_timestamp_geracao() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M")


def normalizar_nome_coluna(nome: str) -> str:
    mapa = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
        "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC",
    )
    return " ".join((nome or "").translate(mapa).strip().lower().split())


def montar_cabecalho_com_frente(cabecalho_atual: list[str]) -> tuple[list[str], int | None, int | None]:
    """
    Monta o cabeçalho final do consolidado garantindo a coluna Frente.

    Regra oficial:
    - Origem: coluna 'Área de Negócio' do CSV bruto.
    - Destino: coluna 'Frente' no CSV consolidado.
    - A coluna 'Área de Negócio' é preservada.
    - A coluna 'Frente' é inserida logo após 'Área de Negócio'.
    """
    colunas_normalizadas = [normalizar_nome_coluna(c) for c in cabecalho_atual]

    area_idx = None
    frente_idx = None

    for idx, nome in enumerate(colunas_normalizadas):
        if nome == "area de negocio":
            area_idx = idx
        elif nome == "frente":
            frente_idx = idx

    if area_idx is None and frente_idx is None:
        raise RuntimeError(
            "Não encontrei a coluna 'Área de Negócio' no CSV bruto para gerar a coluna 'Frente'."
        )

    cabecalho_saida = list(cabecalho_atual)

    if frente_idx is None:
        posicao_frente = (area_idx + 1) if area_idx is not None else len(cabecalho_saida)
        cabecalho_saida.insert(posicao_frente, "Frente")
        frente_idx_saida = posicao_frente
    else:
        frente_idx_saida = frente_idx

    return cabecalho_saida, area_idx, frente_idx_saida


def montar_linha_com_frente(
    linha: list[str],
    cabecalho_atual: list[str],
    cabecalho_saida_sem_gerado_em: list[str],
    area_idx: int | None,
) -> list[str]:
    linha_ajustada = list(linha)

    if len(linha_ajustada) < len(cabecalho_atual):
        linha_ajustada += [""] * (len(cabecalho_atual) - len(linha_ajustada))
    elif len(linha_ajustada) > len(cabecalho_atual):
        linha_ajustada = linha_ajustada[:len(cabecalho_atual)]

    colunas_normalizadas = [normalizar_nome_coluna(c) for c in cabecalho_atual]
    ja_tem_frente = "frente" in colunas_normalizadas

    if ja_tem_frente:
        return linha_ajustada

    frente = ""
    if area_idx is not None and area_idx < len(linha_ajustada):
        frente = (linha_ajustada[area_idx] or "").strip()

    # Insere Frente na mesma posição definida no cabeçalho de saída.
    try:
        posicao_frente = [normalizar_nome_coluna(c) for c in cabecalho_saida_sem_gerado_em].index("frente")
    except ValueError:
        posicao_frente = len(linha_ajustada)

    linha_ajustada.insert(posicao_frente, frente)
    return linha_ajustada



PRIORIDADES_CENARIO_PERMITIDAS = {"p1", "p2", "p3", "p9"}


def normalizar_valor_prioridade(valor: str) -> str:
    """Normaliza valores como P1, p1, P1 - Alta para comparação segura."""
    valor_normalizado = normalizar_nome_coluna(valor)
    if not valor_normalizado:
        return ""

    primeiro_token = valor_normalizado.replace("-", " ").replace("_", " ").split()[0]
    return primeiro_token.strip()


def obter_indice_coluna_prioridade(cabecalho_atual: list[str]) -> int:
    """Localiza a coluna de prioridade no CSV bruto.

    Aceita nomes como:
    - Prioridade
    - Grupo de Prioridade
    - Grupo Prioridade
    """
    colunas_normalizadas = [normalizar_nome_coluna(c) for c in cabecalho_atual]

    candidatos_exatos = [
        "prioridade",
        "grupo de prioridade",
        "grupo prioridade",
    ]

    for candidato in candidatos_exatos:
        if candidato in colunas_normalizadas:
            return colunas_normalizadas.index(candidato)

    for idx, nome in enumerate(colunas_normalizadas):
        if "prioridade" in nome:
            return idx

    raise RuntimeError(
        "Não encontrei uma coluna de prioridade no CSV bruto. "
        "Para gerar o arquivo de cenários, preciso de uma coluna como 'Prioridade' "
        "ou 'Grupo de Prioridade'."
    )


def linha_tem_prioridade_permitida(linha: list[str], prioridade_idx: int) -> bool:
    if prioridade_idx >= len(linha):
        return False

    prioridade = normalizar_valor_prioridade(linha[prioridade_idx])
    return prioridade in PRIORIDADES_CENARIO_PERMITIDAS

def consolidar_csvs(arquivos_csv: list[Path]) -> Path:
    if not arquivos_csv:
        raise RuntimeError("Nenhum CSV foi baixado para consolidar.")

    destino = OUTPUT_DIR / "Cenarios_Consolidados_atualizado.csv"
    total_linhas = 0
    cabecalho_base = None
    cabecalho_saida_sem_gerado_em = None
    gerado_em = obter_timestamp_geracao()

    with open(destino, "w", newline="", encoding="utf-8-sig") as saida:
        writer = None

        for arquivo in arquivos_csv:
            if not arquivo.exists():
                log(f"⚠️ Arquivo não encontrado para consolidação: {arquivo}")
                continue

            log(f"🧩 Consolidando arquivo: {arquivo.name}")

            with abrir_csv_com_encoding_flexivel(arquivo) as entrada:
                amostra = entrada.read(4096)
                entrada.seek(0)

                try:
                    dialect = csv.Sniffer().sniff(amostra, delimiters=",;\t|")
                except Exception:
                    dialect = csv.excel
                    dialect.delimiter = ";" if ";" in amostra else ","

                reader = csv.reader(entrada, dialect)

                try:
                    cabecalho_atual = next(reader)
                except StopIteration:
                    log(f"ℹ️ Arquivo vazio ignorado na consolidação: {arquivo.name}")
                    continue

                cabecalho_atual = [c.strip() for c in cabecalho_atual]
                cabecalho_saida_atual, area_idx, frente_idx_saida = montar_cabecalho_com_frente(cabecalho_atual)

                if writer is None:
                    cabecalho_saida_sem_gerado_em = cabecalho_saida_atual
                    cabecalho_base = cabecalho_saida_atual + ["Gerado em"]
                    writer = csv.writer(saida, delimiter=';')
                    writer.writerow(cabecalho_base)
                    log(f"🧱 Cabeçalho base definido com {len(cabecalho_base)} colunas.")
                    log(f"🧭 Coluna 'Frente' criada na posição {frente_idx_saida + 1}, baseada em 'Área de Negócio'.")
                else:
                    if cabecalho_saida_atual + ["Gerado em"] != cabecalho_base:
                        raise RuntimeError(
                            "Estrutura divergente entre os CSVs baixados após aplicar a coluna 'Frente'. "
                            f"Arquivo com divergência: {arquivo.name}"
                        )

                prioridade_idx = obter_indice_coluna_prioridade(cabecalho_atual)
                log(
                    "🎯 Filtro de cenários ativo: considerando somente prioridades "
                    f"{', '.join(p.upper() for p in sorted(PRIORIDADES_CENARIO_PERMITIDAS))} "
                    f"pela coluna '{cabecalho_atual[prioridade_idx]}'."
                )

                linhas_arquivo = 0
                linhas_ignoradas_prioridade = 0

                for linha in reader:
                    if not any((col or '').strip() for col in linha):
                        continue

                    if not linha_tem_prioridade_permitida(linha, prioridade_idx):
                        linhas_ignoradas_prioridade += 1
                        continue

                    linha_saida = montar_linha_com_frente(
                        linha=linha,
                        cabecalho_atual=cabecalho_atual,
                        cabecalho_saida_sem_gerado_em=cabecalho_saida_sem_gerado_em,
                        area_idx=area_idx,
                    )

                    writer.writerow(linha_saida + [gerado_em])
                    linhas_arquivo += 1
                    total_linhas += 1

                log(
                    f"✅ {arquivo.name}: {linhas_arquivo} linhas adicionadas ao consolidado "
                    f"com prioridades P1/P2/P3/P9. "
                    f"Linhas ignoradas por prioridade fora do escopo: {linhas_ignoradas_prioridade}."
                )

    if cabecalho_base is None:
        raise RuntimeError("Os arquivos baixados não continham dados válidos para consolidar.")

    log(f"📦 Consolidado gerado em: {destino}")
    log(f"📊 Total de linhas no geral.csv: {total_linhas}")
    return destino


def executar_fluxo() -> None:
    validar_env()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-dev-shm-usage",
                "--disable-popup-blocking",
            ],
        )
        context = browser.new_context(accept_downloads=True)
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.new_page()

        try:
            fazer_login(page)
            abrir_execucao_testes(page)

            arquivos_baixados = processar_relatorios(page)
            arquivo_ocorrencias = baixar_ocorrencias(page)
            arquivo_consolidado = consolidar_csvs(arquivos_baixados)

            salvar_debug(page, "final_sucesso")

            log("🎯 Processo concluído com sucesso.")
            for arquivo in arquivos_baixados:
                log(f"📥 Arquivo baixado: {arquivo}")
            log(f"🐞 Arquivo de ocorrências final: {arquivo_ocorrencias}")
            log(f"🗂️ Arquivo consolidado final: {arquivo_consolidado}")

        except PlaywrightTimeoutError as e:
            log(f"⏰ Timeout: {e}")
            salvar_debug(page, "timeout")
            raise

        except Exception as e:
            log(f"❌ Erro: {e}")
            salvar_debug(page, "erro")
            raise

        finally:
            try:
                context.close()
            finally:
                browser.close()


def executar() -> None:
    if LOCK_FILE.exists():
        log("⚠️ Já existe uma execução em andamento. Encerrando.")
        return

    try:
        LOCK_FILE.touch()

        log("==================================================")
        log("🚀 Iniciando execução do fluxo 2 GTN")
        log("==================================================")

        executar_fluxo()

        log("✅ Execução encerrada com sucesso.")

    except Exception as e:
        log(f"❌ Falha geral na execução: {e}")
        log(traceback.format_exc())

    finally:
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception as e:
            log(f"⚠️ Não consegui remover lock file: {e}")


if __name__ == "__main__":
    executar()